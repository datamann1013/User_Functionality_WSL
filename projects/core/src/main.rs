use axum::{extract::State, response::Json, routing::{get, post}, Router};
use parking_lot::RwLock;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::{collections::HashMap, net::SocketAddr, sync::Arc, env, fs};

mod ca;

#[derive(Clone)]
struct AppState {
    registry: Arc<RwLock<HashMap<String, ServiceInfo>>>,
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
async fn main() {
    // Initialize CA - require passphrase
    let passphrase = env::var("RUNECORE_CA_PASSPHRASE").unwrap_or_else(|_| {
        eprintln!("Environment variable RUNECORE_CA_PASSPHRASE not set - exiting");
        std::process::exit(1);
    });

    let data_dir = env::var("RUNECORE_DATA_DIR").unwrap_or_else(|_| "./data".to_string());
    fs::create_dir_all(&data_dir).expect("Failed to create data dir");

    ca::init_ca(&data_dir, &passphrase).expect("Failed to initialize CA");

    let state = AppState {
        registry: Arc::new(RwLock::new(HashMap::new())),
    };

    let app = Router::new()
        .route("/", get(root))
        .route("/health", get(health))
        .route("/api/v1/services/register", post(register_service))
        .route("/api/v1/services", get(get_services))
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 11440));
    println!("RuneCore core listening on {}", addr);
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

async fn root() -> &'static str {
    "RuneCore Core - Rust skeleton"
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({"status": "ok"}))
}

async fn register_service(State(state): State<AppState>, Json(payload): Json<ServiceInfo>) -> Json<serde_json::Value> {
    let mut info = payload.clone();
    if info.id.is_empty() {
        // generate random id
        let mut rng = rand::thread_rng();
        let mut b = [0u8; 8];
        rng.fill_bytes(&mut b);
        info.id = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(&b);
    }
    state.registry.write().insert(info.id.clone(), info.clone());
    Json(json!({"ok": true, "service_id": info.id}))
}

async fn get_services(State(state): State<AppState>) -> Json<serde_json::Value> {
    let map = state.registry.read();
    let list: Vec<ServiceInfo> = map.values().cloned().collect();
    Json(json!({"services": list}))
}
