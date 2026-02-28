use crate::config::Config;
use std::io::{self, Write};
use serde_json::Value as JsonValue;
use base64::{engine::general_purpose, Engine as _};

pub fn send_cbor_to_ipc(cfg: &Config, payload: &[u8]) -> io::Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::net::UnixStream;
        let path = &cfg.unix_socket_path;
        // Best-effort: connect and write raw CBOR bytes
        let mut stream = UnixStream::connect(path)?;
        // Optionally prefix length for receiver; here we write length then bytes
        let len = (payload.len() as u32).to_be_bytes();
        stream.write_all(&len)?;
        stream.write_all(payload)?;
        Ok(())
    }

    #[cfg(windows)]
    {
        // Use named_pipe crate on Windows; the crate is optional in Cargo.toml
        // If the named pipe dependency is not available, fall back to an error
        use named_pipe::PipeClient;
        let pipe_name = &cfg.windows_pipe_name;
        // PipeClient expects path like \\\\.\\pipe\\name
        let mut client = PipeClient::connect(pipe_name).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        // Write length prefix then data
        let len = (payload.len() as u32).to_be_bytes();
        client.write_all(&len).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        client.write_all(payload).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        Ok(())
    }

    #[cfg(not(any(unix, windows)))]
    {
        Err(io::Error::new(io::ErrorKind::Other, "unsupported platform for IPC"))
    }
}

/// Attempt to forward the CBOR payload to CoreMemory via HTTP POST as a JSON body.
/// Tries to decode CBOR into a JSON value; if decoding fails, will embed base64 payload in metadata.
pub fn forward_to_core_memory(cfg: &Config, payload: &[u8]) -> io::Result<()> {
    // discover core memory URL
    match crate::config::get_core_memory_url(cfg) {
        Ok(core_mem_url) => {
            // try decode CBOR into JSON
            let maybe_json: Result<JsonValue, _> = serde_cbor::from_slice(payload);
            let body = if let Ok(json_val) = maybe_json {
                serde_json::json!({"text": "sentinel.metrics", "metadata": {"cbor": json_val}})
            } else {
                // fallback: send base64 encoded payload in metadata
                let b64 = general_purpose::STANDARD.encode(payload);
                serde_json::json!({"text": "sentinel.metrics", "metadata": {"cbor_base64": b64}})
            };

            let client = reqwest::blocking::Client::builder().danger_accept_invalid_certs(true).build().map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
            let url = format!("{}/v1/memories", core_mem_url.trim_end_matches('/'));
            let resp = client.post(&url).json(&body).send().map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
            if resp.status().is_success() {
                Ok(())
            } else {
                Err(io::Error::new(io::ErrorKind::Other, format!("core memory forward returned {}", resp.status())))
            }
        }
        Err(e) => Err(io::Error::new(io::ErrorKind::Other, format!("discovery error: {}", e))),
    }
}
