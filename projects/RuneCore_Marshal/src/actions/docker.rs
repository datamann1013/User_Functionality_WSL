/// Docker container management via docker.exe CLI.
use crate::actions::{ActionError, ActionResult, run_cmd};
use crate::config::MarshalConfig;
use log::info;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct DockerInspectState {
    #[serde(rename = "Status")]
    status: String,
    #[serde(rename = "Running")]
    running: bool,
}

#[derive(Debug, Deserialize)]
struct DockerInspect {
    #[serde(rename = "State")]
    state: DockerInspectState,
}

/// Get container status: "running", "exited", "not_found", or the raw status string.
pub async fn container_status(docker_exe: &str, name: &str) -> String {
    let (stdout, _, ok) = run_cmd(
        docker_exe,
        &["inspect", "--format", "{{json .State}}", name],
    ).await;

    if !ok || stdout.trim().is_empty() {
        return "not_found".to_string();
    }

    match serde_json::from_str::<DockerInspectState>(stdout.trim()) {
        Ok(state) => state.status.to_lowercase(),
        Err(_) => "unknown".to_string(),
    }
}

/// Ensure a container is running. If it doesn't exist, create+start it.
/// If it exists but is stopped, restart it.
///
/// `gpu_uuid`: optional NVIDIA GPU UUID for `--gpus device=<uuid>`
pub async fn ensure_container(
    docker_exe: &str,
    name: &str,
    image: &str,
    port: u16,
    env_vars: &[(&str, &str)],
    gpu_uuid: Option<&str>,
) -> Result<(), String> {
    let status = container_status(docker_exe, name).await;

    if status == "running" {
        info!("Container {} already running", name);
        return Ok(());
    }

    if status == "exited" || status == "stopped" {
        // Restart existing container
        let (_, stderr, ok) = run_cmd(docker_exe, &["start", name]).await;
        return if ok {
            info!("Container {} restarted", name);
            Ok(())
        } else {
            Err(format!("docker start failed: {}", stderr.trim()))
        };
    }

    // Container doesn't exist — create and start it
    let mut args: Vec<String> = vec![
        "run".into(), "-d".into(),
        "--name".into(), name.into(),
        "--restart".into(), "unless-stopped".into(),
        "-p".into(), format!("{port}:{port}"),
    ];

    for (k, v) in env_vars {
        args.push("-e".into());
        args.push(format!("{k}={v}"));
    }

    if let Some(uuid) = gpu_uuid {
        args.push("--gpus".into());
        args.push(format!("device={uuid}"));
    }

    args.push(image.into());

    let args_ref: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    let (stdout, stderr, ok) = run_cmd(docker_exe, &args_ref).await;

    if ok {
        info!("Container {} created and started", name);
        Ok(())
    } else {
        Err(format!("docker run failed: {} {}", stdout.trim(), stderr.trim()))
    }
}

/// Stop and remove a container.
pub async fn stop_container(docker_exe: &str, name: &str) -> Result<(), String> {
    let (_, _, _) = run_cmd(docker_exe, &["stop", name]).await;
    let (_, stderr, ok) = run_cmd(docker_exe, &["rm", name]).await;
    if ok {
        Ok(())
    } else {
        Err(format!("docker rm failed: {}", stderr.trim()))
    }
}

/// Ensure an Ollama container is running on the given port, targeting a specific GPU.
pub async fn ensure_ollama_gpu(
    cfg: &MarshalConfig,
    container_name: &str,
    gpu_uuid: &str,
    port: u16,
) -> ActionResult {
    let docker = &cfg.paths.docker_exe;
    let endpoint = format!("http://localhost:{port}");

    match ensure_container(
        docker,
        container_name,
        "ollama/ollama:latest",
        port,
        &[("OLLAMA_HOST", &format!("0.0.0.0:{port}"))],
        Some(gpu_uuid),
    ).await {
        Ok(_) => ActionResult::ok(container_name, "running", Some(endpoint)),
        Err(e) => ActionResult::err(
            container_name,
            ActionError::new("EMAA02", format!("Docker error: {e}")),
        ),
    }
}
