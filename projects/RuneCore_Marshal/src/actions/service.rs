/// Windows service management via sc.exe and NSSM.
use crate::actions::run_cmd;
use log::info;

#[derive(Debug, PartialEq)]
pub enum WinServiceState {
    Running,
    Stopped,
    NotFound,
    Unknown(String),
}

/// Query Windows service state via `sc query <name>`.
pub async fn query_service(name: &str) -> WinServiceState {
    let (stdout, _, _) = run_cmd("sc", &["query", name]).await;
    let upper = stdout.to_uppercase();
    if upper.contains("DOES NOT EXIST") || upper.contains("FAILED 1060") {
        WinServiceState::NotFound
    } else if upper.contains("RUNNING") {
        WinServiceState::Running
    } else if upper.contains("STOPPED") {
        WinServiceState::Stopped
    } else {
        WinServiceState::Unknown(stdout.trim().to_string())
    }
}

/// Start a Windows service that already exists.
pub async fn start_service(name: &str) -> Result<(), String> {
    let (stdout, stderr, ok) = run_cmd("sc", &["start", name]).await;
    if ok {
        info!("Service {} started", name);
        Ok(())
    } else {
        Err(format!("sc start failed: {} {}", stdout.trim(), stderr.trim()))
    }
}

/// Stop a Windows service.
pub async fn stop_service(name: &str) -> Result<(), String> {
    let (stdout, stderr, ok) = run_cmd("sc", &["stop", name]).await;
    if ok || stdout.to_uppercase().contains("STOP_PENDING") || stdout.to_uppercase().contains("STOPPED") {
        info!("Service {} stopped", name);
        Ok(())
    } else {
        Err(format!("sc stop failed: {} {}", stdout.trim(), stderr.trim()))
    }
}

/// Install a binary as a Windows service using NSSM, then start it.
pub async fn install_and_start_service(
    nssm_exe: &str,
    service_name: &str,
    binary_path: &str,
    app_dir: &str,
) -> Result<(), String> {
    // Install
    let (_, _, ok) = run_cmd(nssm_exe, &["install", service_name, binary_path]).await;
    if !ok {
        return Err(format!("NSSM install failed for {service_name}"));
    }
    // Set working directory
    run_cmd(nssm_exe, &["set", service_name, "AppDirectory", app_dir]).await;
    // Auto-start
    run_cmd(nssm_exe, &["set", service_name, "Start", "SERVICE_AUTO_START"]).await;
    // Start
    let (stdout, stderr, ok) = run_cmd(nssm_exe, &["start", service_name]).await;
    if ok {
        info!("Service {} installed and started via NSSM", service_name);
        Ok(())
    } else {
        Err(format!("NSSM start failed: {} {}", stdout.trim(), stderr.trim()))
    }
}

/// Service status for API responses
#[derive(Debug, serde::Serialize)]
pub struct ServiceStatusResponse {
    pub name: String,
    pub status: String,
}

pub async fn get_status(name: &str) -> ServiceStatusResponse {
    let state = query_service(name).await;
    ServiceStatusResponse {
        name: name.to_string(),
        status: match state {
            WinServiceState::Running => "running",
            WinServiceState::Stopped => "stopped",
            WinServiceState::NotFound => "not_found",
            WinServiceState::Unknown(_) => "unknown",
        }.to_string(),
    }
}
