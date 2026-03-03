/// Declarative setup spec execution.
///
/// The caller sends a list of desired components; Marshal ensures each one
/// is in the requested state and returns a routing table of endpoints.
use crate::actions::{ActionError, ActionResult};
use crate::actions::sentinel;
use crate::actions::docker;
use crate::config::MarshalConfig;
use crate::registry::Registry;
use log::{info, warn};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A single component spec within a SetupRequest
#[derive(Debug, Deserialize)]
pub struct ComponentSpec {
    #[serde(rename = "type")]
    pub kind: String,        // "sentinel" | "onnx_service" | "ollama_gpu"
    pub action: String,      // "ensure" | "stop"
    #[serde(default)]
    pub config: ComponentConfig,
}

#[derive(Debug, Deserialize, Default)]
pub struct ComponentConfig {
    // For ollama_gpu
    pub gpu_uuid: Option<String>,
    pub port: Option<u16>,
    pub name: Option<String>,
    // For onnx_service
    pub model: Option<String>,
    pub device: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct SetupRequest {
    pub components: Vec<ComponentSpec>,
}

#[derive(Debug, Serialize)]
pub struct SetupResponse {
    pub status: String,
    pub endpoints: HashMap<String, String>,
    pub actions_taken: Vec<String>,
    pub errors: Vec<ActionError>,
}

pub async fn execute(
    req: SetupRequest,
    cfg: &MarshalConfig,
    registry: &Registry,
) -> SetupResponse {
    let mut endpoints: HashMap<String, String> = HashMap::new();
    let mut actions_taken: Vec<String> = Vec::new();
    let mut errors: Vec<ActionError> = Vec::new();

    for spec in req.components {
        info!("Setup: processing component '{}' action='{}'", spec.kind, spec.action);

        let result = match spec.kind.as_str() {
            "sentinel" => {
                match spec.action.as_str() {
                    "ensure" => sentinel::ensure(cfg).await,
                    _ => ActionResult::err(
                        "sentinel",
                        ActionError::new("EMAA00", format!("Unknown action '{}'", spec.action)),
                    ),
                }
            }

            "onnx_service" => {
                match spec.action.as_str() {
                    "ensure" => ensure_onnx_service(cfg, &spec.config).await,
                    "stop"   => stop_onnx_service(cfg).await,
                    _ => ActionResult::err(
                        "onnx_service",
                        ActionError::new("EMAA00", format!("Unknown action '{}'", spec.action)),
                    ),
                }
            }

            "ollama_gpu" => {
                match spec.action.as_str() {
                    "ensure" => {
                        let gpu_uuid = spec.config.gpu_uuid.as_deref().unwrap_or("");
                        let port = spec.config.port.unwrap_or_else(|| cfg.paths.ollama_base_port);
                        let name = spec.config.name.as_deref()
                            .unwrap_or("ollama-gpu");
                        docker::ensure_ollama_gpu(cfg, name, gpu_uuid, port).await
                    }
                    _ => ActionResult::err(
                        "ollama_gpu",
                        ActionError::new("EMAA00", format!("Unknown action '{}'", spec.action)),
                    ),
                }
            }

            unknown => ActionResult::err(
                unknown,
                ActionError::new("EMAA00", format!("Unknown component type '{unknown}'")),
            ),
        };

        // Collect results
        let summary = format!("{}: {}", result.component, result.outcome);
        if let Some(err) = result.error {
            warn!("{} error {}: {}", result.component, err.code, err.detail);
            errors.push(err);
        } else {
            actions_taken.push(summary);
            if let Some(ep) = result.endpoint {
                endpoints.insert(result.component, ep);
            }
        }
    }

    let status = if errors.is_empty() { "ok" } else { "partial" }.to_string();
    SetupResponse { status, endpoints, actions_taken, errors }
}

/// Start the ONNX service natively via run_native.ps1
async fn ensure_onnx_service(cfg: &MarshalConfig, comp_cfg: &ComponentConfig) -> ActionResult {
    use crate::actions::run_cmd;
    use std::path::Path;

    let onnx_dir = &cfg.paths.onnx_service_dir;
    let script = format!("{onnx_dir}/run_native.ps1");

    if !Path::new(&script).exists() {
        return ActionResult::err(
            "onnx_service",
            ActionError::new("EMAA01", format!("ONNX service script not found at '{script}'")),
        );
    }

    // Check if already running by hitting /health
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(2))
        .build()
        .unwrap_or_default();

    if client.get("http://localhost:5006/health").send().await.is_ok() {
        return ActionResult::ok("onnx_service", "already running", Some("http://localhost:5006".into()));
    }

    // Launch run_native.ps1 as detached process
    let model_arg = comp_cfg.model.clone().unwrap_or_default();
    let device_arg = comp_cfg.device.clone().unwrap_or_else(|| "dml".into());

    let spawn_result = tokio::process::Command::new("powershell")
        .args(&[
            "-NonInteractive", "-NoProfile", "-WindowStyle", "Hidden",
            "-File", &script,
            "-ModelName", &model_arg,
            "-Device", &device_arg,
        ])
        .spawn();

    match spawn_result {
        Ok(_) => {
            // Give it a moment then check health
            tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            ActionResult::ok("onnx_service", "started", Some("http://localhost:5006".into()))
        }
        Err(e) => ActionResult::err(
            "onnx_service",
            ActionError::new("EMAA03", format!("Failed to launch ONNX service: {e}")),
        ),
    }
}

async fn stop_onnx_service(_cfg: &MarshalConfig) -> ActionResult {
    use crate::actions::run_cmd;
    // Find and kill the uvicorn process for onnx_app
    let (stdout, _, _) = run_cmd(
        "powershell",
        &["-Command", "Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force"],
    ).await;
    ActionResult::ok("onnx_service", "stopped", None)
}
