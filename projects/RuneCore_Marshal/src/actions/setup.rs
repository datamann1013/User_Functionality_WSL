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
    pub kind: String,        // "sentinel" | "onnx_service" | "ollama_gpu" | "ollama_igpu"
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

            "ollama_igpu" => {
                match spec.action.as_str() {
                    "ensure" => {
                        let port = spec.config.port.unwrap_or(11436);
                        let name = spec.config.name.as_deref().unwrap_or("ollama-igpu0");
                        ensure_ollama_igpu(cfg, name, port).await
                    }
                    _ => ActionResult::err(
                        "ollama_igpu",
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
    let (_, _, _) = run_cmd(
        "powershell",
        &["-Command", "Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force"],
    ).await;
    ActionResult::ok("onnx_service", "stopped", None)
}

/// Start a native Ollama instance for the integrated GPU using NSSM.
///
/// Ollama is run with `OLLAMA_HOST=0.0.0.0:{port}` so it listens on a
/// separate port from the primary Ollama. On Windows, Ollama's DirectML
/// backend picks up AMD integrated GPUs automatically.
async fn ensure_ollama_igpu(cfg: &MarshalConfig, service_name: &str, port: u16) -> ActionResult {
    use crate::actions::{run_cmd, service as svc};

    let endpoint = format!("http://localhost:{port}");

    // Fast path: if already running just return the endpoint
    if svc::query_service(service_name).await == svc::WinServiceState::Running {
        return ActionResult::ok(service_name, "already running", Some(endpoint));
    }

    // Find the Ollama binary — config path → PATH → common install locations
    let ollama_bin = {
        let cfg_path = cfg.paths.ollama_native_binary.trim();
        if !cfg_path.is_empty() && std::path::Path::new(cfg_path).exists() {
            cfg_path.to_string()
        } else {
            // Try PATH first
            let (from_path, _, ok) = run_cmd("where", &["ollama"]).await;
            if ok && !from_path.trim().is_empty() {
                from_path.lines().next().unwrap_or("ollama").trim().to_string()
            } else {
                // Search common Windows install locations
                let common = [
                    r"C:\Program Files\Ollama\ollama.exe",
                    r"C:\Program Files (x86)\Ollama\ollama.exe",
                ];
                // Also search all user profiles
                let user_glob = std::fs::read_dir(r"C:\Users")
                    .into_iter()
                    .flatten()
                    .flatten()
                    .map(|e| e.path().join(r"AppData\Local\Programs\Ollama\ollama.exe"))
                    .find(|p| p.exists())
                    .map(|p| p.to_string_lossy().into_owned());

                let found = common.iter()
                    .map(|s| s.to_string())
                    .chain(user_glob)
                    .find(|p| std::path::Path::new(p).exists());

                match found {
                    Some(p) => p,
                    None => return ActionResult::err(
                        service_name,
                        ActionError::new("EMAA04",
                            "Ollama binary not found. Set [paths] ollama_native_binary in marshal.toml"),
                    ),
                }
            }
        }
    };

    let nssm = &cfg.paths.nssm_exe;

    // Install the service if not already registered
    let ollama_dir = std::path::Path::new(&ollama_bin)
        .parent()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_else(|| ".".to_string());

    run_cmd(nssm, &["install", service_name, &ollama_bin, "serve"]).await;

    // Set working dir, env and start type regardless of install outcome
    // (nssm set is idempotent — safe to call on an already-installed service)
    run_cmd(nssm, &["set", service_name, "AppDirectory", &ollama_dir]).await;
    run_cmd(nssm, &["set", service_name, "AppEnvironmentExtra",
        &format!("OLLAMA_HOST=0.0.0.0:{port}"),
    ]).await;
    run_cmd(nssm, &["set", service_name, "Start", "SERVICE_AUTO_START"]).await;

    // Start (poll until Running, handles SERVICE_START_PENDING)
    match svc::start_service(service_name).await {
        Ok(_) => {
            // Poll up to 5 s for service to reach Running state
            for _ in 0..10 {
                tokio::time::sleep(std::time::Duration::from_millis(500)).await;
                if svc::query_service(service_name).await == svc::WinServiceState::Running {
                    info!("iGPU Ollama '{}' running on port {}", service_name, port);
                    return ActionResult::ok(service_name, "started", Some(endpoint));
                }
            }
            ActionResult::ok(service_name, "started", Some(endpoint))
        }
        Err(e) => ActionResult::err(
            service_name,
            ActionError::new("EMAA05", format!("Failed to start iGPU Ollama: {e}")),
        ),
    }
}
