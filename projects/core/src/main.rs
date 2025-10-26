use axum::{extract::State, response::Json, routing::{get, post}, Router};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::{net::SocketAddr, sync::Arc, env, fs};

mod diag;

mod ca;
mod db;
mod cli;

#[derive(Clone)]
struct AppState {
    db: sqlx::SqlitePool,
    data_dir: String,
    ca_passphrase: String,
}

#[derive(Serialize, Deserialize, Clone)]
struct ServiceInfo {
    id: String,
    name: String,
    version: Option<String>,
    ws_url: Option<String>,
    rest_url: Option<String>,
    public_key_pem: Option<String>,
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

    let state = AppState { db: pool, data_dir: data_dir.clone(), ca_passphrase: passphrase.clone() };

    let app = Router::new()
        .route("/", get(root))
        .route("/health", get(health))
        .route("/api/v1/services/register", post(register_service))
        .route("/api/v1/services", get(get_services))
        .route("/api/v1/pki/sign", post(sign_csr))
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
                <rustls::server::AllowAnyAuthenticatedClient as rustls::server::ClientCertVerifier>::verify_client_cert(&*self.inner, end_entity, intermediates, now)
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

async fn register_service(State(state): State<AppState>, Json(payload): Json<ServiceInfo>) -> Json<serde_json::Value> {
    tracing::info!("register_service handler invoked: name={}", payload.name);
    let mut info = payload.clone();
    if info.id.is_empty() {
        info.id = uuid::Uuid::new_v4().to_string();
    }
    let row = db::ServiceRow {
        id: info.id.clone(),
        name: info.name.clone(),
        version: info.version.clone(),
        ws_url: info.ws_url.clone(),
        rest_url: info.rest_url.clone(),
        public_key_pem: info.public_key_pem.clone(),
    };
    if let Err(e) = db::insert_service(&state.db, &row).await {
        // Report DB insert failure to ErrorLogger for diagnostics
        let _ = diag::report_error_sync(&format!("db insert error: {}", e), None);
        return Json(serde_json::json!({"ok": false, "error": format!("db error: {}", e)}));
    }
    tracing::info!("register_service succeeded: id={}", info.id);
    Json(serde_json::json!({"ok": true, "service_id": info.id}))
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
