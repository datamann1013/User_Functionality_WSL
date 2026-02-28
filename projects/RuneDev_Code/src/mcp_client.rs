/// MCP client — connects to external MCP servers via stdio (JSON-RPC 2.0).
///
/// This lets runecode USE any MCP server that works with Claude Code CLI:
/// Playwright, custom tools, etc. The server is spawned as a subprocess,
/// initialized, and its tools are added to the agent's tool set.
///
/// Tool calls from the LLM that belong to an external server are routed
/// here rather than to the built-in tools module.
use anyhow::{anyhow, Result};
use serde_json::Value;
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};

use crate::config::McpServerConfig;

pub struct McpClient {
    _child: Child,
    stdin: tokio::process::ChildStdin,
    reader: BufReader<tokio::process::ChildStdout>,
    tools: Vec<Value>,
    pub name: String,
    next_id: u64,
}

impl McpClient {
    /// Spawn an MCP server process and complete the initialize handshake.
    pub async fn connect(cfg: &McpServerConfig) -> Result<Self> {
        let mut child = Command::new(&cfg.command)
            .args(&cfg.args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| anyhow!("Failed to spawn MCP server '{}': {e}", cfg.name))?;

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| anyhow!("No stdin on MCP server '{}'", cfg.name))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| anyhow!("No stdout on MCP server '{}'", cfg.name))?;

        let mut client = McpClient {
            _child: child,
            stdin,
            reader: BufReader::new(stdout),
            tools: vec![],
            name: cfg.name.clone(),
            next_id: 1,
        };

        client.initialize().await?;
        client.tools = client.list_tools().await?;

        Ok(client)
    }

    async fn send(&mut self, msg: &Value) -> Result<()> {
        let mut line = serde_json::to_string(msg)?;
        line.push('\n');
        self.stdin.write_all(line.as_bytes()).await?;
        self.stdin.flush().await?;
        Ok(())
    }

    async fn recv_response(&mut self) -> Result<Value> {
        let mut line = String::new();
        loop {
            line.clear();
            let n = self.reader.read_line(&mut line).await?;
            if n == 0 {
                return Err(anyhow!("MCP server '{}' closed stdout", self.name));
            }
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            let msg: Value = serde_json::from_str(trimmed)
                .map_err(|e| anyhow!("Invalid JSON from MCP server '{}': {e}", self.name))?;

            // Skip notifications (they have no 'id')
            if msg.get("id").is_some() {
                return Ok(msg);
            }
        }
    }

    async fn rpc(&mut self, method: &str, params: Value) -> Result<Value> {
        let id = self.next_id;
        self.next_id += 1;

        self.send(&serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params
        }))
        .await?;

        let response = self.recv_response().await?;

        if let Some(err) = response.get("error") {
            return Err(anyhow!("MCP error from '{}': {err}", self.name));
        }

        Ok(response["result"].clone())
    }

    async fn initialize(&mut self) -> Result<()> {
        self.rpc(
            "initialize",
            serde_json::json!({
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "runecode",
                    "version": env!("CARGO_PKG_VERSION")
                }
            }),
        )
        .await?;

        // Acknowledgement notification — no response expected
        self.send(&serde_json::json!({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }))
        .await?;

        Ok(())
    }

    async fn list_tools(&mut self) -> Result<Vec<Value>> {
        let result = self.rpc("tools/list", serde_json::json!({})).await?;
        Ok(result
            .get("tools")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default())
    }

    /// Execute a tool on this server. Returns `(output_text, is_error)`.
    pub async fn call_tool(&mut self, name: &str, args: Value) -> Result<(String, bool)> {
        let result = self
            .rpc(
                "tools/call",
                serde_json::json!({ "name": name, "arguments": args }),
            )
            .await?;

        let is_error = result
            .get("isError")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let text = result
            .get("content")
            .and_then(|c| c.as_array())
            .and_then(|arr| arr.first())
            .and_then(|item| item.get("text"))
            .and_then(|t| t.as_str())
            .unwrap_or("")
            .to_string();

        Ok((text, is_error))
    }

    /// Tool schemas in MCP format, to be sent to the LLM.
    pub fn tool_schemas(&self) -> &[Value] {
        &self.tools
    }

    pub fn tool_count(&self) -> usize {
        self.tools.len()
    }
}

// ---------------------------------------------------------------------------
// Registry — owns all connected MCP clients and routes tool calls
// ---------------------------------------------------------------------------

pub struct McpRegistry {
    clients: Vec<McpClient>,
    /// tool_name → client index
    tool_map: std::collections::HashMap<String, usize>,
}

impl McpRegistry {
    pub fn new(clients: Vec<McpClient>) -> Self {
        let mut tool_map = std::collections::HashMap::new();
        for (i, c) in clients.iter().enumerate() {
            for tool in c.tool_schemas() {
                if let Some(name) = tool.get("name").and_then(|v| v.as_str()) {
                    tool_map.insert(name.to_string(), i);
                }
            }
        }
        McpRegistry { clients, tool_map }
    }

    pub fn is_empty(&self) -> bool {
        self.clients.is_empty()
    }

    /// Returns true if `name` belongs to an external MCP server.
    pub fn owns(&self, name: &str) -> bool {
        self.tool_map.contains_key(name)
    }

    /// Execute a tool on the appropriate MCP server.
    pub async fn execute(&mut self, name: &str, args: Value) -> (String, bool) {
        match self.tool_map.get(name).copied() {
            Some(idx) => match self.clients[idx].call_tool(name, args).await {
                Ok(r) => r,
                Err(e) => (format!("MCP error: {e}"), true),
            },
            None => (format!("No MCP server provides tool: {name}"), true),
        }
    }

    /// All tool schemas from all connected servers (for the LLM tool list).
    pub fn all_schemas(&self) -> Vec<Value> {
        self.clients
            .iter()
            .flat_map(|c| c.tool_schemas().iter().cloned())
            .collect()
    }
}

/// Connect to all configured MCP servers. Failures are non-fatal — a warning
/// is printed and that server is skipped.
pub async fn connect_all(cfgs: &[crate::config::McpServerConfig]) -> McpRegistry {
    if cfgs.is_empty() {
        return McpRegistry::new(vec![]);
    }

    println!("  Connecting to MCP servers...");
    let mut clients = vec![];

    for cfg in cfgs {
        match tokio::time::timeout(
            std::time::Duration::from_secs(10),
            McpClient::connect(cfg),
        )
        .await
        {
            Ok(Ok(c)) => {
                println!(
                    "  \x1b[32m✓\x1b[0m {} ({} tools)",
                    cfg.name,
                    c.tool_count()
                );
                clients.push(c);
            }
            Ok(Err(e)) => {
                println!("  \x1b[33m⚠\x1b[0m {} — {e}", cfg.name);
            }
            Err(_) => {
                println!("  \x1b[33m⚠\x1b[0m {} — timed out", cfg.name);
            }
        }
    }

    McpRegistry::new(clients)
}
