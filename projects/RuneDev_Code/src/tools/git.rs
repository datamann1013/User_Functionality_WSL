use std::path::PathBuf;
use tokio::process::Command;

use super::ToolDef;

pub fn git_status_def() -> ToolDef {
    ToolDef {
        name: "git_status",
        description: "Show the working tree status (git status)",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {},
            "required": []
        }),
    }
}

pub fn git_diff_def() -> ToolDef {
    ToolDef {
        name: "git_diff",
        description: "Show unstaged changes, or staged changes, or diff for a specific file",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional: limit diff to this file path"
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show staged (--cached) diff (default: false)"
                }
            },
            "required": []
        }),
    }
}

pub fn git_log_def() -> ToolDef {
    ToolDef {
        name: "git_log",
        description: "Show recent commit history in one-line format",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show (default: 10)"
                }
            },
            "required": []
        }),
    }
}

async fn run_git_cmd(mut cmd: Command, cwd: &PathBuf) -> (String, bool) {
    cmd.current_dir(cwd);
    match cmd.output().await {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let success = output.status.success();
            let result = if !stdout.is_empty() { stdout } else { stderr };
            (result, !success)
        }
        Err(e) => (format!("Failed to run git: {e}"), true),
    }
}

pub async fn git_status(_args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let mut cmd = Command::new("git");
    cmd.arg("status");
    run_git_cmd(cmd, cwd).await
}

pub async fn git_diff(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let staged = args
        .get("staged")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let path = args
        .get("path")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    let mut cmd = Command::new("git");
    cmd.arg("diff");
    if staged {
        cmd.arg("--staged");
    }
    if !path.is_empty() {
        cmd.arg(&path);
    }

    run_git_cmd(cmd, cwd).await
}

pub async fn git_log(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let count = args
        .get("count")
        .and_then(|v| v.as_u64())
        .unwrap_or(10);

    let mut cmd = Command::new("git");
    cmd.arg("log")
        .arg(format!("-{count}"))
        .arg("--oneline");

    run_git_cmd(cmd, cwd).await
}
