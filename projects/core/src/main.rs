use axum::{extract::State, response::Json, routing::{get, post}, Router};
use serde::{Deserialize, Serialize};
use std::{net::SocketAddr, sync::Arc, env, fs};

mod ca;
mod db;

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

    let pool = db::init_db(&data_dir).await?;

    let state = AppState { db: pool, data_dir: data_dir.clone(), ca_passphrase: passphrase.clone() };

    let app = Router::new()
        .route("/", get(root))
        .route("/health", get(health))
        .route("/api/v1/services/register", post(register_service))
        .route("/api/v1/services", get(get_services))
        .route("/api/v1/pki/sign", post(sign_csr))
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 11440));
    println!("RuneCore core listening on {}", addr);
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();

    Ok(())
}

async fn root() -> &'static str {
    "RuneCore Core - Rust skeleton"
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({"status": "ok"}))
}

async fn register_service(State(state): State<AppState>, Json(payload): Json<ServiceInfo>) -> Json<serde_json::Value> {
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
        return Json(serde_json::json!({"ok": false, "error": format!("db error: {}", e)}));
    }
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
