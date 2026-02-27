use anyhow::Result;
use std::{path::Path, fs};

/// Certificate Revocation List management
///
/// openssl-rs 0.10.x does not expose an X509CrlBuilder API, so full PEM-CRL
/// generation is not yet implemented here.  Revocation state is tracked in
/// `cert_registry.json` via `CertificateRegistry`.  The `/api/v1/pki/crl`
/// endpoint serves the CRL PEM file if one already exists on disk (e.g.
/// generated externally), and returns an error otherwise.

pub struct CrlManager {
    data_dir: String,
}

impl CrlManager {
    pub fn new(data_dir: &str) -> Self {
        CrlManager {
            data_dir: data_dir.to_string(),
        }
    }

    /// No-op: CRL PEM generation requires openssl-rs builder APIs not yet
    /// available.  Revocation is tracked via `CertificateRegistry`.
    pub fn init_crl(&self, _passphrase: &str) -> Result<()> {
        tracing::warn!(
            "CRL PEM builder not available in this build; \
             revocation tracked via cert_registry.json"
        );
        Ok(())
    }

    /// Record a revocation.  Updates `cert_registry.json`; does not
    /// regenerate the CRL PEM file (see `init_crl` note above).
    pub fn revoke_certificate(&self, _passphrase: &str, serial: &str, reason: &str) -> Result<()> {
        // Actual JSON tracking is done by the caller via CertificateRegistry.
        // This method exists so that main.rs can call crl_manager.revoke_certificate()
        // without needing to know about the implementation limitation.
        tracing::info!(
            "Certificate {} marked for revocation (reason: {}); \
             update cert_registry.json for persistent record",
            serial,
            reason
        );
        Ok(())
    }

    /// Check whether a certificate serial is revoked by consulting the JSON
    /// registry (not the PEM CRL, which may not exist).
    pub fn is_revoked(&self, serial: &str) -> Result<bool> {
        let registry_path = Path::new(&self.data_dir).join("cert_registry.json");
        if !registry_path.exists() {
            return Ok(false);
        }
        let content = fs::read_to_string(&registry_path)?;
        let registry: serde_json::Value = serde_json::from_str(&content)?;
        if let Some(cert_info) = registry["certificates"].get(serial) {
            return Ok(cert_info["status"].as_str() == Some("revoked"));
        }
        Ok(false)
    }

    /// Return all revoked serials from the JSON registry.
    pub fn get_revoked_list(&self) -> Result<Vec<String>> {
        let registry_path = Path::new(&self.data_dir).join("cert_registry.json");
        if !registry_path.exists() {
            return Ok(Vec::new());
        }
        let content = fs::read_to_string(&registry_path)?;
        let registry: serde_json::Value = serde_json::from_str(&content)?;
        let mut revoked = Vec::new();
        if let Some(certs) = registry["certificates"].as_object() {
            for (serial, info) in certs {
                if info["status"].as_str() == Some("revoked") {
                    revoked.push(serial.clone());
                }
            }
        }
        Ok(revoked)
    }

    /// Serve the CRL PEM file from disk, if it exists.
    pub fn get_crl_pem(&self) -> Result<Vec<u8>> {
        let crl_path = Path::new(&self.data_dir).join("ca_crl.pem");
        if crl_path.exists() {
            Ok(fs::read(&crl_path)?)
        } else {
            anyhow::bail!("CRL file not found; revocation tracked via cert_registry.json")
        }
    }
}

/// Track issued certificates for renewal validation and revocation state.
pub struct CertificateRegistry {
    data_dir: String,
}

impl CertificateRegistry {
    pub fn new(data_dir: &str) -> Self {
        CertificateRegistry {
            data_dir: data_dir.to_string(),
        }
    }

    /// Record an issued certificate.
    pub fn register_certificate(
        &self,
        serial: &str,
        container_name: &str,
        service_name: &str,
        issued_at: i64,
    ) -> Result<()> {
        let registry_path = Path::new(&self.data_dir).join("cert_registry.json");
        let mut registry: serde_json::Value = if registry_path.exists() {
            let content = fs::read_to_string(&registry_path)?;
            serde_json::from_str(&content)?
        } else {
            serde_json::json!({ "certificates": {} })
        };

        registry["certificates"][serial] = serde_json::json!({
            "container_name": container_name,
            "service_name": service_name,
            "issued_at": issued_at,
            "status": "active"
        });

        fs::write(registry_path, serde_json::to_string_pretty(&registry)?)?;
        Ok(())
    }

    /// Verify that the container name matches the recorded certificate.
    pub fn verify_renewal(&self, serial: &str, container_name: &str) -> Result<bool> {
        let registry_path = Path::new(&self.data_dir).join("cert_registry.json");
        if !registry_path.exists() {
            return Ok(false);
        }
        let content = fs::read_to_string(&registry_path)?;
        let registry: serde_json::Value = serde_json::from_str(&content)?;
        if let Some(cert_info) = registry["certificates"].get(serial) {
            if let Some(registered_container) = cert_info["container_name"].as_str() {
                return Ok(registered_container == container_name);
            }
        }
        Ok(false)
    }

    /// Mark a certificate as revoked in the registry.
    pub fn mark_revoked(&self, serial: &str) -> Result<()> {
        let registry_path = Path::new(&self.data_dir).join("cert_registry.json");
        if !registry_path.exists() {
            return Ok(());
        }
        let content = fs::read_to_string(&registry_path)?;
        let mut registry: serde_json::Value = serde_json::from_str(&content)?;
        if let Some(cert_info) = registry["certificates"].get_mut(serial) {
            cert_info["status"] = serde_json::json!("revoked");
        }
        fs::write(registry_path, serde_json::to_string_pretty(&registry)?)?;
        Ok(())
    }
}
