use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use serde_json::{json, Value};
use std::sync::Arc;

use crate::actions::service as svc;
use crate::actions::setup::{self, SetupRequest};
use crate::config::MarshalConfig;
use crate::rbac::{self, RbacResult};
use crate::registry::Registry;

/// Shared application state for Axum handlers
#[derive(Clone)]
pub struct AppState {
    pub config: Arc<MarshalConfig>,
    pub registry: Registry,
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

/// POST /api/setup — declarative setup spec
pub async fn post_setup(
    State(state): State<AppState>,
    axum::Extension(caller): axum::Extension<CallerCn>,
    Json(req): Json<SetupRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    rbac_check(&state.config, &caller.0, "setup")?;

    let response = setup::execute(req, &state.config, &state.registry).await;
    let status = if response.errors.is_empty() { StatusCode::OK } else { StatusCode::MULTI_STATUS };

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
        let result = crate::actions::sentinel::ensure(&state.config).await;
        return Ok(Json(serde_json::to_value(&result).unwrap_or_default()));
    }

    // Generic Windows service start
    match svc::start_service(&name).await {
        Ok(_) => Ok(Json(json!({"component": name, "outcome": "started"}))),
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
            Ok(_) => return Ok(Json(json!({"component": name, "outcome": "stopped"}))),
            Err(e) => return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"error": e, "code": "EMAA02"})),
            )),
        }
    }

    // Otherwise treat as Windows service
    match svc::stop_service(&name).await {
        Ok(_) => Ok(Json(json!({"component": name, "outcome": "stopped"}))),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"error": e, "code": "EMAA01"})),
        )),
    }
}
