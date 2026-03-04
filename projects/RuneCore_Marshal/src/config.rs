use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub port: u16,
    pub cert_path: String,
    pub key_path: String,
    pub ca_path: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CoreConfig {
    pub url: String,
    pub service_name: String,
    pub core_memory_url: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PathsConfig {
    pub sentinel_binary: String,
    pub sentinel_service: String,
    pub docker_exe: String,
    pub nssm_exe: String,
    pub ollama_base_port: u16,
    pub onnx_service_dir: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RoleConfig {
    pub caller_cn: String,
    pub allowed_actions: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MarshalConfig {
    pub server: ServerConfig,
    pub core: CoreConfig,
    pub paths: PathsConfig,
    #[serde(default)]
    pub roles: Vec<RoleConfig>,
    /// Auto-start Sentinel on Marshal startup (default: true)
    #[serde(default = "default_true")]
    pub auto_start_sentinel: bool,
    /// Local plain-HTTP port for the tray status window (default: 11444)
    #[serde(default = "default_tray_port")]
    pub tray_status_port: u16,
}

fn default_true() -> bool { true }
fn default_tray_port() -> u16 { 11444 }

impl MarshalConfig {
    pub fn load() -> Self {
        // Config file path: env var > working dir > binary dir
        let config_path = std::env::var("MARSHAL_CONFIG")
            .unwrap_or_else(|_| "marshal.toml".to_string());

        let content = fs::read_to_string(&config_path)
            .unwrap_or_else(|_| {
                // Try next to binary
                let exe = std::env::current_exe().unwrap_or_default();
                let sibling = exe.parent().unwrap_or(std::path::Path::new("."))
                    .join("marshal.toml");
                fs::read_to_string(&sibling).unwrap_or_default()
            });

        if content.is_empty() {
            panic!(
                "marshal.toml not found. Set MARSHAL_CONFIG env var or place marshal.toml in working directory."
            );
        }

        toml::from_str(&content).expect("Failed to parse marshal.toml")
    }
}

/// Registration payload for RuneCore_Core service registry
#[derive(Debug, Serialize)]
pub struct ServiceRegistration {
    pub name: String,
    pub version: Option<String>,
    pub rest_url: Option<String>,
    pub ws_url: Option<String>,
    pub public_key_pem: Option<String>,
}

pub async fn register_with_core(cfg: &MarshalConfig) -> Result<(), String> {
    let info = ServiceRegistration {
        name: cfg.core.service_name.clone(),
        version: Some(env!("CARGO_PKG_VERSION").to_string()),
        rest_url: Some(format!("https://127.0.0.1:{}", cfg.server.port)),
        ws_url: None,
        public_key_pem: None,
    };

    let url = format!(
        "{}/api/v1/services/register",
        cfg.core.url.trim_end_matches('/')
    );
    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .map_err(|e: reqwest::Error| e.to_string())?;

    let resp = client.post(&url).json(&info).send().await
        .map_err(|e: reqwest::Error| e.to_string())?;
    if resp.status().is_success() {
        Ok(())
    } else {
        Err(format!("Core registration returned {}", resp.status()))
    }
}
