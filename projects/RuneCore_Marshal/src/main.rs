use std::io;
use std::net::SocketAddr;
use std::sync::Arc;

use axum::{middleware::AddExtension, routing::{get, post}, Router};
use axum_server::accept::Accept;
use axum_server::tls_rustls::{RustlsAcceptor, RustlsConfig};
use futures_util::future::BoxFuture;
use log::{info, warn, error};
use tokio::io::{AsyncRead, AsyncWrite};
use tokio_rustls::server::TlsStream;
use tower::Layer;
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
    match register_with_core(&cfg).await {
        Ok(_)  => info!("Registered with RuneCore_Core"),
        Err(e) => warn!("Core registration failed (non-fatal): {}", e),
    }

    // Build TLS config (mTLS — client cert required)
    let server_config = match tls::load_server_tls(
        &cfg.server.cert_path,
        &cfg.server.key_path,
        &cfg.server.ca_path,
    ) {
        Ok(c) => Arc::new(c),
        Err(e) => {
            error!("Failed to load TLS config: {}", e);
            error!("Place marshal.crt, marshal.key, ca.crt in the certs/ directory.");
            std::process::exit(1);
        }
    };

    let rustls_cfg = RustlsConfig::from_config(server_config);

    let registry = Registry::new();
    let state = AppState {
        config: Arc::new(cfg.clone()),
        registry: registry.clone(),
    };

    // Build Axum router — CallerCn injected per-connection by MtlsAcceptor
    let app = Router::new()
        .route("/health", get(api::health))
        .route("/api/setup", post(api::post_setup))
        .route("/api/services", get(api::list_services))
        .route("/api/services/:name/status", get(api::get_service_status))
        .route("/api/services/:name/ensure", post(api::ensure_service))
        .route("/api/services/:name/stop",   post(api::stop_service))
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], cfg.server.port));
    info!("Listening on https://{}", addr);

    let acceptor = MtlsAcceptor::new(RustlsAcceptor::new(rustls_cfg));

    axum_server::bind(addr)
        .acceptor(acceptor)
        .serve(app.into_make_service())
        .await
        .expect("Server failed to start");
}

/// Custom acceptor: performs the TLS handshake, then extracts the client cert CN
/// and injects it as a `CallerCn` extension so RBAC handlers can read it.
#[derive(Clone)]
struct MtlsAcceptor {
    inner: RustlsAcceptor,
}

impl MtlsAcceptor {
    fn new(inner: RustlsAcceptor) -> Self {
        Self { inner }
    }
}

impl<I, S> Accept<I, S> for MtlsAcceptor
where
    I: AsyncRead + AsyncWrite + Unpin + Send + 'static,
    S: Send + 'static,
{
    type Stream = TlsStream<I>;
    type Service = AddExtension<S, CallerCn>;
    type Future = BoxFuture<'static, io::Result<(Self::Stream, Self::Service)>>;

    fn accept(&self, stream: I, service: S) -> Self::Future {
        let acceptor = self.inner.clone();

        Box::pin(async move {
            let (tls_stream, service) = acceptor.accept(stream, service).await?;

            // After the TLS handshake, peer_certificates() gives us the client cert chain
            let server_conn = tls_stream.get_ref().1;
            let cn: Option<String> = server_conn
                .peer_certificates()
                .and_then(|certs| certs.first())
                .and_then(|der| tls::extract_cn_from_der(der.as_ref()));

            let service = axum::Extension(CallerCn(cn)).layer(service);

            Ok((tls_stream, service))
        })
    }
}
