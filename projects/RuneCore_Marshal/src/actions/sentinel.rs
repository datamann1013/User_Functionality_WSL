/// Ensure the RuneCore Sentinel Windows service is installed and running.
use crate::actions::{ActionError, ActionResult};
use crate::actions::service::{query_service, start_service, install_and_start_service, WinServiceState};
use crate::config::MarshalConfig;
use log::info;
use std::path::Path;

pub async fn ensure(cfg: &MarshalConfig) -> ActionResult {
    let service_name = &cfg.paths.sentinel_service;
    let binary_path  = &cfg.paths.sentinel_binary;
    let nssm_exe     = &cfg.paths.nssm_exe;

    match query_service(service_name).await {
        WinServiceState::Running => {
            info!("Sentinel already running");
            ActionResult::ok("sentinel", "already running", None)
        }

        WinServiceState::Stopped => {
            match start_service(service_name).await {
                Ok(_) => ActionResult::ok("sentinel", "started", None),
                Err(e) => ActionResult::err(
                    "sentinel",
                    ActionError::new("EMAA01", format!("Failed to start Sentinel service: {e}")),
                ),
            }
        }

        WinServiceState::NotFound => {
            // Service not installed — check if binary exists
            if !Path::new(binary_path).exists() {
                return ActionResult::err(
                    "sentinel",
                    ActionError::new(
                        "EMAA01",
                        format!("Sentinel binary not found at '{binary_path}'. Build and deploy Sentinel first."),
                    ),
                );
            }

            // Binary exists — install as service and start
            let app_dir = Path::new(binary_path)
                .parent()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_default();

            match install_and_start_service(nssm_exe, service_name, binary_path, &app_dir).await {
                Ok(_) => ActionResult::ok("sentinel", "installed and started", None),
                Err(e) => ActionResult::err(
                    "sentinel",
                    ActionError::new("EMAA03", format!("Failed to install Sentinel service: {e}")),
                ),
            }
        }

        WinServiceState::Unknown(state) => ActionResult::err(
            "sentinel",
            ActionError::new("EMAA01", format!("Unexpected Sentinel service state: {state}")),
        ),
    }
}
