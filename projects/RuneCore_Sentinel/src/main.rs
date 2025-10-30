use std::time::Duration;

mod config;
mod ipc;
mod metrics;

use config::Config;
use ipc::send_cbor_to_ipc;
use metrics::sample_system_metrics;

use log::{info, warn};

fn main() {
    env_logger::init();
    info!("RuneCore Sentinel starting (alpha skeleton)");

    let cfg = Config::from_env();
    info!("configuration: sampling_interval={}s", cfg.sampling_interval);

    // Best-effort register with Core (non-blocking-ish for now)
    if let Err(e) = config::register_with_core(&cfg) {
        warn!("registration with core failed: {}", e);
    } else {
        info!("registered with core (or registration attempted)");
    }

    // main sampling loop
    let interval = Duration::from_secs(cfg.sampling_interval as u64);
    loop {
        let metric = sample_system_metrics();
        match serde_cbor::to_vec(&metric) {
            Ok(payload) => {
                if let Err(e) = send_cbor_to_ipc(&cfg, &payload) {
                    warn!("failed to send telemetry over IPC: {}", e);
                } else {
                    info!("telemetry sent ({} bytes)", payload.len());
                }
            }
            Err(e) => warn!("failed to serialize metric to CBOR: {}", e),
        }

        std::thread::sleep(interval);
    }
}
