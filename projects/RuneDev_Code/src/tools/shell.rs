use std::path::PathBuf;
use tokio::process::Command;

use super::ToolDef;

pub fn run_bash_def() -> ToolDef {
    ToolDef {
        name: "run_bash",
        description: "Execute a shell command in the project root and return its output",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "timeout_secs": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30)"
                }
            },
            "required": ["command"]
        }),
    }
}

pub async fn run_bash(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let command = match args.get("command").and_then(|v| v.as_str()) {
        Some(c) => c.to_string(),
        None => return ("Missing required argument: command".to_string(), true),
    };

    // Security guardrail: reject commands matching the denylist (or failing
    // the allowlist) before spawning a shell.
    if let Err(reason) = crate::security::check_command(&command) {
        return (reason, true);
    }

    let timeout_secs = args
        .get("timeout_secs")
        .and_then(|v| v.as_u64())
        .unwrap_or(30);

    let mut cmd = if cfg!(target_os = "windows") {
        let mut c = Command::new("cmd");
        c.args(["/C", &command]);
        c
    } else {
        let mut c = Command::new("sh");
        c.args(["-c", &command]);
        c
    };

    cmd.current_dir(cwd);

    let result = tokio::time::timeout(
        std::time::Duration::from_secs(timeout_secs),
        cmd.output(),
    )
    .await;

    match result {
        Ok(Ok(output)) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let exit_code = output.status.code().unwrap_or(-1);
            let success = output.status.success();

            let mut out = String::new();
            if !stdout.is_empty() {
                out.push_str(&stdout);
            }
            if !stderr.is_empty() {
                if !out.is_empty() {
                    out.push('\n');
                }
                out.push_str(&format!("[stderr]\n{stderr}"));
            }
            if out.is_empty() {
                out = format!("[exit code: {exit_code}]");
            }

            (out, !success)
        }
        Ok(Err(e)) => (format!("Failed to launch command: {e}"), true),
        Err(_) => (format!("Command timed out after {timeout_secs}s"), true),
    }
}
