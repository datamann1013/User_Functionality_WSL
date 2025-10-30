use std::time::Duration;

mod config;
mod ipc;
mod metrics;
mod spool;

use config::Config;
use ipc::send_cbor_to_ipc;
use metrics::sample_system_metrics;
use spool::{write_spool, flush_spool};

use log::{info, warn, error};

fn main() {
    env_logger::init();
    info!("RuneCore Sentinel starting (beta-ready skeleton)");

    let cfg = Config::from_env();
    info!("configuration: sampling_interval={}s", cfg.sampling_interval);

    // Best-effort register with Core
    match config::register_with_core(&cfg) {
        Ok(_) => info!("registered with core"),
        Err(e) => warn!("registration with core failed: {}", e),
    }

    // Spawn a background thread to flush spool periodically
    let cfg_clone = cfg.clone();
    std::thread::spawn(move || loop {
        if let Err(e) = flush_spool(&cfg_clone) {
            error!("spool flush error: {}", e);
        }
        std::thread::sleep(std::time::Duration::from_secs(10));
    });

    // main sampling loop
    let interval = Duration::from_secs(cfg.sampling_interval as u64);
    loop {
        let metric = sample_system_metrics();
        match serde_cbor::to_vec(&metric) {
            Ok(payload) => {
                if let Err(e) = send_cbor_to_ipc(&cfg, &payload) {
                    warn!("failed to send telemetry over IPC: {} - spooling", e);
                    if let Err(spool_err) = write_spool(&payload) {
                        error!("failed to write spool: {}", spool_err);
                    }
                } else {
                    info!("telemetry sent ({} bytes)", payload.len());
                }
            }
            Err(e) => warn!("failed to serialize metric to CBOR: {}", e),
        }

        std::thread::sleep(interval);
    }
}
