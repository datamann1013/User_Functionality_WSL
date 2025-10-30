use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub sampling_interval: u32,
    pub unix_socket_path: String,
    pub windows_pipe_name: String,
    pub core_url: String,
    pub service_name: String,
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

        Config {
            sampling_interval,
            unix_socket_path,
            windows_pipe_name,
            core_url,
            service_name,
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

pub fn register_with_core(cfg: &Config) -> Result<(), String> {
    let info = ServiceInfo {
        name: cfg.service_name.clone(),
        version: Some("0.1.0-alpha".to_string()),
        ws_url: None,
        rest_url: None,
        public_key_pem: None,
    };

    let url = format!("{}/api/v1/services/register", cfg.core_url.trim_end_matches('/'));
    let client = reqwest::blocking::Client::builder().danger_accept_invalid_certs(true).build().map_err(|e| e.to_string())?;
    let resp = client.post(&url).json(&info).send().map_err(|e| e.to_string())?;
    if resp.status().is_success() {
        Ok(())
    } else {
        Err(format!("register returned status {}", resp.status()))
    }
}
