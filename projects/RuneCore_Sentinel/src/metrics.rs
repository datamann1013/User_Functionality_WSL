use serde::{Deserialize, Serialize};
use sysinfo::{CpuExt, System, SystemExt};
use std::time::{SystemTime, UNIX_EPOCH};
use std::process::Command;
use std::str;
use serde_json::Value as JsonValue;

// ── Subprocess helpers ────────────────────────────────────────────────────────
//
// On Windows every Command::new() spawns a new console window unless
// CREATE_NO_WINDOW is set.  All subprocess calls in this file use these
// helpers so nothing ever flashes on screen.

#[cfg(target_os = "windows")]
fn run_powershell(script: &str) -> std::io::Result<std::process::Output> {
    use std::os::windows::process::CommandExt;
    Command::new("powershell")
        .creation_flags(0x0800_0000) // CREATE_NO_WINDOW
        .args(["-NoProfile", "-Command", script])
        .output()
}

// nvidia-smi wrapper — suppresses console window on Windows
fn run_nvidia_smi(args: &[&str]) -> std::io::Result<std::process::Output> {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        Command::new("nvidia-smi")
            .creation_flags(0x0800_0000)
            .args(args)
            .output()
    }
    #[cfg(not(target_os = "windows"))]
    Command::new("nvidia-smi").args(args).output()
}

// ── Data types ────────────────────────────────────────────────────────────────

/// Hardware facts that don't change at runtime.
/// Collected ONCE at startup via PowerShell / system tools.
/// Never called again in the hot loop.
#[derive(Debug, Clone)]
pub struct StaticHardware {
    /// GPU model, vendor, total VRAM, driver — from nvidia-smi or PowerShell
    pub gpu_base: Option<Vec<GpuInfo>>,
    pub npu: Option<Vec<NpuInfo>>,
    pub disks: Option<Vec<DiskInfo>>,
    pub ram_slots: Option<Vec<RamSlotInfo>>,
}

/// Live telemetry sampled every loop iteration.
/// Only fast operations: sysinfo (no subprocess) + nvidia-smi (fast, hidden window).
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SystemMetrics {
    pub ts: u128,
    pub host: String,
    pub cpu_usage: f32,
    pub cpu_model: Option<String>,
    pub cpu_frequency_mhz: Option<u64>,
    pub per_core_frequency_mhz: Option<Vec<u64>>,
    pub total_memory: u64,
    pub used_memory: u64,
    pub gpu: Option<Vec<GpuInfo>>,
    pub npu: Option<Vec<NpuInfo>>,
    pub disks: Option<Vec<DiskInfo>>,
    pub ram_slots: Option<Vec<RamSlotInfo>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GpuInfo {
    pub name: Option<String>,
    pub vendor: Option<String>,
    pub total_memory_kb: Option<u64>,
    pub used_memory_kb: Option<u64>,
    pub utilization_percent: Option<f32>,
    pub device_id: Option<String>,
    pub driver_version: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct NpuInfo {
    pub name: Option<String>,
    pub utilization_percent: Option<f32>,
    pub device_id: Option<String>,
    pub class: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DiskInfo {
    pub model: Option<String>,
    pub media_type: Option<String>,
    pub size_gb: Option<f64>,
    pub serial: Option<String>,
    pub interface: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RamSlotInfo {
    pub capacity_gb: Option<f64>,
    pub speed_mhz: Option<u32>,
    pub memory_type: Option<String>,
    pub manufacturer: Option<String>,
}

// ── Public API ────────────────────────────────────────────────────────────────

/// Called ONCE at startup.  Runs all slow PowerShell/subprocess probes.
pub fn collect_static_hardware() -> StaticHardware {
    StaticHardware {
        gpu_base:  detect_gpu_static(),
        npu:       detect_npu(),
        disks:     detect_disks(),
        ram_slots: detect_ram_slots(),
    }
}

/// Called every loop iteration — fast, no PowerShell.
/// Reads CPU/memory from sysinfo and refreshes GPU utilization via nvidia-smi.
pub fn sample_system_metrics(hw: &StaticHardware) -> SystemMetrics {
    let mut sys = System::new_all();
    sys.refresh_cpu();
    sys.refresh_memory();

    let cpu       = sys.global_cpu_info().cpu_usage();
    let total_mem = sys.total_memory();
    let used_mem  = sys.used_memory();

    let cpu_model = sys.cpus().first().and_then(|c| {
        let b = c.brand();
        if b.trim().is_empty() { None } else { Some(b.to_string()) }
    });
    let cpu_frequency_mhz = sys.cpus().first().map(|c| c.frequency() as u64);
    let per_core_frequency_mhz = {
        let freqs: Vec<u64> = sys.cpus().iter().map(|c| c.frequency() as u64).collect();
        if freqs.is_empty() { None } else { Some(freqs) }
    };

    let ts   = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
    let host = sys.host_name().unwrap_or_else(|| "unknown".to_string());

    // Merge cached static GPU info with fresh nvidia-smi utilization (hidden window)
    let gpu = sample_gpu_live(&hw.gpu_base);

    SystemMetrics {
        ts, host, cpu_usage: cpu, cpu_model,
        cpu_frequency_mhz, per_core_frequency_mhz,
        total_memory: total_mem, used_memory: used_mem,
        gpu,
        npu:       hw.npu.clone(),
        disks:     hw.disks.clone(),
        ram_slots: hw.ram_slots.clone(),
    }
}

// ── GPU ───────────────────────────────────────────────────────────────────────

/// Collect static GPU info (name, vendor, total VRAM, driver).  Called ONCE.
fn detect_gpu_static() -> Option<Vec<GpuInfo>> {
    // nvidia-smi: fast, gives us everything including initial util snapshot
    if let Ok(out) = run_nvidia_smi(&[
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]) {
        if out.status.success() {
            if let Ok(s) = str::from_utf8(&out.stdout) {
                let mut res = Vec::new();
                for line in s.lines() {
                    let parts: Vec<&str> = line.split(',').map(|p| p.trim()).collect();
                    let name     = parts.first().map(|s| s.to_string());
                    let total_kb = parts.get(1).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let driver   = parts.get(2).map(|s| s.to_string());
                    res.push(GpuInfo {
                        name, vendor: Some("NVIDIA".to_string()),
                        total_memory_kb: total_kb, used_memory_kb: None,
                        utilization_percent: None, device_id: None, driver_version: driver,
                    });
                }
                if !res.is_empty() { return Some(res); }
            }
        }
    }

    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lspci").arg("-nn").output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    let mut res = Vec::new();
                    for line in s.lines() {
                        let low = line.to_lowercase();
                        if low.contains("vga") || low.contains("3d") || low.contains("display") {
                            let vendor = vendor_from_name(line);
                            res.push(GpuInfo { name: Some(line.to_string()), vendor,
                                total_memory_kb: None, used_memory_kb: None,
                                utilization_percent: None, device_id: None, driver_version: None });
                        }
                    }
                    if !res.is_empty() { return Some(res); }
                }
            }
        }
    }

    // Windows fallback: PowerShell CIM — called ONCE only, hidden window
    #[cfg(target_os = "windows")]
    {
        let ps = r#"Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,PNPDeviceID,DriverVersion | ConvertTo-Json"#;
        if let Ok(out) = run_powershell(ps) {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        for item in json_to_array(json) {
                            let name     = item.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let total_kb = item.get("AdapterRAM").and_then(|v| v.as_u64()).map(|b| b / 1024);
                            let pnp      = item.get("PNPDeviceID").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let drv      = item.get("DriverVersion").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let vendor   = name.as_deref().and_then(vendor_from_name);
                            res.push(GpuInfo { name, vendor, total_memory_kb: total_kb,
                                used_memory_kb: None, utilization_percent: None,
                                device_id: pnp, driver_version: drv });
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }
    }

    None
}

/// Called every loop — runs only nvidia-smi (fast, hidden window) to get live
/// utilization/used-VRAM.  Falls back to static base for non-NVIDIA GPUs.
fn sample_gpu_live(base: &Option<Vec<GpuInfo>>) -> Option<Vec<GpuInfo>> {
    if let Ok(out) = run_nvidia_smi(&[
        "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version",
        "--format=csv,noheader,nounits",
    ]) {
        if out.status.success() {
            if let Ok(s) = str::from_utf8(&out.stdout) {
                let mut res = Vec::new();
                for line in s.lines() {
                    let parts: Vec<&str> = line.split(',').map(|p| p.trim()).collect();
                    let name     = parts.first().map(|s| s.to_string());
                    let total_kb = parts.get(1).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let used_kb  = parts.get(2).and_then(|v| v.parse::<u64>().ok()).map(|m| m * 1024);
                    let util     = parts.get(3).and_then(|v| v.parse::<f32>().ok());
                    let driver   = parts.get(4).map(|s| s.to_string());
                    res.push(GpuInfo {
                        name, vendor: Some("NVIDIA".to_string()),
                        total_memory_kb: total_kb, used_memory_kb: used_kb,
                        utilization_percent: util, device_id: None, driver_version: driver,
                    });
                }
                if !res.is_empty() { return Some(res); }
            }
        }
    }
    base.clone()
}

// ── NPU ───────────────────────────────────────────────────────────────────────

fn detect_npu() -> Option<Vec<NpuInfo>> {
    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lspci").arg("-nn").output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    let mut res = Vec::new();
                    for line in s.lines() {
                        let low = line.to_lowercase();
                        if low.contains("npu") || low.contains("movidius") || low.contains("myriad")
                            || low.contains("amd xdna") || low.contains("qualcomm ai")
                        {
                            res.push(NpuInfo {
                                name: Some(line.trim().to_string()),
                                utilization_percent: None, device_id: None,
                                class: vendor_from_name(line),
                            });
                        }
                    }
                    if !res.is_empty() { return Some(res); }
                }
            }
        }
    }

    #[cfg(target_os = "windows")]
    {
        // Phase 1 — ComputeAccelerator class (Intel AI Boost, AMD XDNA, Qualcomm NPU)
        let ps1 = r#"Get-PnpDevice -Class ComputeAccelerator -ErrorAction SilentlyContinue | Select-Object Name,FriendlyName,InstanceId | ConvertTo-Json -Compress"#;
        if let Ok(out) = run_powershell(ps1) {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        for item in json_to_array(json) {
                            let friendly  = item.get("FriendlyName").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let name_f    = item.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let inst_id   = item.get("InstanceId").and_then(|v| v.as_str()).map(|s| s.to_string());
                            if let Some(dev_name) = friendly.or(name_f) {
                                res.push(NpuInfo { name: Some(dev_name), utilization_percent: None,
                                    device_id: inst_id, class: Some("ComputeAccelerator".to_string()) });
                            }
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }

        // Phase 2 — targeted product-name fallback
        const NPU_NAMES: &[&str] = &[
            "intel(r) ai boost", "intel ai boost",
            "intel(r) gna scoring accelerator", "intel(r) gna",
            "amd xdna", "amd ryzen ai",
            "qualcomm(r) npu", "qualcomm npu", "qualcomm ai",
            "movidius", "myriad",
        ];
        let ps2 = r#"Get-PnpDevice -ErrorAction SilentlyContinue | Select-Object Name,FriendlyName,Class,InstanceId | ConvertTo-Json -Compress"#;
        if let Ok(out) = run_powershell(ps2) {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        for item in json_to_array(json) {
                            let name_f   = item.get("Name").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let friendly = item.get("FriendlyName").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let class_f  = item.get("Class").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let inst_id  = item.get("InstanceId").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let combined = format!("{} {} {}",
                                name_f.as_deref().unwrap_or(""),
                                friendly.as_deref().unwrap_or(""),
                                class_f.as_deref().unwrap_or(""),
                            ).to_lowercase();
                            if NPU_NAMES.iter().any(|kw| combined.contains(kw)) {
                                res.push(NpuInfo { name: friendly.or(name_f),
                                    utilization_percent: None, device_id: inst_id, class: class_f });
                                break;
                            }
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }
    }

    if cfg!(target_os = "macos") {
        if let Ok(out) = Command::new("system_profiler").args(&["SPHardwareDataType", "-json"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if s.to_lowercase().contains("neural engine") {
                        return Some(vec![NpuInfo {
                            name: Some("Apple Neural Engine".to_string()),
                            utilization_percent: None, device_id: None,
                            class: Some("Apple Neural Engine".to_string()),
                        }]);
                    }
                }
            }
        }
    }

    None
}

// ── Disks ─────────────────────────────────────────────────────────────────────

fn detect_disks() -> Option<Vec<DiskInfo>> {
    #[cfg(target_os = "windows")]
    {
        let ps = r#"Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size,SerialNumber,BusType | ConvertTo-Json"#;
        if let Ok(out) = run_powershell(ps) {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        for item in json_to_array(json) {
                            let model      = item.get("FriendlyName").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let media_type = item.get("MediaType").and_then(|v| v.as_str()).map(|s| s.to_string());
                            let size_gb    = item.get("Size").and_then(|v| v.as_u64())
                                .map(|b| b as f64 / (1024.0 * 1024.0 * 1024.0));
                            let serial     = item.get("SerialNumber").and_then(|v| v.as_str())
                                .map(|s| s.trim().to_string()).filter(|s| !s.is_empty());
                            let bus_type   = item.get("BusType").and_then(|v| v.as_str()).map(|s| s.to_string());
                            res.push(DiskInfo { model, media_type, size_gb, serial, interface: bus_type });
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }
    }

    if cfg!(target_os = "linux") {
        if let Ok(out) = Command::new("lsblk").args(&["-J", "-o", "NAME,MODEL,SIZE,TYPE,ROTA"]).output() {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        if let Some(devs) = json.get("blockdevices").and_then(|v| v.as_array()) {
                            for dev in devs {
                                if dev.get("type").and_then(|v| v.as_str()) != Some("disk") { continue; }
                                let model   = dev.get("model").and_then(|v| v.as_str())
                                    .filter(|s| !s.is_empty()).map(|s| s.trim().to_string());
                                let size_gb = dev.get("size").and_then(|v| v.as_str())
                                    .and_then(|s| parse_lsblk_size(s));
                                let is_rot  = dev.get("rota").and_then(|v| v.as_str()) == Some("1");
                                let name    = dev.get("name").and_then(|v| v.as_str()).unwrap_or("");
                                let (mt, iface) = if name.starts_with("nvme") {
                                    (Some("NVMe".to_string()), Some("NVMe".to_string()))
                                } else if is_rot {
                                    (Some("HDD".to_string()), Some("SATA".to_string()))
                                } else {
                                    (Some("SSD".to_string()), Some("SATA".to_string()))
                                };
                                res.push(DiskInfo { model, media_type: mt, size_gb, serial: None, interface: iface });
                            }
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }
    }

    None
}

// ── RAM slots ─────────────────────────────────────────────────────────────────

fn detect_ram_slots() -> Option<Vec<RamSlotInfo>> {
    #[cfg(target_os = "windows")]
    {
        let ps = r#"Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue | Select-Object Capacity,Speed,SMBIOSMemoryType,Manufacturer | ConvertTo-Json"#;
        if let Ok(out) = run_powershell(ps) {
            if out.status.success() {
                if let Ok(s) = str::from_utf8(&out.stdout) {
                    if let Ok(json) = serde_json::from_str::<JsonValue>(s) {
                        let mut res = Vec::new();
                        for item in json_to_array(json) {
                            let cap_gb  = item.get("Capacity").and_then(|v| v.as_u64())
                                .map(|b| b as f64 / (1024.0 * 1024.0 * 1024.0));
                            let speed   = item.get("Speed").and_then(|v| v.as_u64()).map(|s| s as u32);
                            let smbios  = item.get("SMBIOSMemoryType").and_then(|v| v.as_u64()).unwrap_or(0);
                            let mfr     = item.get("Manufacturer").and_then(|v| v.as_str())
                                .filter(|s| !s.trim().is_empty() && !s.trim().eq_ignore_ascii_case("unknown"))
                                .map(|s| s.trim().to_string());
                            res.push(RamSlotInfo { capacity_gb: cap_gb, speed_mhz: speed,
                                memory_type: smbios_memory_type(smbios), manufacturer: mfr });
                        }
                        if !res.is_empty() { return Some(res); }
                    }
                }
            }
        }
    }

    None
}

// ── Utilities ─────────────────────────────────────────────────────────────────

fn json_to_array(v: JsonValue) -> Vec<JsonValue> {
    match v {
        JsonValue::Array(arr) => arr,
        JsonValue::Object(_) => vec![v],
        _ => vec![],
    }
}

fn vendor_from_name(name: &str) -> Option<String> {
    let low = name.to_lowercase();
    if low.contains("nvidia") { Some("NVIDIA".to_string()) }
    else if low.contains("intel") { Some("Intel".to_string()) }
    else if low.contains("amd") { Some("AMD".to_string()) }
    else { None }
}

fn smbios_memory_type(t: u64) -> Option<String> {
    Some(match t {
        20 => "DDR",  21 => "DDR2", 24 => "DDR3", 26 => "DDR4", 34 => "DDR5",
        35 => "LPDDR", 36 => "LPDDR2", 37 => "LPDDR3", 38 => "LPDDR4", 43 => "LPDDR5",
        _ => return None,
    }.to_string())
}

fn parse_lsblk_size(s: &str) -> Option<f64> {
    let s = s.trim();
    if s.is_empty() { return None; }
    let (num, unit) = s.split_at(s.len().saturating_sub(1));
    let n: f64 = num.parse().ok()?;
    match unit.to_uppercase().as_str() {
        "T" => Some(n * 1024.0),
        "G" => Some(n),
        "M" => Some(n / 1024.0),
        _   => None,
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serialize_roundtrip_cbor() {
        let m = SystemMetrics {
            ts: 1, host: "test-host".to_string(),
            cpu_usage: 12.34, cpu_model: None,
            cpu_frequency_mhz: None, per_core_frequency_mhz: None,
            total_memory: 1024, used_memory: 512,
            gpu: None, npu: None, disks: None, ram_slots: None,
        };
        let bytes   = serde_cbor::to_vec(&m).expect("cbor serialize");
        let decoded: SystemMetrics = serde_cbor::from_slice(&bytes).expect("cbor deserialize");
        assert_eq!(decoded.host, "test-host");
        assert_eq!(decoded.total_memory, 1024);
    }

    #[test]
    fn smbios_type_mapping() {
        assert_eq!(smbios_memory_type(26).as_deref(), Some("DDR4"));
        assert_eq!(smbios_memory_type(34).as_deref(), Some("DDR5"));
        assert_eq!(smbios_memory_type(43).as_deref(), Some("LPDDR5"));
        assert!(smbios_memory_type(0).is_none());
    }
}
