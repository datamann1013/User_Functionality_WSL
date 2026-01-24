use anyhow::Result;
use std::{path::Path, fs};
use openssl::x509::{X509, X509Crl};
use openssl::pkey::PKey;
use openssl::bn::BigNum;
use openssl::asn1::Asn1Time;
use std::collections::HashSet;

/// Certificate Revocation List management
/// 
/// This module manages a CRL (Certificate Revocation List) for the RuneCore CA.
/// Services must check the CRL before accepting certificates.

pub struct CrlManager {
    data_dir: String,
}

impl CrlManager {
    pub fn new(data_dir: &str) -> Self {
        CrlManager {
            data_dir: data_dir.to_string(),
        }
    }
    
    /// Initialize empty CRL if it doesn't exist
    pub fn init_crl(&self, passphrase: &str) -> Result<()> {
        let crl_path = Path::new(&self.data_dir).join("ca_crl.pem");
        
        if crl_path.exists() {
            println!("CRL exists - skipping initialization");
            return Ok(());
        }
        
        println!("Initializing empty CRL...");
        
        // Load CA cert and key
        let ca_cert_path = Path::new(&self.data_dir).join("ca_cert.pem");
        let ca_cert_pem = fs::read(&ca_cert_path)?;
        let ca_cert = X509::from_pem(&ca_cert_pem)?;
        
        let key_pem = crate::ca::load_encrypted_key(&self.data_dir, passphrase)?;
        let ca_priv = PKey::private_key_from_pem(&key_pem)?;
        
        // Create empty CRL
        let mut crl = X509Crl::builder()?;
        crl.set_issuer_name(ca_cert.subject_name())?;
        
        let now = Asn1Time::days_from_now(0)?;
        let next_update = Asn1Time::days_from_now(7)?; // Update weekly
        
        crl.set_last_update(&now)?;
        crl.set_next_update(&next_update)?;
        
        // Sign the CRL
        crl.sign(&ca_priv, openssl::hash::MessageDigest::sha256())?;
        
        let crl_pem = crl.build().to_pem()?;
        fs::write(crl_path, crl_pem)?;
        
        println!("CRL initialized at {:?}", crl_path);
        Ok(())
    }
    
    /// Add a certificate serial number to the CRL
    pub fn revoke_certificate(&self, passphrase: &str, serial: &str, reason: &str) -> Result<()> {
        let crl_path = Path::new(&self.data_dir).join("ca_crl.pem");
        
        // Load existing CRL
        let existing_crl_pem = fs::read(&crl_path)?;
        let existing_crl = X509Crl::from_pem(&existing_crl_pem)?;
        
        // Load CA cert and key
        let ca_cert_path = Path::new(&self.data_dir).join("ca_cert.pem");
        let ca_cert_pem = fs::read(&ca_cert_path)?;
        let ca_cert = X509::from_pem(&ca_cert_pem)?;
        
        let key_pem = crate::ca::load_encrypted_key(&self.data_dir, passphrase)?;
        let ca_priv = PKey::private_key_from_pem(&key_pem)?;
        
        // Create new CRL with all existing entries plus the new one
        let mut new_crl = X509Crl::builder()?;
        new_crl.set_issuer_name(ca_cert.subject_name())?;
        
        let now = Asn1Time::days_from_now(0)?;
        let next_update = Asn1Time::days_from_now(7)?;
        
        new_crl.set_last_update(&now)?;
        new_crl.set_next_update(&next_update)?;
        
        // Copy existing revoked entries
        for revoked in existing_crl.get_revoked() {
            for entry in revoked {
                new_crl.add_revoked(entry.clone())?;
            }
        }
        
        // Add new revoked certificate
        let serial_bn = BigNum::from_hex_str(serial)?;
        let mut revoked = openssl::x509::X509Revoked::new()?;
        revoked.set_serial_number(serial_bn.to_asn1_integer()?.as_ref())?;
        revoked.set_revocation_date(&now)?;
        
        new_crl.add_revoked(revoked)?;
        
        // Sign the updated CRL
        new_crl.sign(&ca_priv, openssl::hash::MessageDigest::sha256())?;
        
        let crl_pem = new_crl.build().to_pem()?;
        fs::write(crl_path, crl_pem)?;
        
        println!("Certificate {} revoked: {}", serial, reason);
        Ok(())
    }
    
    /// Check if a certificate serial is revoked
    pub fn is_revoked(&self, serial: &str) -> Result<bool> {
        let crl_path = Path::new(&self.data_dir).join("ca_crl.pem");
        
        if !crl_path.exists() {
            return Ok(false);
        }
        
        let crl_pem = fs::read(&crl_path)?;
        let crl = X509Crl::from_pem(&crl_pem)?;
        
        let serial_bn = BigNum::from_hex_str(serial)?;
        let serial_check = serial_bn.to_asn1_integer()?;
        
        if let Some(revoked) = crl.get_revoked() {
            for entry in revoked {
                if entry.serial_number() == serial_check.as_ref() {
                    return Ok(true);
                }
            }
        }
        
        Ok(false)
    }
    
    /// Get list of all revoked serials
    pub fn get_revoked_list(&self) -> Result<Vec<String>> {
        let crl_path = Path::new(&self.data_dir).join("ca_crl.pem");
        
        if !crl_path.exists() {
            return Ok(Vec::new());
        }
        
        let crl_pem = fs::read(&crl_path)?;
        let crl = X509Crl::from_pem(&crl_pem)?;
        
        let mut revoked_list = Vec::new();
        
        if let Some(revoked) = crl.get_revoked() {
            for entry in revoked {
                let serial = entry.serial_number().to_bn()?.to_hex_str()?;
                revoked_list.push(serial.to_string());
            }
        }
        
        Ok(revoked_list)
    }
    
    /// Get CRL PEM content for distribution
    pub fn get_crl_pem(&self) -> Result<Vec<u8>> {
        let crl_path = Path::new(&self.data_dir).join("ca_crl.pem");
        Ok(fs::read(&crl_path)?)
    }
}

/// Track issued certificates for renewal validation
pub struct CertificateRegistry {
    data_dir: String,
}

impl CertificateRegistry {
    pub fn new(data_dir: &str) -> Self {
        CertificateRegistry {
            data_dir: data_dir.to_string(),
        }
    }
    
    /// Record an issued certificate
    pub fn register_certificate(&self, serial: &str, container_name: &str, service_name: &str, issued_at: i64) -> Result<()> {
        let registry_path = Path::new(&self.data_dir).join("cert_registry.json");
        
        // Load existing registry
        let mut registry: serde_json::Value = if registry_path.exists() {
            let content = fs::read_to_string(&registry_path)?;
            serde_json::from_str(&content)?
        } else {
            serde_json::json!({
                "certificates": {}
            })
        };
        
        // Add new certificate entry
        registry["certificates"][serial] = serde_json::json!({
            "container_name": container_name,
            "service_name": service_name,
            "issued_at": issued_at,
            "status": "active"
        });
        
        // Write back
        let json_str = serde_json::to_string_pretty(&registry)?;
        fs::write(registry_path, json_str)?;
        
        Ok(())
    }
    
    /// Verify container name matches certificate on renewal
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
    
    /// Mark certificate as revoked in registry
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
        
        let json_str = serde_json::to_string_pretty(&registry)?;
        fs::write(registry_path, json_str)?;
        
        Ok(())
    }
}
