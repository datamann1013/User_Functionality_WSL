use serde::{Deserialize, Serialize};
use sysinfo::{CpuExt, System, SystemExt};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub ts: u128,
    pub host: String,
    pub cpu_usage: f32,
    pub total_memory: u64,
    pub used_memory: u64,
}

pub fn sample_system_metrics() -> SystemMetrics {
    let mut sys = System::new_all();
    sys.refresh_cpu();
    sys.refresh_memory();

    let cpu = sys.global_cpu_info().cpu_usage();
    let total_mem = sys.total_memory();
    let used_mem = sys.used_memory();

    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
    let host = sys.host_name().unwrap_or_else(|| "unknown".to_string());

    SystemMetrics {
        ts,
        host,
        cpu_usage: cpu,
        total_memory: total_mem,
        used_memory: used_mem,
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serialize_roundtrip_cbor() {
        let m = SystemMetrics {
            ts: 1,
            host: "test-host".to_string(),
            cpu_usage: 12.34,
            total_memory: 1024,
            used_memory: 512,
        };
        let bytes = serde_cbor::to_vec(&m).expect("cbor serialize");
        let decoded: SystemMetrics = serde_cbor::from_slice(&bytes).expect("cbor deserialize");
        assert_eq!(decoded.host, "test-host");
        assert_eq!(decoded.total_memory, 1024);
    }
}

