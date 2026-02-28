/// telemetry.rs — Push live host usage metrics to CoreMemory (InfluxDB).
///
/// Called every loop iteration (same ~5s cadence as regular metrics sampling).
/// Measurement: "host_metrics"
/// Tags: host, platform
/// Fields: cpu_percent, mem_used_gb, mem_total_gb, gpu_N_util_percent, gpu_N_mem_used_gb, gpu_N_mem_total_gb

use log::{debug, warn};
use crate::config::Config;
use crate::metrics::SystemMetrics;

pub fn push_host_metrics(cfg: &Config, metrics: &SystemMetrics) {
    let base_url = cfg.core_memory_url.trim_end_matches('/');
    let url = format!("{}/v1/telemetry/batch", base_url);

    let mem_used_gb = metrics.used_memory as f64 / (1024.0 * 1024.0 * 1024.0);
    let mem_total_gb = metrics.total_memory as f64 / (1024.0 * 1024.0 * 1024.0);

    let mut fields = serde_json::json!({
        "cpu_percent": metrics.cpu_usage as f64,
        "mem_used_gb": (mem_used_gb * 100.0).round() / 100.0,
        "mem_total_gb": (mem_total_gb * 10.0).round() / 10.0,
    });

    // Add per-GPU live stats (utilization and VRAM) indexed by slot number
    if let Some(ref gpus) = metrics.gpu {
        for (i, gpu) in gpus.iter().enumerate() {
            if let Some(util) = gpu.utilization_percent {
                fields[format!("gpu_{}_util_percent", i)] = serde_json::json!(util as f64);
            }
            if let Some(used_kb) = gpu.used_memory_kb {
                let used_gb = (used_kb as f64 / (1024.0 * 1024.0) * 100.0).round() / 100.0;
                fields[format!("gpu_{}_mem_used_gb", i)] = serde_json::json!(used_gb);
            }
            if let Some(total_kb) = gpu.total_memory_kb {
                let total_gb = (total_kb as f64 / (1024.0 * 1024.0) * 10.0).round() / 10.0;
                fields[format!("gpu_{}_mem_total_gb", i)] = serde_json::json!(total_gb);
            }
        }
    }

    let body = serde_json::json!({
        "points": [{
            "measurement": "host_metrics",
            "tags": {
                "host": metrics.host,
                "platform": std::env::consts::OS,
            },
            "fields": fields,
        }]
    });

    let client = match reqwest::blocking::Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(std::time::Duration::from_secs(5))
        .build()
    {
        Ok(c) => c,
        Err(e) => { warn!("telemetry: cannot build HTTP client: {}", e); return; }
    };

    match client.post(&url).json(&body).send() {
        Ok(resp) if resp.status().is_success() => {
            debug!("host metrics pushed to CoreMemory");
        }
        Ok(resp) => {
            warn!("host metrics push returned HTTP {}", resp.status());
        }
        Err(e) => {
            warn!("failed to push host metrics: {}", e);
        }
    }
}
