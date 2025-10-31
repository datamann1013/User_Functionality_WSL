use serde::{Deserialize, Serialize};
use sysinfo::{CpuExt, System, SystemExt};
use std::time::{SystemTime, UNIX_EPOCH};
use std::process::Command;
use std::str;

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub ts: u128,
    pub host: String,
    pub cpu_usage: f32,
    pub total_memory: u64,
    pub used_memory: u64,
    // Best-effort GPU/NPU detection (may be None on unsupported platforms)
    pub gpu: Option<GpuInfo>,
    pub npu: Option<NpuInfo>,
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
        gpu: detect_gpu(),
        npu: detect_npu(),
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GpuInfo {
    pub name: Option<String>,
    /// total memory in kilobytes if available
    pub total_memory_kb: Option<u64>,
    /// used memory in kilobytes if available
    pub used_memory_kb: Option<u64>,
    /// utilization in percent if available
    pub utilization_percent: Option<f32>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct NpuInfo {
    pub name: Option<String>,
    pub utilization_percent: Option<f32>,
}

fn detect_gpu() -> Option<GpuInfo> {
    // Platform-specific probing. Best-effort: try vendor tools first (nvidia-smi), then fall back
    // to common system probes (lspci, wmic, system_profiler). Return None if nothing found.

    // Try NVIDIA `nvidia-smi` (Linux/Windows if driver installed)
    if let Ok(out) = Command::new("nvidia-smi").args(&["--query-gpu=name,memory.total,memory.used,utilization.gpu","--format=csv,noheader,nounits"]).output() {
        if out.status.success() {
            if let Ok(s) = str::from_utf8(&out.stdout) {
                if let Some(line) = s.lines().next() {
                    let parts: Vec<&str> = line.split(',').map(|p| p.trim()).collect();
                    let name = parts.get(0).map(|s| s.to_string());
                    let total_kb = parts.get(1).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let used_kb = parts.get(2).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let util = parts.get(3).and_then(|v| v.parse::<f32>().ok());
                    return Some(GpuInfo { name, total_memory_kb: total_kb, used_memory_kb: used_kb, utilization_percent: util });
                }
            }
        }
    }

    // Linux: try lspci to fetch a GPU name
    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lspci").arg("-nn").output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    for line in s.lines() {
                        let low = line.to_lowercase();
                        if low.contains("vga") || low.contains("3d") || low.contains("display") {
                            // Use the full line as the name
                            return Some(GpuInfo { name: Some(line.to_string()), total_memory_kb: None, used_memory_kb: None, utilization_percent: None });
                        }
                    }
                }
            }
        }
    }

    // macOS: system_profiler
    if cfg!(target_os = "macos") {
        if let Ok(out) = Command::new("system_profiler").args(&["SPDisplaysDataType","-json"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    // crude parsing: look for 'chipset' or 'model' fields
                    if s.contains("chipset") || s.contains("intel") || s.contains("Apple") || s.contains("AMD") {
                        return Some(GpuInfo { name: Some("macOS GPU".to_string()), total_memory_kb: None, used_memory_kb: None, utilization_percent: None });
                    }
                }
            }
        }
    }

    // Windows: try wmic
    if cfg!(target_os = "windows") {
        if let Ok(out) = Command::new("wmic").args(&["path","win32_VideoController","get","Name,AdapterRAM","/format:csv"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    for line in s.lines() {
                        let line = line.trim();
                        if line.is_empty() { continue; }
                        if line.contains(',') {
                            // CSV form: Node,AdapterRAM,Name
                            let parts: Vec<&str> = line.split(',').collect();
                            if parts.len() >= 3 {
                                let name = parts[2].trim().to_string();
                                // AdapterRAM may be empty
                                let total_kb = parts.get(1).and_then(|v| v.trim().parse::<u64>().ok()).map(|b| b / 1024);
                                return Some(GpuInfo { name: Some(name), total_memory_kb: total_kb, used_memory_kb: None, utilization_percent: None });
                            }
                        }
                    }
                }
            }
        }
    }

    None
}

fn detect_npu() -> Option<NpuInfo> {
    // Very best-effort detection: search system device lists for NPU keywords
    // Linux: check lspci for known NPU keywords
    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lspci").arg("-nn").output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    let low = s.to_lowercase();
                    for kw in &["npu", "neural", "movidius", "ethos", "ascend", "vision"] {
                        if low.contains(kw) {
                            return Some(NpuInfo { name: Some(kw.to_string()), utilization_percent: None });
                        }
                    }
                }
            }
        }
    }

    // Windows: probe wmic/device list for NPU-like keywords
    if cfg!(target_os = "windows") {
        if let Ok(out) = Command::new("wmic").args(&["path","win32_PnPEntity","get","Name","/format:csv"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    let low = s.to_lowercase();
                    for kw in &["npu", "neural", "movidius", "intel neural", "vision"] {
                        if low.contains(kw) {
                            return Some(NpuInfo { name: Some(kw.to_string()), utilization_percent: None });
                        }
                    }
                }
            }
        }
    }

    // macOS: system_profiler may indicate Apple Neural Engine in hardware data
    if cfg!(target_os = "macos") {
        if let Ok(out) = Command::new("system_profiler").args(&["SPHardwareDataType","-json"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if s.to_lowercase().contains("neural") || s.to_lowercase().contains("apple neural") {
                        return Some(NpuInfo { name: Some("Apple Neural Engine".to_string()), utilization_percent: None });
                    }
                }
            }
        }
    }

    None
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

