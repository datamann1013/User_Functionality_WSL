// On Windows: run as a GUI-subsystem binary so no console window appears
// when launched detached (startup / tray). Launching from a terminal still
// inherits stdout, so --debug output is still visible.
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use std::time::Duration;
use std::env;
use serde_json;

mod config;
mod install;
mod ipc;
mod metrics;
mod profile;
mod spool;
mod telemetry;
#[cfg(target_os = "windows")]
mod tray;

use config::Config;
use ipc::send_cbor_to_ipc;
use metrics::{collect_static_hardware, sample_system_metrics};
use spool::{write_spool, flush_spool};

use log::{info, warn, error};

const PROFILE_REFRESH_ITERS: u64 = 60;

fn main() {
    env_logger::init();

    let args: Vec<String> = env::args().collect();
    let debug  = args.iter().any(|a| a == "--debug");
    let once   = args.iter().any(|a| a == "--once");
    let delete = args.iter().any(|a| a == "--delete");

    if delete {
        install::self_uninstall();
        return;
    }

    info!("RuneSentry starting");

    let cfg = Config::from_env();
    info!("sampling_interval={}s  core_memory={}", cfg.sampling_interval, cfg.core_memory_url);

    match config::register_with_core(&cfg) {
        Ok(_)  => info!("registered with Core"),
        Err(e) => warn!("Core registration failed: {}", e),
    }

    // Background spool-flush thread
    {
        let cfg_clone = cfg.clone();
        std::thread::spawn(move || loop {
            if let Err(e) = flush_spool(&cfg_clone) {
                error!("spool flush error: {}", e);
            }
            std::thread::sleep(Duration::from_secs(10));
        });
    }

    // ── Collect static hardware ONCE ─────────────────────────────────────────
    // This runs PowerShell probes for GPU model, NPU, disks, RAM slots.
    // It is never called again inside the hot loop.
    info!("collecting static hardware profile…");
    let hw = collect_static_hardware();

    // Publish initial machine profile on startup
    {
        let first = sample_system_metrics(&hw);
        if debug {
            if let Ok(s) = serde_json::to_string_pretty(&first) {
                println!("[DEBUG] initial metrics:\n{}", s);
            }
        }
        profile::publish_machine_profile(&cfg, &first);
    }

    // Windows system tray — only in persistent daemon mode.
    // setup() spawns its own thread with a message pump; returns immediately.
    #[cfg(target_os = "windows")]
    if !once { tray::setup(); }

    // ── Hot loop ─────────────────────────────────────────────────────────────
    // Only fast ops here: sysinfo (no subprocess) + nvidia-smi (hidden window).
    let interval      = Duration::from_secs(cfg.sampling_interval as u64);
    let mut loop_count: u64 = 0;

    loop {
        let metric = sample_system_metrics(&hw);

        if debug {
            match serde_json::to_string_pretty(&metric) {
                Ok(s)  => println!("[DEBUG] metric:\n{}", s),
                Err(e) => println!("[DEBUG] serialize error: {}", e),
            }
        }

        // CBOR → IPC pipe
        match serde_cbor::to_vec(&metric) {
            Ok(payload) => {
                if let Err(e) = send_cbor_to_ipc(&cfg, &payload) {
                    warn!("IPC send failed: {} — spooling", e);
                    if let Err(se) = write_spool(&payload) {
                        error!("spool write failed: {}", se);
                    }
                } else {
                    info!("telemetry sent ({} bytes)", payload.len());
                }
            }
            Err(e) => warn!("CBOR serialize failed: {}", e),
        }

        // HTTP → InfluxDB via CoreMemory proxy
        telemetry::push_host_metrics(&cfg, &metric);

        // Refresh static profile periodically
        loop_count += 1;
        if loop_count % PROFILE_REFRESH_ITERS == 0 {
            profile::publish_machine_profile(&cfg, &metric);
        }

        if once { break; }

        std::thread::sleep(interval);
    }
}
