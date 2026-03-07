use axum::{
    body::Body,
    extract::{Path as AxumPath, State},
    http::{Method, StatusCode, HeaderMap},
    response::{IntoResponse, Response},
};

use crate::AppState;
use crate::db;

/// Build a reqwest client for outbound proxy calls.
///
/// When the target URL uses https://, this client presents Core's server
/// certificate as the mTLS client identity and only trusts certificates
/// signed by our own CA.
///
/// When the target URL uses plain http://, TLS is not involved and the
/// client behaves as a standard HTTP client — so modules running plain
/// HTTP inside Docker work without any changes.
///
/// This should be called once at startup and stored in AppState.
/// Building the client is expensive (PBKDF2 key derivation + TLS config),
/// so it must not be called per-request.
pub fn build_proxy_client(data_dir: &str, passphrase: &str) -> Result<reqwest::Client, String> {
    use rustls::{Certificate, ClientConfig, PrivateKey};
    use rustls_pemfile::{certs, read_one, Item};

    // CA cert — used to verify TLS certificates presented by downstream modules
    let ca_cert_path = std::path::Path::new(data_dir).join("ca_cert.pem");
    let ca_cert_pem = std::fs::read(&ca_cert_path)
        .map_err(|e| format!("read ca cert: {}", e))?;

    let mut root_store = rustls::RootCertStore::empty();
    let ca_der = certs(&mut std::io::Cursor::new(&ca_cert_pem))
        .map_err(|e| format!("parse ca cert: {}", e))?;
    root_store.add_parsable_certificates(&ca_der);

    // Core's own server cert + key — presented as the client identity
    // when connecting to modules over mTLS
    let (cert_pem, key_pem) = crate::ca::get_server_cert_and_key_pem(data_dir, passphrase)
        .map_err(|e| format!("load server cert/key: {}", e))?;

    let client_certs: Vec<Certificate> = certs(&mut std::io::Cursor::new(&cert_pem))
        .map_err(|e| format!("parse server cert: {}", e))?
        .into_iter()
        .map(Certificate)
        .collect();

    let client_key = match read_one(&mut std::io::Cursor::new(&key_pem))
        .map_err(|e| format!("read key: {}", e))?
    {
        Some(Item::PKCS8Key(buf)) | Some(Item::RSAKey(buf)) => PrivateKey(buf),
        _ => return Err("unsupported key format in server_key".into()),
    };

    let tls_config = ClientConfig::builder()
        .with_safe_defaults()
        .with_root_certificates(root_store)
        .with_client_auth_cert(client_certs, client_key)
        .map_err(|e| format!("build tls config: {}", e))?;

    reqwest::Client::builder()
        .use_preconfigured_tls(tls_config)
        .build()
        .map_err(|e| format!("build reqwest client: {}", e))
}

/// HTTP proxy handler — forwards requests to registered services.
///
/// Route: /api/proxy/{service}/*path
///
/// - Looks up the service in the registry by name
/// - Constructs the target URL from the service's rest_url
/// - Forwards the original HTTP method and headers (hop-by-hop headers stripped)
/// - Streams the response body back to the caller without buffering
/// - Uses mTLS when the target URL is https://, plain HTTP otherwise
pub async fn proxy_handler(
    State(state): State<AppState>,
    AxumPath((service_name, path)): AxumPath<(String, String)>,
    method: Method,
    headers: HeaderMap,
    body: Body,
) -> Result<Response<Body>, (StatusCode, String)> {
    tracing::info!("proxy: {} {} -> {}", method, service_name, path);

    // Resolve service from registry
    let service = match db::get_service_by_name(&state.db, &service_name).await {
        Ok(Some(svc)) => svc,
        Ok(None) => {
            tracing::warn!("proxy: service '{}' not registered", service_name);
            return Err((StatusCode::NOT_FOUND, format!("Service '{}' not registered", service_name)));
        }
        Err(e) => {
            tracing::error!("proxy: db error: {}", e);
            return Err((StatusCode::INTERNAL_SERVER_ERROR, format!("db error: {}", e)));
        }
    };

    let ok_status = matches!(service.status.as_str(), "running" | "limb_mode" | "healthy");
    if !ok_status {
        tracing::warn!("proxy: service '{}' is {} — rejecting", service_name, service.status);
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            format!("Service '{}' is currently {}", service_name, service.status),
        ));
    }

    let rest_url = match service.rest_url {
        Some(url) => url,
        None => {
            tracing::warn!("proxy: service '{}' has no rest_url", service_name);
            return Err((StatusCode::BAD_GATEWAY, "Service has no REST URL configured".into()));
        }
    };

    let target_url = if path.is_empty() {
        rest_url.trim_end_matches('/').to_string()
    } else {
        format!("{}/{}", rest_url.trim_end_matches('/'), path.trim_start_matches('/'))
    };

    tracing::debug!("proxy: forwarding {} {}", method, target_url);

    // Use the cached mTLS client from state
    let client = state.proxy_client.clone();

    // Map axum's Method to reqwest's Method
    let req_method = reqwest::Method::from_bytes(method.as_str().as_bytes())
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("method error: {}", e)))?;

    let mut req_builder = client.request(req_method, &target_url);

    // Forward headers — drop hop-by-hop and Host (we reconstruct Host from target URL).
    // Bridge http 1.x (axum) HeaderValue → http 0.2.x (reqwest) HeaderValue via raw bytes.
    for (name, value) in headers.iter() {
        let n = name.as_str().to_lowercase();
        if !is_hop_by_hop_header(&n) && n != "host" {
            if let Ok(v) = reqwest::header::HeaderValue::from_bytes(value.as_bytes()) {
                req_builder = req_builder.header(name.as_str(), v);
            }
        }
    }

    // Read the request body. For most API calls this is a small JSON payload.
    // We use a 16 MB cap to guard against accidental huge uploads.
    let body_bytes = axum::body::to_bytes(body, 16 * 1024 * 1024)
        .await
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("read request body: {}", e)))?;

    req_builder = req_builder.body(body_bytes);

    // Execute the upstream request
    let upstream_resp = req_builder
        .send()
        .await
        .map_err(|e| {
            tracing::error!("proxy: upstream error for {}: {}", target_url, e);
            (StatusCode::BAD_GATEWAY, format!("upstream error: {}", e))
        })?;

    let status = StatusCode::from_u16(upstream_resp.status().as_u16())
        .unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);

    // Build the response, forwarding status and headers
    let mut resp_builder = Response::builder().status(status);

    // Bridge http 0.2.x (reqwest) HeaderValue → http 1.x (axum) HeaderValue via raw bytes.
    for (name, value) in upstream_resp.headers().iter() {
        let n = name.as_str().to_lowercase();
        if !is_hop_by_hop_header(&n) {
            if let Ok(v) = axum::http::HeaderValue::from_bytes(value.as_bytes()) {
                resp_builder = resp_builder.header(name.as_str(), v);
            }
        }
    }

    // Stream the response body directly back to the caller without buffering.
    // This correctly handles server-sent events, ndjson streams (Ollama), and
    // any other streaming response that modules might produce.
    let stream = upstream_resp.bytes_stream();
    let response = resp_builder
        .body(Body::from_stream(stream))
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("build response: {}", e)))?;

    Ok(response)
}

/// Query the service registry by name.
/// Returns availability, URLs, status, and dependency info.
pub async fn query_service(
    State(state): State<AppState>,
    query: axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<axum::Json<serde_json::Value>, (StatusCode, String)> {
    let service_name = match query.get("name") {
        Some(name) => name,
        None => return Err((StatusCode::BAD_REQUEST, "Missing 'name' query parameter".into())),
    };

    let service = match db::get_service_by_name(&state.db, service_name).await {
        Ok(Some(svc)) => svc,
        Ok(None) => {
            return Ok(axum::Json(serde_json::json!({
                "available": false,
                "missing_dependencies": [service_name],
            })));
        }
        Err(e) => {
            tracing::error!("query_service db error: {}", e);
            return Err((StatusCode::INTERNAL_SERVER_ERROR, format!("db error: {}", e)));
        }
    };

    let offline_type = if service.status == "permanently_offline" {
        "permanent"
    } else if service.status.contains("offline") {
        "temporary"
    } else {
        "none"
    };

    Ok(axum::Json(serde_json::json!({
        "name": service.name,
        "rest_url": service.rest_url,
        "ws_url": service.ws_url,
        "status": service.status,
        "last_seen": service.last_seen,
        "dependencies": service.dependencies_list(),
        "wishlist": service.wishlist_list(),
        "available": service.status == "running" || service.status == "limb_mode",
        "offline_type": offline_type,
    })))
}

/// Returns true if the header is hop-by-hop and should not be forwarded.
fn is_hop_by_hop_header(name: &str) -> bool {
    matches!(
        name,
        "connection"
            | "keep-alive"
            | "proxy-authenticate"
            | "proxy-authorization"
            | "te"
            | "trailer"
            | "transfer-encoding"
            | "upgrade"
    )
}
