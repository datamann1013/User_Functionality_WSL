use anyhow::{anyhow, Result};
use futures_util::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;

// ---------------------------------------------------------------------------
// Request / response types
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
pub struct AgentRequest {
    pub model: String,
    pub messages: Vec<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<Vec<Value>>,
    pub stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub arguments: Value,
}

#[derive(Debug, Deserialize)]
pub struct AgentResponse {
    pub role: String,
    pub content: Option<String>,
    pub tool_calls: Option<Vec<ToolCall>>,
    pub done: bool,
    /// True when tool calls were promoted from plain-text JSON (no native tool support).
    /// The agent uses this to send tool results as `role:"user"` so the model sees them.
    #[serde(default)]
    pub promoted: bool,
}

#[derive(Debug, Deserialize)]
struct StreamChunk {
    delta: Option<String>,
    done: bool,
    #[allow(dead_code)]
    error: Option<String>,
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

pub struct OllamaClient {
    client: Client,
    base_url: String,
}

impl OllamaClient {
    pub fn new(base_url: String) -> Self {
        OllamaClient {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(300))
                .build()
                .expect("Failed to build HTTP client"),
            base_url,
        }
    }

    /// Query the wrapper for available Ollama models.
    /// Returns Ok(list) on success, Err(message) if the wrapper is unreachable.
    pub async fn available_models(&self) -> Result<Vec<String>> {
        let url = format!("{}/api/models", self.base_url);

        let resp = Client::builder()
            .timeout(std::time::Duration::from_secs(5))
            .build()?
            .get(&url)
            .send()
            .await
            .map_err(|e| anyhow!("AI service unreachable at {}: {e}", self.base_url))?;

        if !resp.status().is_success() {
            return Err(anyhow!("AI service returned {}", resp.status()));
        }

        let data: Value = resp
            .json()
            .await
            .map_err(|e| anyhow!("Could not parse /api/models response: {e}"))?;

        // Wrapper returns either strings or objects — normalize both
        let models = data
            .get("models")
            .and_then(|m| m.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| {
                        if let Some(s) = v.as_str() {
                            Some(s.to_string())
                        } else {
                            v.get("name").and_then(|n| n.as_str()).map(|s| s.to_string())
                        }
                    })
                    .collect()
            })
            .unwrap_or_default();

        Ok(models)
    }

    /// Trigger a model download via the wrapper's /api/pull endpoint.
    /// Returns immediately once the download is initiated (background on the wrapper side).
    pub async fn pull_model(&self, name: &str) -> Result<()> {
        let url = format!("{}/api/pull", self.base_url);

        let resp = Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()?
            .post(&url)
            .json(&serde_json::json!({ "name": name }))
            .send()
            .await
            .map_err(|e| anyhow!("Failed to start download: {e}"))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(anyhow!("Download initiation failed {status}: {body}"));
        }

        Ok(())
    }

    /// Poll the progress of an active model download.
    /// Returns `(status, percent)` where status is "running" | "completed" | "failed".
    /// Returns `("starting", 0)` if the entry isn't visible yet (brief window after kick-off).
    pub async fn poll_pull(&self, name: &str) -> Result<(String, u8)> {
        // Colons are valid in URL path segments; Flask <path:model> handles them fine.
        let url = format!("{}/api/pulls/{}", self.base_url, name);

        let resp = Client::builder()
            .timeout(std::time::Duration::from_secs(5))
            .build()?
            .get(&url)
            .send()
            .await
            .map_err(|e| anyhow!("Poll error: {e}"))?;

        if resp.status().as_u16() == 404 {
            return Ok(("starting".to_string(), 0));
        }

        if !resp.status().is_success() {
            return Err(anyhow!("Poll returned {}", resp.status()));
        }

        let data: Value = resp.json().await.map_err(|e| anyhow!("Poll parse error: {e}"))?;
        let status = data
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();
        let progress = data
            .get("progress")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
            .min(100) as u8;

        Ok((status, progress))
    }

    /// Single-step agent call (non-streaming). Returns a normalized AgentResponse.
    pub async fn agent(&self, req: AgentRequest) -> Result<AgentResponse> {
        let url = format!("{}/api/agent", self.base_url);

        let resp = self
            .client
            .post(&url)
            .json(&req)
            .send()
            .await
            .map_err(|e| anyhow!("Network error calling /api/agent: {e}"))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(anyhow!("/api/agent returned {status}: {body}"));
        }

        resp.json::<AgentResponse>()
            .await
            .map_err(|e| anyhow!("Failed to parse /api/agent response: {e}"))
    }

    /// Streaming agent call. Each text chunk is passed to `on_chunk`.
    /// Uses NDJSON stream from the wrapper (`stream: true`).
    pub async fn agent_stream<F>(&self, req: AgentRequest, mut on_chunk: F) -> Result<()>
    where
        F: FnMut(&str),
    {
        let url = format!("{}/api/agent", self.base_url);

        let resp = self
            .client
            .post(&url)
            .json(&req)
            .send()
            .await
            .map_err(|e| anyhow!("Network error calling /api/agent (stream): {e}"))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(anyhow!("/api/agent stream returned {status}: {body}"));
        }

        let mut byte_stream = resp.bytes_stream();
        let mut buf = String::new();

        while let Some(chunk) = byte_stream.next().await {
            let bytes = chunk.map_err(|e| anyhow!("Stream read error: {e}"))?;
            buf.push_str(&String::from_utf8_lossy(&bytes));

            // Process all complete NDJSON lines in the buffer
            while let Some(nl) = buf.find('\n') {
                let line = buf[..nl].trim().to_string();
                buf = buf[nl + 1..].to_string();

                if line.is_empty() {
                    continue;
                }

                if let Ok(sc) = serde_json::from_str::<StreamChunk>(&line) {
                    if let Some(delta) = &sc.delta {
                        if !delta.is_empty() {
                            on_chunk(delta);
                        }
                    }
                    if sc.done {
                        return Ok(());
                    }
                }
            }
        }

        Ok(())
    }
}
