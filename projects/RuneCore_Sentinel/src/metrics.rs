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
    // Collections used so the sentinel can report multiple devices
    pub gpu: Option<Vec<GpuInfo>>,
    pub npu: Option<Vec<NpuInfo>>,
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
    /// vendor or short vendor string when available (eg. "NVIDIA", "Intel", "AMD")
    pub vendor: Option<String>,
    /// total memory in kilobytes if available
    pub total_memory_kb: Option<u64>,
    /// used memory in kilobytes if available
    pub used_memory_kb: Option<u64>,
    /// utilization in percent if available
    pub utilization_percent: Option<f32>,
    /// Optional device identifier (PNP/DeviceID on Windows or lspci id on Linux)
    pub device_id: Option<String>,
    /// Optional driver version string when available
    pub driver_version: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct NpuInfo {
    pub name: Option<String>,
    pub utilization_percent: Option<f32>,
    /// Optional device identifier (InstanceId or DeviceID on Windows)
    pub device_id: Option<String>,
    /// Optional vendor/class hint
    pub class: Option<String>,
}
fn detect_gpu() -> Option<Vec<GpuInfo>> {
    // Platform-specific probing. Best-effort: try vendor tools first (nvidia-smi), then fall back
    // to common system probes (lspci, wmic, system_profiler). Return None if nothing found.

    // Try NVIDIA `nvidia-smi` (Linux/Windows if driver installed)
    if let Ok(out) = Command::new("nvidia-smi").args(&["--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version","--format=csv,noheader,nounits"]).output() {
        if out.status.success() {
            if let Ok(s) = str::from_utf8(&out.stdout) {
                let mut res = Vec::new();
                for line in s.lines() {
                    let parts: Vec<&str> = line.split(',').map(|p| p.trim()).collect();
                    let name = parts.get(0).map(|s| s.to_string());
                    let total_kb = parts.get(1).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let used_kb = parts.get(2).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let util = parts.get(3).and_then(|v| v.parse::<f32>().ok());
                    let driver = parts.get(4).map(|s| s.to_string());
                    res.push(GpuInfo { name, vendor: Some("NVIDIA".to_string()), total_memory_kb: total_kb, used_memory_kb: used_kb, utilization_percent: util, device_id: None, driver_version: driver });
                }
                if !res.is_empty() { return Some(res); }
            }
        }
    }

    // Linux: try lspci to fetch a GPU name
    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lspci").arg("-nn").output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    let mut res = Vec::new();
                    for line in s.lines() {
                        let low = line.to_lowercase();
                        if low.contains("vga") || low.contains("3d") || low.contains("display") {
                            // Try to extract vendor token if present
                            let vendor = if low.contains("nvidia") { Some("NVIDIA".to_string()) } else if low.contains("intel") { Some("Intel".to_string()) } else if low.contains("amd") { Some("AMD".to_string()) } else { None };
                            res.push(GpuInfo { name: Some(line.to_string()), vendor, total_memory_kb: None, used_memory_kb: None, utilization_percent: None, device_id: None, driver_version: None });
                        }
                    }
                    if !res.is_empty() { return Some(res); }
                }
            }
        }
    }

    // macOS: system_profiler
    if cfg!(target_os = "macos") {
        if let Ok(out) = Command::new("system_profiler").args(&["SPDisplaysDataType","-json"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if s.to_lowercase().contains("apple") || s.to_lowercase().contains("intel") || s.to_lowercase().contains("amd") {
                        return Some(vec![GpuInfo { name: Some("macOS GPU".to_string()), vendor: None, total_memory_kb: None, used_memory_kb: None, utilization_percent: None, device_id: None, driver_version: None }]);
                    }
                }
            }
        }
    }

    // Windows: use PowerShell CIM query (more reliable than legacy wmic) and parse JSON
    if cfg!(target_os = "windows") {
        let ps = r#"Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,PNPDeviceID,DriverVersion | ConvertTo-Json"#;
        if let Ok(out) = Command::new("powershell").args(&["-NoProfile","-Command", ps]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        if json.is_array() {
                            for item in json.as_array().unwrap_or(&vec![]) {
                                let name = item.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let total_kb = item.get("AdapterRAM").and_then(|v| v.as_u64()).map(|b| b / 1024);
                                let pnp = item.get("PNPDeviceID").and_then(|v| v.as_str()).map(|s| s.to_string());
                                let drv = item.get("DriverVersion").and_then(|v| v.as_str()).map(|s| s.to_string());
                                // vendor hint from name
                                let vendor = name.as_ref().and_then(|n| {
                                    let ln = n.to_lowercase();
                                    if ln.contains("nvidia") { Some("NVIDIA".to_string()) }
                                    else if ln.contains("intel") { Some("Intel".to_string()) }
                                    else if ln.contains("amd") { Some("AMD".to_string()) }
                                    else { None }
                                });
                                res.push(GpuInfo { name, vendor, total_memory_kb: total_kb, used_memory_kb: None, utilization_percent: None, device_id: pnp, driver_version: drv });
                            }
                        } else if json.is_object() {
                            let name = json.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let total_kb = json.get("AdapterRAM").and_then(|v| v.as_u64()).map(|b| b / 1024);
                            let pnp = json.get("PNPDeviceID").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let drv = json.get("DriverVersion").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let vendor = name.as_ref().and_then(|n| {
                                let ln = n.to_lowercase();
                                if ln.contains("nvidia") { Some("NVIDIA".to_string()) }
                                else if ln.contains("intel") { Some("Intel".to_string()) }
                                else if ln.contains("amd") { Some("AMD".to_string()) }
                                else { None }
                            });
                            res.push(GpuInfo { name, vendor, total_memory_kb: total_kb, used_memory_kb: None, utilization_percent: None, device_id: pnp, driver_version: drv });
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }
    }

    None
}

fn detect_npu() -> Option<Vec<NpuInfo>> {
    // Very best-effort detection: search system device lists for NPU keywords
    // Linux: check lspci for known NPU keywords
    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lspci").arg("-nn").output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    let low = s.to_lowercase();
                    let mut res = Vec::new();
                    for kw in &["npu", "neural", "movidius", "ethos", "ascend", "vision"] {
                        if low.contains(kw) {
                            res.push(NpuInfo { name: Some(kw.to_string()), utilization_percent: None, device_id: None, class: Some("lspci".to_string()) });
                        }
                    }
                    if !res.is_empty() { return Some(res); }
                }
            }
        }
    }

    // Windows: use PowerShell to list PnP devices and CIM entities and search for NPU-like keywords
    if cfg!(target_os = "windows") {
        // First try enumerating PnP devices (Name, FriendlyName, Class)
    // Include InstanceId so we can return a useful device identifier
    let ps_pnp = r#"Get-PnpDevice -ErrorAction SilentlyContinue | Select-Object Name,FriendlyName,Class,InstanceId | ConvertTo-Json -Compress"#;
        if let Ok(out) = Command::new("powershell").args(&["-NoProfile","-Command", ps_pnp]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
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
                                // Expand keyword list to catch Intel GNA, AI Boost, and related captions and ComputeAccelerator class
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
                                    "ai boost",
                                    "vision",
                                    "compute accelerator",
                                ] {
                                    if low.contains(kw) || class_field.as_deref().map(|c| c.eq_ignore_ascii_case("ComputeAccelerator")).unwrap_or(false) {
                                        let dev_name = friendly.clone().or(name_field.clone()).or(class_field.clone()).or(Some(kw.to_string()));
                                        let dev_id = instance_id.clone();
                                        res.push(NpuInfo { name: dev_name, utilization_percent: None, device_id: dev_id, class: class_field.clone() });
                                        break;
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
                                "intel gna",
                                "gna",
                                "gna scoring",
                                "gna scoring accelerator",
                                "ai boost",
                                "vision",
                                "compute accelerator",
                            ] {
                                if low.contains(kw) || class_field.as_deref().map(|c| c.eq_ignore_ascii_case("ComputeAccelerator")).unwrap_or(false) {
                                    let dev_name = friendly.clone().or(name_field.clone()).or(class_field.clone()).or(Some(kw.to_string()));
                                    let dev_id = json.get("InstanceId").and_then(|v| v.as_str()).map(|s| s.to_string());
                                    res.push(NpuInfo { name: dev_name, utilization_percent: None, device_id: dev_id, class: class_field.clone() });
                                    break;
                                }
                            }
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }

        // As a fallback, query CIM Win32_PnPEntity for caption/name fields
    // Include DeviceID so we can surface it
    let ps_cim = r#"Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Select-Object Name,Caption,DeviceID | ConvertTo-Json -Compress"#;
        if let Ok(out) = Command::new("powershell").args(&["-NoProfile","-Command", ps_cim]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        // Search per-item and return the device name/caption when matched
                        if json.is_array() {
                            let mut res = Vec::new();
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
                                    "ai boost",
                                    "vision",
                                    "compute accelerator",
                                ] {
                                    if low.contains(kw) {
                                        let dev_name = caption.clone().or(name_field.clone()).or(Some(kw.to_string()));
                                        let dev_id = device_id.clone();
                                        res.push(NpuInfo { name: dev_name, utilization_percent: None, device_id: dev_id, class: None });
                                        break;
                                    }
                                }
                            }
                            if !res.is_empty() { return Some(res); }
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
                                "intel gna",
                                "gna",
                                "gna scoring",
                                "gna scoring accelerator",
                                "ai boost",
                                "vision",
                                "compute accelerator",
                            ] {
                                if low.contains(kw) {
                                    let dev_name = caption.or(name_field).or(Some(kw.to_string()));
                                    let dev_id = json.get("DeviceID").and_then(|v| v.as_str()).map(|s| s.to_string());
                                    return Some(vec![NpuInfo { name: dev_name, utilization_percent: None, device_id: dev_id, class: None }]);
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
                        return Some(vec![NpuInfo {
                            name: Some("Apple Neural Engine".to_string()),
                            utilization_percent: None,
                            device_id: None,
                            class: Some("Apple Neural Engine".to_string())
                        }]);
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

