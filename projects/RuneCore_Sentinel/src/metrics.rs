use serde::{Deserialize, Serialize};
use sysinfo::{CpuExt, System, SystemExt};
use std::time::{SystemTime, UNIX_EPOCH};
use std::process::Command;
use std::str;
use serde_json::Value as JsonValue;

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub ts: u128,
    pub host: String,
    pub cpu_usage: f32,
    /// CPU model/brand string when available (eg. "Intel(R) Core(TM) ...")
    pub cpu_model: Option<String>,
    /// CPU reported base/nominal frequency in MHz when available
    pub cpu_frequency_mhz: Option<u64>,
    /// Per-core frequencies in MHz when available
    pub per_core_frequency_mhz: Option<Vec<u64>>,
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

    // Try to extract CPU model/brand and per-core frequencies
    let cpu_model = sys.cpus().first().and_then(|c| {
        let b = c.brand();
        if b.trim().is_empty() { None } else { Some(b.to_string()) }
    });
    let cpu_frequency_mhz = sys.cpus().first().map(|c| c.frequency() as u64);
    let per_core_frequency_mhz = {
        let freqs: Vec<u64> = sys.cpus().iter().map(|c| c.frequency() as u64).collect();
        if freqs.is_empty() { None } else { Some(freqs) }
    };

    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
    let host = sys.host_name().unwrap_or_else(|| "unknown".to_string());

    SystemMetrics {
        ts,
        host,
        cpu_usage: cpu,
        cpu_model,
        cpu_frequency_mhz,
        per_core_frequency_mhz,
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
    /// Optional device identifier (InstanceId or DeviceID on Windows)
    pub device_id: Option<String>,
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

    // Windows: use PowerShell CIM query (more reliable than legacy wmic) and parse JSON
    if cfg!(target_os = "windows") {
        let ps = r#"Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json"#;
        if let Ok(out) = Command::new("powershell").args(&["-NoProfile","-Command", ps]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        // Could be an array or object
                        if json.is_array() {
                            if let Some(first) = json.as_array().and_then(|a| a.get(0)) {
                                let name = first.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let total_kb = first.get("AdapterRAM").and_then(|v| v.as_u64()).map(|b| b / 1024);
                                return Some(GpuInfo { name, total_memory_kb: total_kb, used_memory_kb: None, utilization_percent: None });
                            }
                        } else if json.is_object() {
                            let name = json.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let total_kb = json.get("AdapterRAM").and_then(|v| v.as_u64()).map(|b| b / 1024);
                            return Some(GpuInfo { name, total_memory_kb: total_kb, used_memory_kb: None, utilization_percent: None });
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

    // Windows: use PowerShell to list PnP devices and CIM entities and search for NPU-like keywords
    if cfg!(target_os = "windows") {
        // First try enumerating PnP devices (Name, FriendlyName, Class)
    // Include InstanceId so we can return a useful device identifier
    let ps_pnp = r#"Get-PnpDevice | Select-Object Name,FriendlyName,Class,InstanceId | ConvertTo-Json"#;
        if let Ok(out) = Command::new("powershell").args(&["-NoProfile","-Command", ps_pnp]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        // Search per-item so we can return the actual device name/friendly name when matched
                        if json.is_array() {
                            for item in json.as_array().unwrap_or(&vec![]) {
                                let name_field = item.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let friendly = item.get("FriendlyName").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let class_field = item.get("Class").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let instance_id = item.get("InstanceId").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let mut hay = String::new();
                                if let Some(ref n) = name_field { hay.push_str(n); hay.push('\n'); }
                                if let Some(ref f) = friendly { hay.push_str(f); hay.push('\n'); }
                                if let Some(ref c) = class_field { hay.push_str(c); hay.push('\n'); }
                                let low = hay.to_lowercase();
                                // Expand keyword list to catch Intel GNA and related captions
                                for kw in &[
                                    "neural processors",
                                    "neural processor",
                                    "neural",
                                    "npu",
                                    "movidius",
                                    "intel neural",
                                    "intel gna",
                                    "gna",
                                    "gna scoring",
                                    "gna scoring accelerator",
                                    "vision",
                                ] {
                                    if low.contains(kw) {
                                        // prefer friendly name then name then class
                                        let dev_name = friendly.clone().or(name_field.clone()).or(class_field.clone()).or(Some(kw.to_string()));
                                        let dev_id = instance_id.clone();
                                        return Some(NpuInfo { name: dev_name, utilization_percent: None, device_id: dev_id });
                                    }
                                }
                            }
                        } else if json.is_object() {
                            let name_field = json.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let friendly = json.get("FriendlyName").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let class_field = json.get("Class").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let mut hay = String::new();
                            if let Some(ref n) = name_field { hay.push_str(n); hay.push('\n'); }
                            if let Some(ref f) = friendly { hay.push_str(f); hay.push('\n'); }
                            if let Some(ref c) = class_field { hay.push_str(c); hay.push('\n'); }
                            let low = hay.to_lowercase();
                            for kw in &[
                                "neural processors",
                                "neural processor",
                                "neural",
                                "npu",
                                "movidius",
                                "intel neural",
                                "gna",
                                "vision",
                            ] {
                                if low.contains(kw) {
                                    let dev_name = friendly.or(name_field).or(class_field).or(Some(kw.to_string()));
                                    return Some(NpuInfo { name: dev_name, utilization_percent: None });
                                }
                            }
                        }
                    }
                }
            }
        }

        // As a fallback, query CIM Win32_PnPEntity for caption/name fields
    // Include DeviceID so we can surface it
    let ps_cim = r#"Get-CimInstance Win32_PnPEntity | Select-Object Name,Caption,DeviceID | ConvertTo-Json"#;
        if let Ok(out) = Command::new("powershell").args(&["-NoProfile","-Command", ps_cim]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        // Search per-item and return the device name/caption when matched
                        if json.is_array() {
                            for item in json.as_array().unwrap_or(&vec![]) {
                                let name_field = item.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let caption = item.get("Caption").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let device_id = item.get("DeviceID").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let mut hay = String::new();
                                if let Some(ref n) = name_field { hay.push_str(n); hay.push('\n'); }
                                if let Some(ref c) = caption { hay.push_str(c); hay.push('\n'); }
                                let low = hay.to_lowercase();
                                for kw in &[
                                    "neural processors",
                                    "neural processor",
                                    "neural",
                                    "npu",
                                    "movidius",
                                    "intel neural",
                                    "intel gna",
                                    "gna",
                                    "gna scoring",
                                    "gna scoring accelerator",
                                    "vision",
                                ] {
                                    if low.contains(kw) {
                                        let dev_name = caption.clone().or(name_field.clone()).or(Some(kw.to_string()));
                                        let dev_id = device_id.clone();
                                        return Some(NpuInfo { name: dev_name, utilization_percent: None, device_id: dev_id });
                                    }
                                }
                            }
                        } else if json.is_object() {
                            let name_field = json.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let caption = json.get("Caption").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let mut hay = String::new();
                            if let Some(ref n) = name_field { hay.push_str(n); hay.push('\n'); }
                            if let Some(ref c) = caption { hay.push_str(c); hay.push('\n'); }
                            let low = hay.to_lowercase();
                            for kw in &[
                                "neural processors",
                                "neural processor",
                                "neural",
                                "npu",
                                "movidius",
                                "intel neural",
                                "gna",
                                "vision",
                            ] {
                                if low.contains(kw) {
                                    let dev_name = caption.or(name_field).or(Some(kw.to_string()));
                                    return Some(NpuInfo { name: dev_name, utilization_percent: None });
                                }
                            }
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
            cpu_model: None,
            cpu_frequency_mhz: None,
            per_core_frequency_mhz: None,
            total_memory: 1024,
            used_memory: 512,
            gpu: None,
            npu: None,
        };
        let bytes = serde_cbor::to_vec(&m).expect("cbor serialize");
        let decoded: SystemMetrics = serde_cbor::from_slice(&bytes).expect("cbor deserialize");
        assert_eq!(decoded.host, "test-host");
        assert_eq!(decoded.total_memory, 1024);
    }
}

