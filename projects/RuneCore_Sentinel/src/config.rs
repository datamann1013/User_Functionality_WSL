use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Config {
    pub sampling_interval: u32,
    pub unix_socket_path: String,
    pub windows_pipe_name: String,
    pub core_url: String,
    pub service_name: String,
    /// CoreMemory base URL for publishing profiles and telemetry.
    /// Defaults to Core's internal HTTP proxy which forwards to CoreMemory.
    pub core_memory_url: String,
    /// Disk usage percentage at/above which a `sentinel.disk_alert` event fires.
    pub disk_alert_percent: f64,
}

impl Config {
    pub fn from_env() -> Self {
        let sampling_interval = env::var("SENTINEL_SAMPLING_INTERVAL")
            .ok()
            .and_then(|s| s.parse::<u32>().ok())
            .unwrap_or(5);

        let unix_socket_path = env::var("SENTINEL_UNIX_SOCKET")
            .unwrap_or_else(|_| "/var/run/runecore/sentinel.sock".to_string());

        let windows_pipe_name = env::var("SENTINEL_PIPE_NAME").unwrap_or_else(|_| "\\.\\pipe\\runecore-sentinel".to_string());

        let core_url = env::var("RUNECORE_CORE_URL").unwrap_or_else(|_| "https://127.0.0.1:11440".to_string());

        let service_name = env::var("SENTINEL_SERVICE_NAME").unwrap_or_else(|_| "RuneCore_Sentinel".to_string());

        // Port 5010 = CoreMemory FastAPI (host-mapped).
        // Port 11441 = Core internal proxy (container-to-container only, NOT host-mapped).
        let core_memory_url = env::var("SENTINEL_CORE_MEMORY_URL")
            .unwrap_or_else(|_| "http://127.0.0.1:5010".to_string());

        let disk_alert_percent = env::var("SENTINEL_DISK_ALERT_PERCENT")
            .ok()
            .and_then(|s| s.parse::<f64>().ok())
            .unwrap_or(90.0);

        Config {
            sampling_interval,
            unix_socket_path,
            windows_pipe_name,
            core_url,
            service_name,
            core_memory_url,
            disk_alert_percent,
        }
    }
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct ServiceInfo {
    pub name: String,
    pub version: Option<String>,
    pub ws_url: Option<String>,
    pub rest_url: Option<String>,
    pub public_key_pem: Option<String>,
}

/// Whether to skip TLS certificate validation.
///
/// Secure by default (validate certs). Only skips validation when
/// `RUNECORE_DISABLE_MTLS` is set to a truthy value — the project-wide
/// dev opt-out convention (see shared_utils/core_contract.md).
pub fn insecure_tls_enabled() -> bool {
    matches!(
        env::var("RUNECORE_DISABLE_MTLS").ok().as_deref(),
        Some("1") | Some("true") | Some("True")
    )
}

/// Build a blocking reqwest client, gating cert validation behind
/// `RUNECORE_DISABLE_MTLS` (default = secure / validate certs).
fn build_blocking_client() -> Result<reqwest::blocking::Client, String> {
    reqwest::blocking::Client::builder()
        .danger_accept_invalid_certs(insecure_tls_enabled())
        .build()
        .map_err(|e| e.to_string())
}

pub fn register_with_core(cfg: &Config) -> Result<(), String> {
    let info = ServiceInfo {
        name: cfg.service_name.clone(),
        version: Some("0.1.0-alpha".to_string()),
        ws_url: None,
        rest_url: None,
        public_key_pem: None,
    };

    let url = format!("{}/api/v1/services/register", cfg.core_url.trim_end_matches('/'));
    let client = build_blocking_client()?;
    let resp = client.post(&url).json(&info).send().map_err(|e| e.to_string())?;
    if resp.status().is_success() {
        Ok(())
    } else {
        Err(format!("register returned status {}", resp.status()))
    }
}

/// Send a single heartbeat to Core's `/api/v1/services/heartbeat` endpoint.
/// Best-effort: returns Err on any failure; callers log and continue.
pub fn send_heartbeat(cfg: &Config) -> Result<(), String> {
    let hostname = std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .unwrap_or_else(|_| "unknown".to_string());

    let payload = serde_json::json!({
        "name": cfg.service_name,
        "status": "healthy",
        "metadata": {
            "hostname": hostname,
            "service_type": "host_telemetry",
        }
    });

    let url = format!("{}/api/v1/services/heartbeat", cfg.core_url.trim_end_matches('/'));
    let client = build_blocking_client()?;
    let resp = client.post(&url).json(&payload).send().map_err(|e| e.to_string())?;
    if resp.status().is_success() {
        Ok(())
    } else {
        Err(format!("heartbeat returned status {}", resp.status()))
    }
}

/// Heartbeat interval in seconds (env `RUNECORE_HEARTBEAT_INTERVAL`, default 30).
pub fn heartbeat_interval_secs() -> u64 {
    env::var("RUNECORE_HEARTBEAT_INTERVAL")
        .ok()
        .and_then(|s| s.parse::<u64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(30)
}

/// Query core for the CoreMemory service rest_url.
pub fn get_core_memory_url(cfg: &Config) -> Result<String, String> {
    let url = format!("{}/api/v1/services", cfg.core_url.trim_end_matches('/'));
    let client = build_blocking_client()?;
    let resp = client.get(&url).send().map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("core services list returned {}", resp.status()));
    }
    let body: serde_json::Value = resp.json().map_err(|e| e.to_string())?;
    if let Some(arr) = body.get("services").and_then(|v| v.as_array()) {
        for s in arr {
            if let Some(name) = s.get("name").and_then(|n| n.as_str()) {
                if name.to_lowercase().contains("memory") {
                    if let Some(rest) = s.get("rest_url").and_then(|r| r.as_str()) {
                        return Ok(rest.to_string());
                    }
                }
            }
        }
    }
    Err("CoreMemory service not found in core registry".to_string())
}
