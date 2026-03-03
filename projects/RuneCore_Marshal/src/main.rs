use std::net::SocketAddr;
use std::sync::Arc;

use axum::{routing::{get, post}, Router};
use axum_server::tls_rustls::RustlsConfig;
use log::{info, warn, error};
use tower_http::trace::TraceLayer;

mod actions;
mod api;
mod config;
mod rbac;
mod registry;
mod tls;

use api::{AppState, CallerCn};
use config::{MarshalConfig, register_with_core};
use registry::Registry;

#[tokio::main]
async fn main() {
    env_logger::init();
    info!("RuneCore_Marshal v{} starting", env!("CARGO_PKG_VERSION"));

    let cfg = MarshalConfig::load();
    info!(
        "Config loaded — port={} cert={} ca={}",
        cfg.server.port, cfg.server.cert_path, cfg.server.ca_path
    );

    // Register with RuneCore_Core (best-effort)
    match register_with_core(&cfg) {
        Ok(_)  => info!("Registered with RuneCore_Core"),
        Err(e) => warn!("Core registration failed (non-fatal): {}", e),
    }

    // Build TLS config (mTLS — client cert required)
    let rustls_cfg = match tls::load_server_tls(
        &cfg.server.cert_path,
        &cfg.server.key_path,
        &cfg.server.ca_path,
    ) {
        Ok(c) => RustlsConfig::from_config(Arc::new(c)),
        Err(e) => {
            error!("Failed to load TLS config: {}", e);
            error!("Place marshal.crt, marshal.key, ca.crt in the certs/ directory.");
            std::process::exit(1);
        }
    };

    let registry = Registry::new();
    let state = AppState {
        config: Arc::new(cfg.clone()),
        registry: registry.clone(),
    };

    // Build Axum router
    let app = Router::new()
        .route("/health", get(api::health))
        .route("/api/setup", post(api::post_setup))
        .route("/api/services", get(api::list_services))
        .route("/api/services/:name/status", get(api::get_service_status))
        .route("/api/services/:name/ensure", post(api::ensure_service))
        .route("/api/services/:name/stop",   post(api::stop_service))
        .layer(TraceLayer::new_for_http())
        .layer(axum::middleware::from_fn_with_state(
            state.clone(),
            extract_caller_cn_middleware,
        ))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], cfg.server.port));
    info!("Listening on https://{}", addr);

    axum_server::bind_rustls(addr, rustls_cfg)
        .serve(app.into_make_service())
        .await
        .expect("Server failed to start");
}

/// Axum middleware: extract client cert CN from TLS connection info
/// and inject as a `CallerCn` extension for RBAC checks.
async fn extract_caller_cn_middleware(
    mut req: axum::http::Request<axum::body::Body>,
    next: axum::middleware::Next,
) -> axum::response::Response {
    // axum-server injects connection info as an extension
    let cn: Option<String> = req
        .extensions()
        .get::<axum_server::tls_rustls::PeerCertificates>()
        .and_then(|certs| certs.first())
        .and_then(|der| tls::extract_cn_from_der(der.as_ref()));

    req.extensions_mut().insert(CallerCn(cn));
    next.run(req).await
}
