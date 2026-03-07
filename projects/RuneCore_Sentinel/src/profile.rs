/// profile.rs — Publish a static hardware profile to CoreMemory (PostgreSQL memories).
///
/// Called once on startup and refreshed every ~5 minutes. The profile contains
/// slow-changing hardware facts: CPU model, GPU(s), NPU(s), RAM, disks.
/// Stored in namespace "machine_profile" so any ecosystem component can query it.

use log::{info, warn};
use crate::config::Config;
use crate::metrics::SystemMetrics;

pub fn publish_machine_profile(cfg: &Config, metrics: &SystemMetrics) {
    let base_url = cfg.core_memory_url.trim_end_matches('/');
    let url = format!("{}/v1/memories", base_url);

    let body = build_profile_body(metrics);

    let client = match reqwest::blocking::Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(std::time::Duration::from_secs(10))
        .build()
    {
        Ok(c) => c,
        Err(e) => { warn!("profile: cannot build HTTP client: {}", e); return; }
    };

    match client.post(&url).json(&body).send() {
        Ok(resp) if resp.status().is_success() => {
            info!("machine profile published to CoreMemory");
        }
        Ok(resp) => {
            warn!("machine profile publish returned HTTP {}", resp.status());
        }
        Err(e) => {
            warn!("failed to publish machine profile: {}", e);
        }
    }
}

fn build_profile_body(metrics: &SystemMetrics) -> serde_json::Value {
    let mem_total_gb = metrics.total_memory as f64 / (1024.0 * 1024.0 * 1024.0);

    // Short human-readable summary line for the memory text field
    let cpu_str = metrics.cpu_model.as_deref().unwrap_or("Unknown CPU");
    let gpu_str = metrics.gpu.as_ref()
        .and_then(|g| g.first())
        .and_then(|g| g.name.as_deref())
        .unwrap_or("No GPU");
    let text = format!(
        "Machine profile for {}: {}, {:.0}GB RAM, {}",
        metrics.host, cpu_str, mem_total_gb, gpu_str
    );

    // Build GPU array
    let gpu_arr: serde_json::Value = metrics.gpu.as_ref()
        .map(|gpus| {
            gpus.iter().map(|g| serde_json::json!({
                "name": g.name,
                "vendor": g.vendor,
                "gpu_type": g.gpu_type,
                "total_memory_gb": g.total_memory_kb.map(|kb| kb as f64 / (1024.0 * 1024.0)),
                "driver_version": g.driver_version,
            })).collect::<serde_json::Value>()
        })
        .unwrap_or(serde_json::Value::Array(vec![]));

    // Build NPU array
    let npu_arr: serde_json::Value = metrics.npu.as_ref()
        .map(|npus| {
            npus.iter().map(|n| serde_json::json!({
                "name": n.name,
                "class": n.class,
                "device_id": n.device_id,
            })).collect::<serde_json::Value>()
        })
        .unwrap_or(serde_json::Value::Array(vec![]));

    // Build disk array
    let disk_arr: serde_json::Value = metrics.disks.as_ref()
        .map(|disks| {
            disks.iter().map(|d| serde_json::json!({
                "model": d.model,
                "media_type": d.media_type,
                "size_gb": d.size_gb,
                "interface": d.interface,
            })).collect::<serde_json::Value>()
        })
        .unwrap_or(serde_json::Value::Array(vec![]));

    // Build RAM slot array
    let ram_arr: serde_json::Value = metrics.ram_slots.as_ref()
        .map(|slots| {
            slots.iter().map(|s| serde_json::json!({
                "capacity_gb": s.capacity_gb,
                "speed_mhz": s.speed_mhz,
                "memory_type": s.memory_type,
                "manufacturer": s.manufacturer,
            })).collect::<serde_json::Value>()
        })
        .unwrap_or(serde_json::Value::Array(vec![]));

    // Build network interface array — real host LAN IPs used by RuneMesh_Drop for QR links
    let net_arr: serde_json::Value = metrics.network_interfaces.as_ref()
        .map(|ifaces| {
            ifaces.iter().map(|n| serde_json::json!({
                "name": n.name,
                "ip": n.ip,
            })).collect::<serde_json::Value>()
        })
        .unwrap_or(serde_json::Value::Array(vec![]));

    let metadata = serde_json::json!({
        "schema_version": "1",
        "hostname": metrics.host,
        "platform": std::env::consts::OS,
        "cpu_model": metrics.cpu_model,
        "cpu_cores": metrics.per_core_frequency_mhz.as_ref().map(|v| v.len()),
        "cpu_freq_mhz": metrics.cpu_frequency_mhz,
        "memory_total_gb": (mem_total_gb * 10.0).round() / 10.0,
        "gpu": gpu_arr,
        "npu": npu_arr,
        "disks": disk_arr,
        "ram_slots": ram_arr,
        "network_interfaces": net_arr,
        "sampled_at_ms": metrics.ts,
    });

    serde_json::json!({
        "namespace": "machine_profile",
        "agent_id": metrics.host,
        "text": text,
        "metadata": metadata,
    })
}
