//! Native-service PKI registry.
//!
//! Manages one-time bootstrap tokens that allow native (non-container) services
//! to obtain a cert from the RuneCore CA without already holding a client cert.
//!
//! Flow:
//!   install_service.ps1  →  POST /api/v1/pki/native/register  → gets bootstrap_token
//!   runecore_marshal.exe --bootstrap  →  POST /api/v1/pki/native/issue  → gets signed cert
//!
//! Tokens expire after 15 minutes and are consumed on first use.

use anyhow::{anyhow, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, fs, path::Path};

#[derive(Serialize, Deserialize, Clone)]
pub struct NativeServiceRecord {
    pub cn: String,
    /// SHA-256 hex of the registered binary (for audit; future validation).
    pub binary_hash: String,
    /// One-time bootstrap token. Cleared after use.
    pub bootstrap_token: Option<String>,
    /// Unix timestamp after which the token is invalid.
    pub token_expires: Option<i64>,
    /// Whether a cert has been issued for this record.
    pub cert_issued: bool,
    pub registered_at: i64,
}

pub struct NativePkiRegistry {
    data_dir: String,
}

impl NativePkiRegistry {
    pub fn new(data_dir: &str) -> Self {
        Self { data_dir: data_dir.to_string() }
    }

    fn registry_path(&self) -> std::path::PathBuf {
        Path::new(&self.data_dir).join("native_pki_registry.json")
    }

    fn load(&self) -> HashMap<String, NativeServiceRecord> {
        fs::read_to_string(self.registry_path())
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }

    fn save(&self, registry: &HashMap<String, NativeServiceRecord>) -> Result<()> {
        let json = serde_json::to_string_pretty(registry)?;
        fs::write(self.registry_path(), json)?;
        Ok(())
    }

    /// Register a native service with its binary hash.
    /// Returns a one-time bootstrap token valid for 15 minutes.
    /// Re-registering the same CN replaces the previous record.
    pub fn register(&self, cn: &str, binary_hash: &str) -> Result<String> {
        let mut registry = self.load();
        let token = uuid::Uuid::new_v4().to_string();
        let expires = Utc::now().timestamp() + 15 * 60;

        registry.insert(cn.to_string(), NativeServiceRecord {
            cn: cn.to_string(),
            binary_hash: binary_hash.to_string(),
            bootstrap_token: Some(token.clone()),
            token_expires: Some(expires),
            cert_issued: false,
            registered_at: Utc::now().timestamp(),
        });

        self.save(&registry)?;
        Ok(token)
    }

    /// Validate and consume a bootstrap token.
    /// Returns the stored binary_hash on success; errors on unknown CN, bad token, or expiry.
    pub fn validate_and_consume_token(&self, cn: &str, token: &str) -> Result<String> {
        let mut registry = self.load();

        let record = registry.get_mut(cn)
            .ok_or_else(|| anyhow!("unknown native service CN: {}", cn))?;

        let stored = record.bootstrap_token.as_deref()
            .ok_or_else(|| anyhow!("no active bootstrap token for '{}'", cn))?;

        if stored != token {
            return Err(anyhow!("invalid bootstrap token for '{}'", cn));
        }
        if Utc::now().timestamp() > record.token_expires.unwrap_or(0) {
            return Err(anyhow!("bootstrap token for '{}' has expired", cn));
        }

        let binary_hash = record.binary_hash.clone();

        // Consume — token is one-time use
        record.bootstrap_token = None;
        record.token_expires = None;
        record.cert_issued = true;

        self.save(&registry)?;
        Ok(binary_hash)
    }
}
