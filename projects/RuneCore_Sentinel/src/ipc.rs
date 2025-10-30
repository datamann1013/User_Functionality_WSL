use crate::config::Config;
use std::io::{self, Write};

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
