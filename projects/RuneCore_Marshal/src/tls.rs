use rustls::ServerConfig as RustlsServerConfig;
use rustls::server::WebPkiClientVerifier;
use rustls_pemfile::{certs, pkcs8_private_keys, rsa_private_keys};
use std::fs::File;
use std::io::BufReader;
use std::sync::Arc;

/// Load server TLS config with mutual TLS (client cert required).
/// Returns a rustls ServerConfig that axum-server can use.
///
/// Key loading order:
///   1. `<key_path>.dpapi` — DPAPI-encrypted blob (Windows only, written by bootstrap)
///   2. `<key_path>`       — plain PEM (dev fallback or non-Windows)
pub fn load_server_tls(
    cert_path: &str,
    key_path: &str,
    ca_path: &str,
) -> Result<RustlsServerConfig, String> {
    // Load server certificate chain
    let cert_file = File::open(cert_path)
        .map_err(|e| format!("Cannot open cert {cert_path}: {e}"))?;
    let server_certs: Vec<_> = certs(&mut BufReader::new(cert_file))
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Failed to parse server cert: {e}"))?;

    // Load private key — DPAPI-encrypted variant takes priority on Windows
    let key_bytes = load_key_bytes(key_path)?;

    let private_key = {
        let mut reader = BufReader::new(key_bytes.as_slice());
        let pkcs8: Vec<_> = pkcs8_private_keys(&mut reader)
            .collect::<Result<Vec<_>, _>>()
            .unwrap_or_default();
        if !pkcs8.is_empty() {
            rustls::pki_types::PrivateKeyDer::Pkcs8(pkcs8.into_iter().next().unwrap())
        } else {
            let mut reader = BufReader::new(key_bytes.as_slice());
            let rsa: Vec<_> = rsa_private_keys(&mut reader)
                .collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("Failed to parse private key: {e}"))?;
            if rsa.is_empty() {
                return Err(format!("No private key found in {key_path}"));
            }
            rustls::pki_types::PrivateKeyDer::Pkcs1(rsa.into_iter().next().unwrap())
        }
    };

    // Load CA cert for client verification
    let ca_file = File::open(ca_path)
        .map_err(|e| format!("Cannot open CA cert {ca_path}: {e}"))?;
    let ca_certs: Vec<_> = certs(&mut BufReader::new(ca_file))
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Failed to parse CA cert: {e}"))?;

    let mut roots = rustls::RootCertStore::empty();
    for ca_cert in ca_certs {
        roots.add(ca_cert).map_err(|e| format!("Failed to add CA cert: {e}"))?;
    }

    // Require client cert signed by our CA
    let client_verifier = WebPkiClientVerifier::builder(Arc::new(roots))
        .build()
        .map_err(|e| format!("Failed to build client verifier: {e}"))?;

    let config = RustlsServerConfig::builder()
        .with_client_cert_verifier(client_verifier)
        .with_single_cert(server_certs, private_key)
        .map_err(|e| format!("Failed to build TLS config: {e}"))?;

    Ok(config)
}

/// Load the raw PEM bytes for the private key.
/// On Windows, checks for `<key_path>.dpapi` first and decrypts with DPAPI.
/// Falls back to reading `key_path` as plain PEM.
fn load_key_bytes(key_path: &str) -> Result<Vec<u8>, String> {
    let dpapi_path = format!("{}.dpapi", key_path);

    if std::path::Path::new(&dpapi_path).exists() {
        #[cfg(target_os = "windows")]
        {
            log::info!("Loading DPAPI-encrypted private key from {}", dpapi_path);
            let encrypted = std::fs::read(&dpapi_path)
                .map_err(|e| format!("Cannot read {dpapi_path}: {e}"))?;
            return crate::dpapi::unprotect(&encrypted)
                .map_err(|e| format!("DPAPI decryption failed: {e}"));
        }
        #[cfg(not(target_os = "windows"))]
        {
            return Err(format!(
                "DPAPI key file found at {} but DPAPI is not supported on this platform",
                dpapi_path
            ));
        }
    }

    // Plain PEM — dev fallback
    std::fs::read(key_path)
        .map_err(|e| format!("Cannot read key {key_path}: {e}"))
}

/// Extract the Common Name (CN) from a DER-encoded X.509 certificate.
/// Returns None if the cert cannot be parsed or CN is missing.
pub fn extract_cn_from_der(der: &[u8]) -> Option<String> {
    use x509_parser::prelude::*;
    let (_, cert) = X509Certificate::from_der(der).ok()?;
    let subject = cert.subject();
    for rdn in subject.iter_rdn() {
        for attr in rdn.iter() {
            if attr.attr_type() == &oid_registry::OID_X509_COMMON_NAME {
                if let Ok(s) = attr.attr_value().as_str() {
                    return Some(s.to_string());
                }
            }
        }
    }
    None
}
