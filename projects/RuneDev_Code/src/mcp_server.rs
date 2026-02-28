/// MCP stdio server mode (`runecode --mcp-server`).
///
/// Implements the Model Context Protocol (JSON-RPC 2.0 over stdio) so that
/// Claude Code (or any MCP client) can use RuneDev_Code's file-system,
/// shell, search, and git tools without needing the local Ollama LLM.
///
/// Protocol subset implemented:
///   initialize            — handshake, return capabilities
///   notifications/initialized — client acknowledgement (no response)
///   ping                  — keepalive
///   tools/list            — return all tool schemas
///   tools/call            — execute a tool and return the result
use anyhow::Result;
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

use crate::tools;

pub async fn run() -> Result<()> {
    let stdin = tokio::io::stdin();
    let stdout = tokio::io::stdout();
    let mut reader = BufReader::new(stdin);
    let mut writer = stdout;

    let cwd = std::env::current_dir()?;
    let mut line = String::new();

    loop {
        line.clear();
        let n = reader.read_line(&mut line).await?;
        if n == 0 {
            break; // EOF — client disconnected
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let request: Value = match serde_json::from_str(trimmed) {
            Ok(v) => v,
            Err(_) => continue, // ignore malformed input
        };

        let method = request
            .get("method")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let id = request.get("id").cloned();
        let params = request.get("params");

        if let Some(response) = handle(method, params, id, &cwd).await {
            let mut resp_str = serde_json::to_string(&response)?;
            resp_str.push('\n');
            writer.write_all(resp_str.as_bytes()).await?;
            writer.flush().await?;
        }
    }

    Ok(())
}

async fn handle(
    method: &str,
    params: Option<&Value>,
    id: Option<Value>,
    cwd: &std::path::PathBuf,
) -> Option<Value> {
    let id = id.unwrap_or(Value::Null);

    match method {
        // ------------------------------------------------------------------
        // Handshake
        // ------------------------------------------------------------------
        "initialize" => Some(serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "runecode",
                    "version": env!("CARGO_PKG_VERSION")
                }
            }
        })),

        // Notifications have no id — no response expected
        "notifications/initialized" | "notifications/cancelled" => None,

        // ------------------------------------------------------------------
        // Keepalive
        // ------------------------------------------------------------------
        "ping" => Some(serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {}
        })),

        // ------------------------------------------------------------------
        // Tool listing
        // ------------------------------------------------------------------
        "tools/list" => {
            let tools: Vec<Value> = tools::all_tools()
                .iter()
                .map(|t| tools::tool_to_json(t))
                .collect();

            Some(serde_json::json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": { "tools": tools }
            }))
        }

        // ------------------------------------------------------------------
        // Tool execution
        // ------------------------------------------------------------------
        "tools/call" => {
            let params = params?;
            let name = params.get("name")?.as_str()?;
            let args = params
                .get("arguments")
                .cloned()
                .unwrap_or_else(|| Value::Object(Default::default()));

            let (output, is_error) = tools::execute(name, args, cwd).await;

            Some(serde_json::json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": {
                    "content": [
                        { "type": "text", "text": output }
                    ],
                    "isError": is_error
                }
            }))
        }

        // ------------------------------------------------------------------
        // Unknown method
        // ------------------------------------------------------------------
        _ => Some(serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": -32601,
                "message": format!("Method not found: {method}")
            }
        })),
    }
}
