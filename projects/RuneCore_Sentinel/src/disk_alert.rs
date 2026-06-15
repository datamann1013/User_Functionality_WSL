//! disk_alert.rs — Edge-triggered disk-usage threshold events.
//!
//! Each tick we read logical-volume usage (via sysinfo) and, when a volume
//! first crosses `disk_alert_percent`, emit a `sentinel.disk_alert` memory to
//! CoreMemory. The alert is edge-triggered: it fires once on crossing and is
//! re-armed only after usage drops a few points below the threshold
//! (hysteresis), so a near-full disk does not spam an alert every tick.
//!
//! RuneCore_Mind can consume these `sentinel.disk_alert` memories to react
//! (warn the user, suggest cleanup, etc.).

use std::collections::HashSet;

use log::{info, warn};
use sysinfo::{DiskExt, System, SystemExt};

use crate::config::Config;

/// Re-arm margin: a mount must fall this many points below the threshold
/// before it can alert again.
const HYSTERESIS_PCT: f64 = 5.0;

pub struct DiskAlerter {
    threshold: f64,
    /// Mounts currently in the alerted state.
    alerted: HashSet<String>,
    sys: System,
}

impl DiskAlerter {
    pub fn new(threshold_percent: f64) -> Self {
        let mut sys = System::new();
        sys.refresh_disks_list();
        DiskAlerter {
            threshold: threshold_percent,
            alerted: HashSet::new(),
            sys,
        }
    }

    /// Sample disk usage and emit alerts for newly-crossed thresholds.
    pub fn check(&mut self, cfg: &Config, host: &str) {
        self.sys.refresh_disks();
        for disk in self.sys.disks() {
            let total = disk.total_space();
            if total == 0 {
                continue;
            }
            let avail = disk.available_space();
            let used = total.saturating_sub(avail);
            let used_pct = (used as f64 / total as f64) * 100.0;
            let mount = disk.mount_point().to_string_lossy().to_string();

            if used_pct >= self.threshold {
                // insert() returns true only if the mount was not already alerted
                if self.alerted.insert(mount.clone()) {
                    emit_alert(cfg, host, &mount, used_pct, self.threshold, total, avail);
                }
            } else if used_pct < self.threshold - HYSTERESIS_PCT {
                self.alerted.remove(&mount);
            }
        }
    }
}

fn emit_alert(
    cfg: &Config,
    host: &str,
    mount: &str,
    used_pct: f64,
    threshold: f64,
    total: u64,
    avail: u64,
) {
    let body = serde_json::json!({
        "text": "sentinel.disk_alert",
        "metadata": {
            "event": "disk_alert",
            "host": host,
            "mount": mount,
            "used_percent": (used_pct * 10.0).round() / 10.0,
            "threshold_percent": threshold,
            "total_bytes": total,
            "available_bytes": avail,
        }
    });

    let url = format!("{}/v1/memories", cfg.core_memory_url.trim_end_matches('/'));
    let client = match reqwest::blocking::Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(std::time::Duration::from_secs(5))
        .build()
    {
        Ok(c) => c,
        Err(e) => {
            warn!("disk_alert: cannot build HTTP client: {}", e);
            return;
        }
    };

    match client.post(&url).json(&body).send() {
        Ok(resp) if resp.status().is_success() => {
            info!("disk_alert emitted: {} at {:.1}% (>= {:.0}%)", mount, used_pct, threshold);
        }
        Ok(resp) => warn!("disk_alert POST returned HTTP {}", resp.status()),
        Err(e) => warn!("disk_alert POST failed: {}", e),
    }
}
