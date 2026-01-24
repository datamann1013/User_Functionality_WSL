use axum::{
    body::Body,
    extract::{Path as AxumPath, State},
    http::{Request, Response, StatusCode, HeaderMap, HeaderValue},
    response::IntoResponse,
};
use hyper::body::Incoming;
use hyper_util::client::legacy::Client;
use hyper_util::rt::TokioExecutor;
use std::sync::Arc;
use tower::ServiceExt;

use crate::AppState;
use crate::db;

/// HTTP proxy handler that forwards requests to registered services
/// Route: /api/proxy/{service}/*path
pub async fn proxy_handler(
    State(state): State<AppState>,
    AxumPath((service_name, path)): AxumPath<(String, String)>,
    headers: HeaderMap,
    body: Body,
) -> Result<Response<Body>, (StatusCode, String)> {
    tracing::info!("proxy_handler: service={}, path={}", service_name, path);

    // Look up service in registry
    let service = match db::get_service_by_name(&state.db, &service_name).await {
        Ok(Some(svc)) => svc,
        Ok(None) => {
            tracing::warn!("service not found in registry: {}", service_name);
            return Err((StatusCode::NOT_FOUND, format!("Service '{}' not registered", service_name)));
        }
        Err(e) => {
            tracing::error!("database error looking up service: {}", e);
            return Err((StatusCode::INTERNAL_SERVER_ERROR, "Database error".to_string()));
        }
    };

    // Check service status
    if service.status != "running" && service.status != "limb_mode" {
        tracing::warn!("service {} is {}, rejecting proxy request", service_name, service.status);
        return Err((StatusCode::SERVICE_UNAVAILABLE, format!("Service '{}' is {}", service_name, service.status)));
    }

    // Get target URL (rest_url)
    let rest_url = match service.rest_url {
        Some(url) => url,
        None => {
            tracing::warn!("service {} has no rest_url", service_name);
            return Err((StatusCode::BAD_GATEWAY, "Service has no REST URL configured".to_string()));
        }
    };

    // Construct target URL: service_url + /{path}
    let target_url = if path.is_empty() {
        rest_url.trim_end_matches('/').to_string()
    } else {
        format!("{}/{}", rest_url.trim_end_matches('/'), path.trim_start_matches('/'))
    };

    tracing::debug!("proxying to: {}", target_url);

    // Create HTTP client with connection pooling
    let client = Client::builder(TokioExecutor::new()).build_http();

    // Build upstream request
    let uri: hyper::Uri = match target_url.parse() {
        Ok(u) => u,
        Err(e) => {
            tracing::error!("invalid target URL {}: {}", target_url, e);
            return Err((StatusCode::BAD_GATEWAY, "Invalid service URL".to_string()));
        }
    };

    // Convert axum Body to hyper Incoming (streaming)
    let mut req_builder = Request::builder()
        .method(hyper::Method::GET) // TODO: extract method from original request
        .uri(uri);

    // Forward relevant headers (skip hop-by-hop headers)
    for (name, value) in headers.iter() {
        let name_str = name.as_str().to_lowercase();
        if !is_hop_by_hop_header(&name_str) {
            req_builder = req_builder.header(name, value);
        }
    }

    // Convert axum Body to hyper body
    // Note: This is a simplified version - production should handle streaming properly
    let body_bytes = match axum::body::to_bytes(body, usize::MAX).await {
        Ok(b) => b,
        Err(e) => {
            tracing::error!("failed to read request body: {}", e);
            return Err((StatusCode::BAD_REQUEST, "Failed to read request body".to_string()));
        }
    };

    let upstream_req = req_builder
        .body(body_bytes.clone())
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("Failed to build request: {}", e)))?;

    // Send request to upstream service
    let upstream_resp = match client.request(upstream_req).await {
        Ok(resp) => resp,
        Err(e) => {
            tracing::error!("upstream request failed to {}: {}", target_url, e);
            return Err((StatusCode::BAD_GATEWAY, format!("Upstream service error: {}", e)));
        }
    };

    // Convert hyper response to axum response
    let status = upstream_resp.status();
    let headers = upstream_resp.headers().clone();
    let body_bytes = match hyper::body::to_bytes(upstream_resp.into_body()).await {
        Ok(b) => b,
        Err(e) => {
            tracing::error!("failed to read upstream response body: {}", e);
            return Err((StatusCode::BAD_GATEWAY, "Failed to read upstream response".to_string()));
        }
    };

    let mut response = Response::builder().status(status);

    // Forward response headers (skip hop-by-hop)
    for (name, value) in headers.iter() {
        let name_str = name.as_str().to_lowercase();
        if !is_hop_by_hop_header(&name_str) {
            response = response.header(name, value);
        }
    }

    let final_response = response
        .body(Body::from(body_bytes))
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("Failed to build response: {}", e)))?;

    Ok(final_response)
}

/// Check if header is hop-by-hop and should not be forwarded
fn is_hop_by_hop_header(name: &str) -> bool {
    matches!(
        name,
        "connection" | "keep-alive" | "proxy-authenticate" | "proxy-authorization" | 
        "te" | "trailer" | "transfer-encoding" | "upgrade"
    )
}

/// Query service by name
pub async fn query_service(
    State(state): State<AppState>,
    query: axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<axum::Json<serde_json::Value>, (StatusCode, String)> {
    let service_name = match query.get("name") {
        Some(name) => name,
        None => return Err((StatusCode::BAD_REQUEST, "Missing 'name' query parameter".to_string())),
    };

    let service = match db::get_service_by_name(&state.db, service_name).await {
        Ok(Some(svc)) => svc,
        Ok(None) => {
            return Ok(axum::Json(serde_json::json!({
                "available": false,
                "missing_dependencies": vec![service_name],
            })));
        }
        Err(e) => {
            tracing::error!("database error: {}", e);
            return Err((StatusCode::INTERNAL_SERVER_ERROR, "Database error".to_string()));
        }
    };

    // Determine offline_type
    let offline_type = if service.status.contains("offline") {
        if service.status == "permanently_offline" {
            "permanent"
        } else {
            "temporary"
        }
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
        "available": service.status == "running" || service.status == "limb_mode",
        "offline_type": offline_type,
    })))
}
