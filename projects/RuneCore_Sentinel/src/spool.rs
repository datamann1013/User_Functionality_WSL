use directories::ProjectDirs;
use std::fs::{self, File};
use std::io::{self, Write, Read};
use std::path::PathBuf;

use crate::config::Config;
use crate::ipc::{send_cbor_to_ipc, forward_to_core_memory};

fn spool_dir() -> io::Result<PathBuf> {
    if let Some(proj) = ProjectDirs::from("org", "RuneCore", "runecore") {
        let dir = proj.data_dir().join("sentinel");
        fs::create_dir_all(&dir)?;
        Ok(dir)
    } else {
        Err(io::Error::new(io::ErrorKind::Other, "failed to determine spool dir"))
    }
}

pub fn write_spool(payload: &[u8]) -> io::Result<PathBuf> {
    let dir = spool_dir()?;
    let filename = format!("{}.cbor", chrono::Utc::now().timestamp_millis());
    let path = dir.join(filename);
    let mut f = File::create(&path)?;
    f.write_all(payload)?;
    Ok(path)
}

pub fn flush_spool(cfg: &Config) -> io::Result<()> {
    let dir = spool_dir()?;
    for entry in fs::read_dir(&dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("cbor") {
            continue;
        }
        // read file
        let mut buf = Vec::new();
        let mut f = File::open(&path)?;
        f.read_to_end(&mut buf)?;

        // try IPC first
        match send_cbor_to_ipc(cfg, &buf) {
            Ok(_) => {
                let _ = fs::remove_file(&path);
                continue;
            }
            Err(_) => {
                // try HTTP forward fallback
                if forward_to_core_memory(cfg, &buf).is_ok() {
                    let _ = fs::remove_file(&path);
                    continue;
                }
            }
        }
    }
    Ok(())
}
