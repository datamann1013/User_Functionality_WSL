use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

use crate::actions::service as svc;
use crate::actions::setup::{self, SetupRequest};
use crate::config::MarshalConfig;
use crate::rbac::{self, RbacResult};
use crate::registry::Registry;

pub type ActionLog = Arc<Mutex<VecDeque<String>>>;

/// Shared application state for Axum handlers
#[derive(Clone)]
pub struct AppState {
    pub config: Arc<MarshalConfig>,
    pub registry: Registry,
    pub action_log: ActionLog,
    // Caller CN is extracted by the TLS layer and injected via extension.
    // In dev/test mode (no client cert), this may be None.
}

/// Axum extension carrying the authenticated caller CN (from mTLS client cert)
#[derive(Clone)]
pub struct CallerCn(pub Option<String>);

// ── Helpers ──────────────────────────────────────────────────────────────────

fn rbac_check(
    cfg: &MarshalConfig,
    caller: &Option<String>,
    action: &str,
) -> Result<(), (StatusCode, Json<Value>)> {
    let cn = match caller {
        Some(cn) => cn.as_str(),
        None => {
            return Err((
                StatusCode::UNAUTHORIZED,
                Json(json!({"error": "mTLS client certificate required", "code": "EMAS02"})),
            ));
        }
    };

    match rbac::check(cfg, cn, action) {
        RbacResult::Allowed => Ok(()),
        RbacResult::Denied { caller_cn, action } => Err((
            StatusCode::FORBIDDEN,
            Json(json!({
                "error": format!("Caller '{}' is not authorized for action '{}'", caller_cn, action),
                "code": "EMAS01"
            })),
        )),
        RbacResult::UnknownCaller { cn } => Err((
            StatusCode::FORBIDDEN,
            Json(json!({
                "error": format!("No role configured for caller '{}'", cn),
                "code": "EMAS02"
            })),
        )),
    }
}

/// Append a timestamped entry to the action log (keeps last 50).
pub fn push_log(log: &ActionLog, msg: impl Into<String>) {
    if let Ok(mut guard) = log.lock() {
        guard.push_front(format!(
            "[{}] {}",
            chrono::Utc::now().format("%H:%M:%S"),
            msg.into()
        ));
        if guard.len() > 50 {
            guard.pop_back();
        }
    }
}

// ── Handlers ─────────────────────────────────────────────────────────────────

/// GET /health — public (no RBAC)
pub async fn health(State(state): State<AppState>) -> Json<Value> {
    let services = state.registry.list();
    Json(json!({
        "status": "ok",
        "service": "RuneCore_Marshal",
        "version": env!("CARGO_PKG_VERSION"),
        "managed_components": services.len(),
        "timestamp": chrono::Utc::now().to_rfc3339(),
    }))
}

/// GET / — local plain-HTTP status endpoint (no TLS, no RBAC, localhost-only)
/// Used by the tray status window.
pub async fn local_status(State(state): State<AppState>) -> Json<Value> {
    let mut components = state.registry.list();
    // Sort by name for stable display
    components.sort_by(|a, b| a.name.cmp(&b.name));

    let recent_actions: Vec<String> = state
        .action_log
        .lock()
        .map(|g| g.iter().cloned().collect())
        .unwrap_or_default();

    Json(json!({
        "service": "RuneCore_Marshal",
        "version": env!("CARGO_PKG_VERSION"),
        "components": components,
        "recent_actions": recent_actions,
    }))
}

/// POST /api/setup — declarative setup spec
pub async fn post_setup(
    State(state): State<AppState>,
    axum::Extension(caller): axum::Extension<CallerCn>,
    Json(req): Json<SetupRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    rbac_check(&state.config, &caller.0, "setup")?;

    let caller_cn = caller.0.as_deref().unwrap_or("unknown");
    push_log(&state.action_log, format!("setup request from {}", caller_cn));

    let response = setup::execute(req, &state.config, &state.registry).await;

    let n = response.actions_taken.len();
    let errs = response.errors.len();
    push_log(
        &state.action_log,
        format!("setup done: {} action(s), {} error(s)", n, errs),
    );

    Ok(Json(serde_json::to_value(&response).unwrap_or_default()))
}

/// GET /api/services — list all tracked components
pub async fn list_services(
    State(state): State<AppState>,
    axum::Extension(caller): axum::Extension<CallerCn>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    rbac_check(&state.config, &caller.0, "service.status")?;

    let components = state.registry.list();
    Ok(Json(json!({"components": components})))
}

/// GET /api/services/:name/status
pub async fn get_service_status(
    State(state): State<AppState>,
    axum::Extension(caller): axum::Extension<CallerCn>,
    Path(name): Path<String>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    rbac_check(&state.config, &caller.0, "service.status")?;

    // Check registry first, then query OS
    if let Some(entry) = state.registry.get(&name) {
        return Ok(Json(serde_json::to_value(&entry).unwrap_or_default()));
    }

    // Fall back to live OS query
    let status = svc::get_status(&name).await;
    Ok(Json(serde_json::to_value(&status).unwrap_or_default()))
}

/// POST /api/services/:name/ensure
pub async fn ensure_service(
    State(state): State<AppState>,
    axum::Extension(caller): axum::Extension<CallerCn>,
    Path(name): Path<String>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    rbac_check(&state.config, &caller.0, "service.ensure")?;

    // Special case: sentinel
    if name == "sentinel" {
        push_log(&state.action_log, "ensure: sentinel");
        let result = crate::actions::sentinel::ensure(&state.config).await;
        push_log(
            &state.action_log,
            format!(
                "sentinel -> {}{}",
                result.outcome,
                result.error.as_ref().map(|e| format!(": {}", e.detail)).unwrap_or_default()
            ),
        );
        return Ok(Json(serde_json::to_value(&result).unwrap_or_default()));
    }

    // Generic Windows service start
    push_log(&state.action_log, format!("ensure: {}", name));
    match svc::start_service(&name).await {
        Ok(_) => {
            push_log(&state.action_log, format!("{} -> started", name));
            Ok(Json(json!({"component": name, "outcome": "started"})))
        }
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": e, "code": "EMAA01"})),
        )),
    }
}

/// POST /api/services/:name/stop
pub async fn stop_service(
    State(state): State<AppState>,
    axum::Extension(caller): axum::Extension<CallerCn>,
    Path(name): Path<String>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    rbac_check(&state.config, &caller.0, "service.stop")?;

    // Check if it's a Docker container first
    let docker = &state.config.paths.docker_exe;
    let container_status = crate::actions::docker::container_status(docker, &name).await;
    if container_status != "not_found" {
        match crate::actions::docker::stop_container(docker, &name).await {
            Ok(_) => {
                push_log(&state.action_log, format!("{} -> stopped (docker)", name));
                return Ok(Json(json!({"component": name, "outcome": "stopped"})));
            }
            Err(e) => return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"error": e, "code": "EMAA02"})),
            )),
        }
    }

    // Otherwise treat as Windows service
    push_log(&state.action_log, format!("stop: {}", name));
    match svc::stop_service(&name).await {
        Ok(_) => {
            push_log(&state.action_log, format!("{} -> stopped", name));
            Ok(Json(json!({"component": name, "outcome": "stopped"})))
        }
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": e, "code": "EMAA01"})),
        )),
    }
}
