pub mod docker;
pub mod sentinel;
pub mod service;
pub mod setup;

use serde::Serialize;

/// Unified error type for all actions
#[derive(Debug, Serialize)]
pub struct ActionError {
    pub code: String,
    pub detail: String,
}

impl ActionError {
    pub fn new(code: impl Into<String>, detail: impl Into<String>) -> Self {
        Self { code: code.into(), detail: detail.into() }
    }
}

/// Result of running any individual action step
#[derive(Debug, Serialize)]
pub struct ActionResult {
    pub component: String,
    pub outcome: String,   // e.g. "already running", "started", "installed and started", "error"
    pub endpoint: Option<String>,
    pub error: Option<ActionError>,
}

impl ActionResult {
    pub fn ok(component: impl Into<String>, outcome: impl Into<String>, endpoint: Option<String>) -> Self {
        Self { component: component.into(), outcome: outcome.into(), endpoint, error: None }
    }

    pub fn err(component: impl Into<String>, error: ActionError) -> Self {
        Self { component: component.into(), outcome: "error".into(), endpoint: None, error: Some(error) }
    }
}

/// Run a shell command and return (stdout, stderr, success).
/// Uses `cmd /C` on Windows for PATH resolution.
pub async fn run_cmd(exe: &str, args: &[&str]) -> (String, String, bool) {
    let output = tokio::process::Command::new(exe)
        .args(args)
        .output()
        .await;

    match output {
        Ok(o) => {
            let stdout = String::from_utf8_lossy(&o.stdout).to_string();
            let stderr = String::from_utf8_lossy(&o.stderr).to_string();
            (stdout, stderr, o.status.success())
        }
        Err(e) => (String::new(), e.to_string(), false),
    }
}
