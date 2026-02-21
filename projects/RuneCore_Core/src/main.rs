use axum::{extract::State, response::{Json, IntoResponse}, routing::{get, post}, Router, body::Bytes, extract::Path as AxumPath};
use axum::http::HeaderMap;
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::{net::SocketAddr, sync::Arc, env, fs};

mod diag;

mod ca;
mod db;
mod cli;
mod proxy;
mod crl;
mod raft_consensus;
mod raft_network;
mod raft_storage;

#[derive(Clone)]
struct AppState {
    db: sqlx::SqlitePool,
    data_dir: String,
    ca_passphrase: String,
    raft_manager: Option<Arc<parking_lot::Mutex<raft_consensus::RaftManager>>>,
    enable_raft: bool,
    /// mTLS-capable reqwest client for outbound proxy calls.
    /// Built once at startup (PBKDF2 key derivation is expensive).
    proxy_client: reqwest::Client,
}

#[derive(Serialize, Deserialize, Clone)]
struct ServiceInfo {
    id: Option<String>,
    name: String,
    version: Option<String>,
    ws_url: Option<String>,
    rest_url: Option<String>,
    public_key_pem: Option<String>,
    #[serde(default)]
    dependencies: Vec<String>,
    #[serde(default)]
    wishlist: Vec<String>,
    #[serde(default)]
    container_name: Option<String>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // If a subcommand was provided, run it and exit. Otherwise start server.
    if std::env::args().len() > 1 {
        let cli = cli::Cli::parse();
        return cli::run_command(cli).map_err(|e| anyhow::anyhow!(e.to_string()));
    }
    // Load passphrase from file if exists, else env var
    let data_dir = env::var("RUNECORE_DATA_DIR").unwrap_or_else(|_| "./data".to_string());
    fs::create_dir_all(&data_dir).expect("Failed to create data dir");

    let pass_file = std::path::Path::new(&data_dir).join("ca_passphrase.txt");
    let passphrase = if pass_file.exists() {
        fs::read_to_string(pass_file)?.trim().to_string()
    } else {
        env::var("RUNECORE_CA_PASSPHRASE").unwrap_or_else(|_| {
            eprintln!("Environment variable RUNECORE_CA_PASSPHRASE not set and no passphrase file found - exiting");
            std::process::exit(1);
        })
    };

    ca::init_ca(&data_dir, &passphrase).expect("Failed to initialize CA");
    
    // Initialize CRL
    let crl_manager = crl::CrlManager::new(&data_dir);
    crl_manager.init_crl(&passphrase).expect("Failed to initialize CRL");

    // Initialize tracing (configurable through RUST_LOG). Also install a panic hook to send
    // fatal errors to the ErrorLogger service so we can diagnose crashes in containers.
    tracing_subscriber::fmt::init();
    std::panic::set_hook(Box::new(|panic_info| {
        let payload = match panic_info.payload().downcast_ref::<&str>() {
            Some(s) => s.to_string(),
            None => match panic_info.payload().downcast_ref::<String>() {
                Some(s) => s.clone(),
                None => "unknown panic".to_string(),
            },
        };
        let location = if let Some(loc) = panic_info.location() {
            format!("{}:{}", loc.file(), loc.line())
        } else {
            "unknown".to_string()
        };
        let details = format!("panic at {}: {}", location, payload);
        let _ = diag::report_error_sync("panic in runecore_core", Some(&details));
    }));

    let pool = db::init_db(&data_dir).await?;

    // Initialize Raft consensus if enabled
    let enable_raft = env::var("RUNECORE_ENABLE_RAFT").unwrap_or_else(|_| "false".to_string()) == "true";
    let raft_manager = if enable_raft {
        let node_id = env::var("RAFT_NODE_ID")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(1);
        
        // Get storage path from env or use default in data_dir
        let storage_path = env::var("RAFT_STORAGE_PATH")
            .unwrap_or_else(|_| format!("{}/raft_node_{}", data_dir, node_id));
        
        tracing::info!("Initializing Raft consensus for node {} with storage at {}", node_id, storage_path);
        
        match raft_consensus::create_three_node_cluster(node_id, &storage_path) {
            Ok(mut manager) => {
                if let Err(e) = manager.bootstrap_cluster() {
                    tracing::warn!("Failed to bootstrap Raft cluster: {}", e);
                }
                Some(Arc::new(parking_lot::Mutex::new(manager)))
            }
            Err(e) => {
                tracing::error!("Failed to create Raft manager: {}", e);
                None
            }
        }
    } else {
        tracing::info!("Raft consensus disabled, using direct database writes");
        None
    };

    // Build the mTLS proxy client once — avoids re-running PBKDF2 on every request.
    // Falls back to a plain client if cert loading fails (e.g. during first-boot before init).
    let proxy_client = match proxy::build_proxy_client(&data_dir, &passphrase) {
        Ok(client) => {
            tracing::info!("Proxy mTLS client ready");
            client
        }
        Err(e) => {
            tracing::warn!("Could not build mTLS proxy client: {} — falling back to plain HTTP", e);
            reqwest::Client::new()
        }
    };

    let state = AppState {
        db: pool,
        data_dir: data_dir.clone(),
        ca_passphrase: passphrase.clone(),
        raft_manager,
        enable_raft,
        proxy_client,
    };

    let app = Router::new()
        .route("/", get(root))
        .route("/health", get(health))
        .route("/api/v1/services/register", post(register_service))
        .route("/api/v1/services", get(get_services))
        .route("/api/v1/services/query", get(proxy::query_service))
        .route("/api/v1/services/heartbeat", post(heartbeat_service))
        .route("/api/v1/pki/sign", post(sign_csr))
        .route("/api/v1/pki/renew", post(renew_certificate))
        .route("/api/v1/pki/revoke", post(revoke_certificate))
        .route("/api/v1/pki/crl", get(get_crl))
        .route("/api/v1/raft/message", post(raft_message_handler))
        .route("/api/proxy/*path", axum::routing::any(proxy_route_handler))
        .with_state(state);

    // Load server cert & key and start TLS server
    let (cert_pem, key_pem) = ca::get_server_cert_and_key_pem(&data_dir, &passphrase).expect("Failed to load server cert/key");

    // create rustls server config
    use rustls::{Certificate as RustlsCert, PrivateKey};
    use rustls_pemfile::{read_one, Item};

    let mut cert_cursor = std::io::Cursor::new(cert_pem.clone());
    let mut certs: Vec<RustlsCert> = vec![];
    while let Ok(Some(item)) = read_one(&mut cert_cursor) {
        if let Item::X509Certificate(buf) = item {
            certs.push(RustlsCert(buf));
        }
    }

    let mut key_cursor = std::io::Cursor::new(key_pem.clone());
    let key = match read_one(&mut key_cursor).expect("read key") {
        Some(Item::PKCS8Key(buf)) | Some(Item::RSAKey(buf)) => PrivateKey(buf),
        _ => panic!("unsupported key format"),
    };

    // configure mTLS: require client certs signed by our CA
    let ca_cert_pem = std::fs::read_to_string(std::path::Path::new(&data_dir).join("ca_cert.pem")).expect("read ca cert");
    // Parse PEM into DER blobs and add to the root store for client verification
    let mut root_store = rustls::RootCertStore::empty();
    let mut cursor = std::io::Cursor::new(ca_cert_pem.as_bytes());
    let der_certs = rustls_pemfile::certs(&mut cursor).expect("failed to parse ca_cert.pem");
    let added = root_store.add_parsable_certificates(&der_certs);
    tracing::debug!("added {:?} CA certs to root store", added);

    let disable_mtls = std::env::var("RUNECORE_DISABLE_MTLS").unwrap_or_default();
    let builder = rustls::ServerConfig::builder().with_safe_defaults();

    let config = if disable_mtls == "1" || disable_mtls.to_lowercase() == "true" {
        tracing::warn!("mTLS disabled via RUNECORE_DISABLE_MTLS env var (debug only)");
        builder.with_no_client_auth().with_single_cert(certs, key).expect("bad certs/key")
    } else {
        // Wrap the default verifier so we can log client certificate details during verification
        let inner_verifier = rustls::server::AllowAnyAuthenticatedClient::new(root_store);
        struct LoggingVerifier {
            inner: std::sync::Arc<rustls::server::AllowAnyAuthenticatedClient>,
        }
        impl rustls::server::ClientCertVerifier for LoggingVerifier {
            fn offer_client_auth(&self) -> bool {
                self.inner.offer_client_auth()
            }
            fn client_auth_mandatory(&self) -> bool {
                self.inner.client_auth_mandatory()
            }
            fn client_auth_root_subjects(&self) -> &[rustls::DistinguishedName] {
                self.inner.client_auth_root_subjects()
            }
            fn verify_client_cert(&self, end_entity: &rustls::Certificate, intermediates: &[rustls::Certificate], now: std::time::SystemTime) -> Result<rustls::server::ClientCertVerified, rustls::Error> {
                tracing::debug!("verify_client_cert called; end_entity_present={}", !end_entity.0.is_empty());
                // best-effort log of subject
                if !end_entity.0.is_empty() {
                    if let Ok(x) = openssl::x509::X509::from_der(&end_entity.0) {
                        if let Some(entry) = x.subject_name().entries().next() {
                            if let Ok(s) = entry.data().as_utf8() {
                                tracing::debug!("client cert first subject entry = {}", s);
                            }
                        }
                    }
                }

                // Call inner verifier and log result
                let res = <rustls::server::AllowAnyAuthenticatedClient as rustls::server::ClientCertVerifier>::verify_client_cert(&*self.inner, end_entity, intermediates, now);
                match &res {
                    Ok(_) => tracing::debug!("client certificate verification: OK"),
                    Err(e) => tracing::error!("client certificate verification failed: {:?}", e),
                }
                res
            }
        }

        let logging = LoggingVerifier { inner: std::sync::Arc::new(inner_verifier) };
        builder.with_client_cert_verifier(std::sync::Arc::new(logging)).with_single_cert(certs, key).expect("bad certs/key")
    };

    let tls_cfg = std::sync::Arc::new(config);
    // axum_server expects its RustlsConfig type
    let rustls_cfg: axum_server::tls_rustls::RustlsConfig = axum_server::tls_rustls::RustlsConfig::from_config(tls_cfg);
    let addr = SocketAddr::from(([0, 0, 0, 0], 11440));
    println!("RuneCore core listening on https://{}", addr);
    
    // Start Raft network task if enabled
    if let Some(ref raft_mgr) = state.raft_manager {
        let peer_urls = env::var("RAFT_PEER_URLS")
            .unwrap_or_else(|_| "1=http://core_primary:11440,2=http://core_secondary:11441,3=http://runecore_ha:11442".to_string());
        
        let node_id = env::var("RAFT_NODE_ID")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(1);
        
        match raft_network::RaftTransport::new(node_id, &peer_urls) {
            Ok(transport) => {
                let raft_clone = Arc::clone(raft_mgr);
                tokio::spawn(async move {
                    if let Err(e) = raft_network::raft_network_task(raft_clone, transport).await {
                        tracing::error!("Raft network task failed: {}", e);
                    }
                });
                tracing::info!("Raft network task started");
            }
            Err(e) => {
                tracing::error!("Failed to create Raft transport: {}", e);
            }
        }
    }
    
    axum_server::bind_rustls(addr, rustls_cfg)
        .serve(app.into_make_service())
        .await
        .unwrap();

    Ok(())
}

async fn root() -> &'static str {
    "RuneCore Core - Rust skeleton"
}

async fn health() -> Json<serde_json::Value> {
    tracing::info!("health handler invoked");
    Json(serde_json::json!({"status": "ok"}))
}

// Handler for incoming Raft messages from peer nodes
async fn raft_message_handler(
    State(state): State<AppState>,
    body: Bytes,
) -> Json<serde_json::Value> {
    if let Some(ref raft_mgr) = state.raft_manager {
        match raft_network::handle_raft_message(Arc::clone(raft_mgr), body.to_vec()).await {
            Ok(_) => Json(serde_json::json!({"ok": true})),
            Err(e) => {
                tracing::error!("Failed to handle Raft message: {}", e);
                Json(serde_json::json!({"ok": false, "error": e.to_string()}))
            }
        }
    } else {
        Json(serde_json::json!({"ok": false, "error": "Raft not enabled"}))
    }
}

async fn register_service(State(state): State<AppState>, headers: HeaderMap, body: Bytes) -> Json<serde_json::Value> {
    // parse JSON body manually so we can return clearer errors (avoid 415 from extractor)
    tracing::debug!("register_service headers: {:?}", headers);
        let content_type = headers.get("content-type").and_then(|v| v.to_str().ok()).unwrap_or(""); // Allow for missing Content-Type
    tracing::debug!("register_service content-type: {}", content_type);
    tracing::debug!("register_service raw body: {}", String::from_utf8_lossy(&body));
        if !content_type.is_empty() && !content_type.contains("application/json") {
            return Json(serde_json::json!({"ok": false, "error": "Expected request with `Content-Type: application/json` if provided"}));
        }
    let payload_res: Result<ServiceInfo, _> = serde_json::from_slice(&body);
    let payload = match payload_res {
        Ok(p) => p,
        Err(e) => return Json(serde_json::json!({"ok": false, "error": format!("invalid json payload: {}", e)})),
    };
    tracing::info!("register_service handler invoked: name={}", payload.name);
    let mut info = payload.clone();
    if info.id.as_ref().map(|s| s.is_empty()).unwrap_or(true) {
        info.id = Some(uuid::Uuid::new_v4().to_string());
    }

    // Validate dependencies (check for cycles and missing services)
    let dependencies_json = serde_json::to_string(&info.dependencies).unwrap_or_else(|_| "[]".to_string());
    let wishlist_json = serde_json::to_string(&info.wishlist).unwrap_or_else(|_| "[]".to_string());

    // Check each dependency exists in registry
    let mut missing_deps = Vec::new();
    let mut available_deps = Vec::new();
    for dep in &info.dependencies {
        match db::get_service_by_name(&state.db, dep).await {
            Ok(Some(svc)) if svc.status == "running" || svc.status == "limb_mode" => {
                available_deps.push(dep.clone());
            }
            _ => {
                missing_deps.push(dep.clone());
            }
        }
    }

    let row = db::ServiceRow {
        id: info.id.clone().unwrap_or_else(|| uuid::Uuid::new_v4().to_string()),
        name: info.name.clone(),
        version: info.version.clone(),
        ws_url: info.ws_url.clone(),
        rest_url: info.rest_url.clone(),
        public_key_pem: info.public_key_pem.clone(),
        dependencies: dependencies_json.clone(),
        wishlist: wishlist_json.clone(),
        container_name: info.container_name.clone(),
        status: if missing_deps.is_empty() { "running".to_string() } else { "limb_mode".to_string() },
        last_seen: chrono::Utc::now().timestamp(),
        offline_since: None,
    };

    // ─── Raft consensus or direct DB write ───────────────────────────────────
    // All raft-related operations (mutex locks, propose) are contained inside a
    // synchronous block expression. No reference to raft_mgr escapes this block,
    // so no !Send type is alive at the .await points below.
    let raft_result: Option<Result<(), anyhow::Error>> = if state.enable_raft {
        if let Some(raft_mgr) = &state.raft_manager {
            // Check leadership; lock is acquired and released within this inner block.
            let (is_leader, leader_id) = {
                let manager = raft_mgr.lock();
                (manager.is_leader(), manager.leader_id())
            };

            if !is_leader {
                tracing::debug!("Not leader, current leader is node {}", leader_id);
                return Json(serde_json::json!({
                    "ok": false,
                    "error": "not_leader",
                    "leader_id": leader_id,
                    "message": "Please retry request with the leader node"
                }));
            }

            let cmd = raft_consensus::RegistryCommand::RegisterService {
                name: info.name.clone(),
                version: info.version.clone(),
                rest_url: info.rest_url.clone(),
                ws_url: info.ws_url.clone(),
                dependencies: info.dependencies.clone(),
                wishlist: info.wishlist.clone(),
                container_name: info.container_name.clone(),
            };

            // Lock is held only for propose(); guard dropped at end of statement.
            // raft_mgr borrow ends at the closing `}` of this block — nothing
            // non-Send escapes into the async continuation below.
            Some(raft_mgr.lock().propose(cmd).map(|_| ()))
        } else {
            None
        }
    } else {
        None
    };

    // Handle raft outcome; .await points below are safe — raft_mgr is out of scope.
    match raft_result {
        Some(Ok(())) => {
            tracing::info!("Service registration proposed via Raft: {}", info.name);
            // Dual-write to local DB during migration to full Raft
            if let Err(e) = db::insert_service(&state.db, &row).await {
                tracing::warn!("Local DB write failed: {}", e);
            }
        }
        Some(Err(e)) => {
            tracing::error!("Raft propose failed: {}", e);
            return Json(serde_json::json!({
                "ok": false,
                "error": format!("raft error: {}", e)
            }));
        }
        None => {
            // Direct database write (Raft disabled)
            if let Err(e) = db::insert_service(&state.db, &row).await {
                let _ = diag::report_error_sync(&format!("db insert error: {}", e), None);
                return Json(serde_json::json!({"ok": false, "error": format!("db error: {}", e)}));
            }
        }
    }

    tracing::info!("register_service succeeded: id={}, status={}", info.id.clone().unwrap_or_default(), row.status);
    
    Json(serde_json::json!({
        "ok": true,
        "registered": true,
        "service_id": info.id,
        "status": row.status,
        "missing_dependencies": missing_deps,
        "available_dependencies": available_deps,
    }))
}

#[derive(Deserialize)]
struct SignCsrRequest {
    csr_pem: String,
    days_valid: Option<u32>,
}

async fn sign_csr(State(state): State<AppState>, Json(payload): Json<SignCsrRequest>) -> Json<serde_json::Value> {
    let days = payload.days_valid.unwrap_or(7);
    match ca::sign_csr(&state.data_dir, &state.ca_passphrase, &payload.csr_pem, days) {
        Ok(cert_pem) => Json(serde_json::json!({"ok": true, "cert_pem": String::from_utf8_lossy(&cert_pem)})),
        Err(e) => Json(serde_json::json!({"ok": false, "error": format!("signing error: {}", e)})),
    }
}

async fn get_services(State(state): State<AppState>) -> Json<serde_json::Value> {
    match db::list_services(&state.db).await {
        Ok(list) => Json(serde_json::json!({"services": list})),
        Err(e) => Json(serde_json::json!({"ok": false, "error": format!("db error: {}", e)})),
    }
}

#[derive(Deserialize)]
struct HeartbeatRequest {
    name: String,
    #[serde(default = "default_status")]
    status: String,
    #[serde(default)]
    metadata: Option<serde_json::Value>,
}

fn default_status() -> String {
    "healthy".to_string()
}

async fn heartbeat_service(State(state): State<AppState>, Json(payload): Json<HeartbeatRequest>) -> Json<serde_json::Value> {
    tracing::debug!("heartbeat from service: {}, status: {}", payload.name, payload.status);
    
    match db::update_service_heartbeat(&state.db, &payload.name, &payload.status).await {
        Ok(_) => Json(serde_json::json!({"ok": true})),
        Err(e) => {
            tracing::error!("failed to update heartbeat for {}: {}", payload.name, e);
            Json(serde_json::json!({"ok": false, "error": format!("db error: {}", e)}))
        }
    }
}

#[derive(Deserialize)]
struct RenewCertRequest {
    service_name: String,
    container_name: String,
    old_serial: String,
    csr_pem: String,
}

async fn renew_certificate(State(state): State<AppState>, Json(payload): Json<RenewCertRequest>) -> Json<serde_json::Value> {
    let cert_registry = crl::CertificateRegistry::new(&state.data_dir);
    
    // Verify container name matches the original certificate
    match cert_registry.verify_renewal(&payload.old_serial, &payload.container_name) {
        Ok(true) => {
            // Container verified, issue new certificate with 7 days validity
            match ca::sign_csr(&state.data_dir, &state.ca_passphrase, &payload.csr_pem, 7) {
                Ok(cert_pem) => {
                    // Extract serial from new certificate and register it
                    let cert_str = String::from_utf8_lossy(&cert_pem);
                    // Register in certificate registry
                    let now = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap()
                        .as_secs() as i64;
                    
                    // Note: In production, extract actual serial from cert
                    // For now, use timestamp as proxy
                    let new_serial = format!("{:x}", now);
                    let _ = cert_registry.register_certificate(
                        &new_serial,
                        &payload.container_name,
                        &payload.service_name,
                        now
                    );
                    
                    tracing::info!("renewed certificate for service {} container {}", 
                        payload.service_name, payload.container_name);
                    
                    Json(serde_json::json!({
                        "ok": true,
                        "cert_pem": cert_str,
                        "expires_in_days": 7
                    }))
                },
                Err(e) => Json(serde_json::json!({
                    "ok": false,
                    "error": format!("signing error: {}", e)
                })),
            }
        },
        Ok(false) => {
            tracing::warn!("renewal denied: container name mismatch for service {} serial {}",
                payload.service_name, payload.old_serial);
            Json(serde_json::json!({
                "ok": false,
                "error": "container name verification failed"
            }))
        },
        Err(e) => Json(serde_json::json!({
            "ok": false,
            "error": format!("verification error: {}", e)
        })),
    }
}

#[derive(Deserialize)]
struct RevokeCertRequest {
    serial: String,
    reason: String,
}

async fn revoke_certificate(State(state): State<AppState>, Json(payload): Json<RevokeCertRequest>) -> Json<serde_json::Value> {
    let crl_manager = crl::CrlManager::new(&state.data_dir);
    let cert_registry = crl::CertificateRegistry::new(&state.data_dir);
    
    match crl_manager.revoke_certificate(&state.ca_passphrase, &payload.serial, &payload.reason) {
        Ok(_) => {
            // Mark as revoked in registry
            let _ = cert_registry.mark_revoked(&payload.serial);
            
            tracing::info!("revoked certificate serial {}: {}", payload.serial, payload.reason);
            Json(serde_json::json!({
                "ok": true,
                "revoked": payload.serial
            }))
        },
        Err(e) => Json(serde_json::json!({
            "ok": false,
            "error": format!("revocation error: {}", e)
        })),
    }
}

async fn get_crl(State(state): State<AppState>) -> impl axum::response::IntoResponse {
    let crl_manager = crl::CrlManager::new(&state.data_dir);
    
    match crl_manager.get_crl_pem() {
        Ok(crl_pem) => {
            let mut headers = HeaderMap::new();
            headers.insert(
                axum::http::header::CONTENT_TYPE,
                "application/x-pem-file".parse().unwrap()
            );
            (headers, crl_pem).into_response()
        },
        Err(e) => {
            (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                format!("Failed to read CRL: {}", e)
            ).into_response()
        }
    }
}

// Route handler that extracts service name and path from wildcard route
async fn proxy_route_handler(
    state: State<AppState>,
    req: axum::extract::Request,
) -> impl axum::response::IntoResponse {
    let path = req.uri().path();
    
    // Extract service name and remaining path from /api/proxy/{service}/{path}
    let parts: Vec<&str> = path.trim_start_matches("/api/proxy/").split('/').collect();
    if parts.is_empty() || parts[0].is_empty() {
        return (axum::http::StatusCode::BAD_REQUEST, "Missing service name").into_response();
    }
    
    let service_name = parts[0].to_string();
    let remaining_path = if parts.len() > 1 {
        parts[1..].join("/")
    } else {
        String::new()
    };
    
    tracing::debug!("proxy route: service={}, path={}", service_name, remaining_path);
    
    // Decompose request into method, headers, and body
    let (parts, body) = req.into_parts();
    let method = parts.method;
    let headers = parts.headers;

    // Call proxy handler
    match proxy::proxy_handler(
        state,
        AxumPath((service_name, remaining_path)),
        method,
        headers,
        body,
    ).await {
        Ok(response) => response.into_response(),
        Err((status, msg)) => (status, msg).into_response(),
    }
}

