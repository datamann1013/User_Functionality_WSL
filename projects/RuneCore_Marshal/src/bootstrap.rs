//! Bootstrap mode: obtain a TLS cert from RuneCore_Core's CA.
//!
//! Invoked as:
//!   runecore_marshal.exe --bootstrap --token TOKEN --core-url URL
//!                        [--install-dir DIR] [--cn CN] [--days N]
//!
//! What it does:
//!   1. Generates an ECDSA P-256 keypair + CSR (pure Rust, no system OpenSSL)
//!   2. POSTs the CSR + token to Core's /api/v1/pki/native/issue endpoint
//!   3. Writes marshal.crt and ca.crt to <install-dir>/certs/
//!   4. Writes marshal.key.dpapi  (DPAPI-encrypted, Windows) or marshal.key (PEM, other)
//!   5. Locks the certs/ directory to SYSTEM + Administrators via icacls (Windows)

use rcgen::{Certificate, CertificateParams, DistinguishedName, DnType, IsCa};

pub struct BootstrapArgs {
    pub token: String,
    pub core_url: String,
    pub install_dir: String,
    pub cn: String,
    pub days_valid: u32,
}

/// Parse the args slice that follows `--bootstrap` on the command line.
pub fn parse_args(args: &[String]) -> Result<BootstrapArgs, String> {
    let mut token = None;
    let mut core_url = None;
    let mut install_dir = "C:/RuneCore/marshal".to_string();
    let mut cn = "runecore_marshal".to_string();
    let mut days_valid = 365u32;

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--token" => {
                i += 1;
                token = args.get(i).cloned();
            }
            "--core-url" => {
                i += 1;
                core_url = args.get(i).cloned();
            }
            "--install-dir" => {
                i += 1;
                install_dir = args.get(i).cloned().unwrap_or(install_dir);
            }
            "--cn" => {
                i += 1;
                cn = args.get(i).cloned().unwrap_or(cn);
            }
            "--days" => {
                i += 1;
                days_valid = args
                    .get(i)
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(365);
            }
            _ => {}
        }
        i += 1;
    }

    Ok(BootstrapArgs {
        token: token.ok_or("--token is required")?,
        core_url: core_url.ok_or("--core-url is required")?,
        install_dir,
        cn,
        days_valid,
    })
}

/// Main bootstrap entry point — runs synchronously (called before tokio starts).
pub fn run(args: BootstrapArgs) -> Result<(), String> {
    println!(
        "[bootstrap] Generating keypair for CN={}",
        args.cn
    );

    // 1. Generate ECDSA P-256 keypair + CSR
    let mut params = CertificateParams::default();
    let mut dn = DistinguishedName::new();
    dn.push(DnType::CommonName, &args.cn);
    params.distinguished_name = dn;
    params.is_ca = IsCa::NoCa;

    let cert = Certificate::from_params(params)
        .map_err(|e| format!("Key generation failed: {}", e))?;

    let csr_pem = cert
        .serialize_request_pem()
        .map_err(|e| format!("CSR generation failed: {}", e))?;
    let key_pem = cert.serialize_private_key_pem();

    // 2. Call Core to issue cert
    println!(
        "[bootstrap] Requesting cert from {}",
        args.core_url
    );

    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("HTTP client error: {}", e))?;

    let issue_url = format!(
        "{}/api/v1/pki/native/issue",
        args.core_url.trim_end_matches('/')
    );

    let resp = client
        .post(&issue_url)
        .json(&serde_json::json!({
            "cn":         args.cn,
            "csr_pem":    csr_pem,
            "token":      args.token,
            "days_valid": args.days_valid,
        }))
        .send()
        .map_err(|e| format!("Failed to reach Core PKI at {}: {}", issue_url, e))?;

    if !resp.status().is_success() {
        return Err(format!(
            "Core PKI returned HTTP {}",
            resp.status()
        ));
    }

    let body: serde_json::Value = resp
        .json()
        .map_err(|e| format!("Invalid JSON from Core PKI: {}", e))?;

    if !body["ok"].as_bool().unwrap_or(false) {
        return Err(format!(
            "Core PKI rejected cert issuance: {}",
            body["error"].as_str().unwrap_or("unknown error")
        ));
    }

    let cert_pem = body["cert_pem"]
        .as_str()
        .ok_or("missing cert_pem in Core response")?;
    let ca_pem = body["ca_cert_pem"]
        .as_str()
        .ok_or("missing ca_cert_pem in Core response")?;

    // 3. Write cert files
    let certs_dir = std::path::Path::new(&args.install_dir).join("certs");
    std::fs::create_dir_all(&certs_dir)
        .map_err(|e| format!("Cannot create certs dir {:?}: {}", certs_dir, e))?;

    std::fs::write(certs_dir.join("marshal.crt"), cert_pem)
        .map_err(|e| format!("Cannot write marshal.crt: {}", e))?;
    std::fs::write(certs_dir.join("ca.crt"), ca_pem)
        .map_err(|e| format!("Cannot write ca.crt: {}", e))?;

    println!("[bootstrap] Wrote marshal.crt and ca.crt");

    // 4. Store private key — DPAPI on Windows, plain PEM elsewhere
    store_key(&certs_dir, key_pem.as_bytes())?;

    // 5. Lock the certs/ directory (Windows)
    #[cfg(target_os = "windows")]
    lock_certs_dir(certs_dir.to_str().unwrap_or(""))?;

    println!("[bootstrap] Done — certs stored in {:?}", certs_dir);
    Ok(())
}

// ── Key storage ──────────────────────────────────────────────────────────────

fn store_key(certs_dir: &std::path::Path, key_pem: &[u8]) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        use crate::dpapi;
        let encrypted = dpapi::protect(key_pem)?;
        std::fs::write(certs_dir.join("marshal.key.dpapi"), &encrypted)
            .map_err(|e| format!("Cannot write marshal.key.dpapi: {}", e))?;
        println!("[bootstrap] Private key DPAPI-encrypted (machine scope)");
        return Ok(());
    }

    #[allow(unreachable_code)]
    {
        std::fs::write(certs_dir.join("marshal.key"), key_pem)
            .map_err(|e| format!("Cannot write marshal.key: {}", e))?;
        println!("[bootstrap] Private key written as plain PEM (non-Windows)");
        Ok(())
    }
}

// ── ACL hardening ─────────────────────────────────────────────────────────────

#[cfg(target_os = "windows")]
fn lock_certs_dir(path: &str) -> Result<(), String> {
    if path.is_empty() {
        return Ok(());
    }
    let status = std::process::Command::new("icacls")
        .args([
            path,
            "/inheritance:r",
            "/grant",
            "SYSTEM:(OI)(CI)F",
            "/grant",
            "Administrators:(OI)(CI)F",
        ])
        .status()
        .map_err(|e| format!("icacls failed: {}", e))?;

    if !status.success() {
        // Non-fatal — log a warning but don't abort bootstrap
        eprintln!(
            "[bootstrap] Warning: icacls exited with {:?} — certs directory ACL may not be restricted",
            status.code()
        );
    } else {
        println!("[bootstrap] certs/ ACL: SYSTEM + Administrators only");
    }
    Ok(())
}
