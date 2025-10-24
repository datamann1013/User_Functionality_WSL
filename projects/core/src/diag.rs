use anyhow::Result;
use std::env;

/// Simple synchronous reporter to ErrorLogger service. Uses `ERRORLOGGER_URL` env var if set,
/// otherwise defaults to `http://host.docker.internal:5001/log` then `http://localhost:5001/log`.
pub fn report_error_sync(message: &str, details: Option<&str>) -> Result<()> {
    let url = env::var("ERRORLOGGER_URL").unwrap_or_else(|_| "http://host.docker.internal:5001/log".to_string());

    let payload = serde_json::json!({
        "service": "runecore_core",
        "level": "error",
        "message": message,
        "details": details.unwrap_or("")
    });

    // Use a blocking client so this can be called from panic hooks or sync contexts.
    let client = reqwest::blocking::Client::new();
    // Try configured URL; if it fails and the URL is the host.docker.internal default, try localhost fallback.
    match client.post(&url).json(&payload).send() {
        Ok(resp) => {
            if resp.status().is_success() {
                Ok(())
            } else {
                // non-fatal; return Ok but include status in error string if caller wants to log
                Ok(())
            }
        }
        Err(e) => {
            // If the default host.docker.internal failed, attempt localhost as fallback
            if url.contains("host.docker.internal") {
                let fallback = "http://localhost:5001/log";
                let _ = client.post(fallback).json(&payload).send();
            }
            // Don't fail the whole application if error logger is unreachable.
            let _ = e;
            Ok(())
        }
    }
}
