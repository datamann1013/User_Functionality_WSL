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
    /// Path to the native Ollama binary for iGPU service.
    /// If empty, Marshal will search common install locations.
    #[serde(default)]
    pub ollama_native_binary: String,
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
    /// Load and parse marshal.toml. Returns a clear error string instead of
    /// panicking so the caller can exit cleanly (no backtrace) on bad config.
    pub fn load() -> Result<Self, String> {
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
            return Err(
                "marshal.toml not found. Set MARSHAL_CONFIG env var or place marshal.toml in working directory."
                    .to_string(),
            );
        }

        toml::from_str(&content)
            .map_err(|e| format!("Failed to parse marshal.toml: {}", e))
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

/// Heartbeat interval in seconds (env `RUNECORE_HEARTBEAT_INTERVAL`, default 30).
pub fn heartbeat_interval_secs() -> u64 {
    std::env::var("RUNECORE_HEARTBEAT_INTERVAL")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(30)
}

/// Send a single best-effort heartbeat to Core's heartbeat endpoint.
pub async fn send_heartbeat(cfg: &MarshalConfig) -> Result<(), String> {
    let payload = serde_json::json!({
        "name": cfg.core.service_name.clone(),
        "container_name": hostname(),
    });
    let url = format!(
        "{}/api/v1/services/heartbeat",
        cfg.core.url.trim_end_matches('/')
    );
    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .map_err(|e: reqwest::Error| e.to_string())?;
    let resp = client.post(&url).json(&payload).send().await
        .map_err(|e: reqwest::Error| e.to_string())?;
    if resp.status().is_success() {
        Ok(())
    } else {
        Err(format!("heartbeat returned {}", resp.status()))
    }
}

fn hostname() -> String {
    std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .unwrap_or_else(|_| "unknown".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn malformed_toml_is_err_not_panic() {
        // Same deserialization path load() uses — malformed input must yield
        // an Err the caller can handle, never a panic/backtrace.
        let bad = "this is = = not valid toml [[[";
        let parsed: Result<MarshalConfig, _> = toml::from_str(bad);
        assert!(parsed.is_err());
    }

    #[test]
    fn heartbeat_interval_defaults_to_30() {
        std::env::remove_var("RUNECORE_HEARTBEAT_INTERVAL");
        assert_eq!(heartbeat_interval_secs(), 30);
    }
}
