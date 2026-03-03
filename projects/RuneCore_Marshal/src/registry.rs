use serde::Serialize;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ComponentStatus {
    Unknown,
    Running,
    Stopped,
    Starting,
    Error,
}

#[derive(Debug, Clone, Serialize)]
pub struct ComponentEntry {
    pub name: String,
    pub kind: String,           // "windows_service" | "docker_container" | "process"
    pub status: ComponentStatus,
    pub endpoint: Option<String>,
    pub last_updated: DateTime<Utc>,
    pub error: Option<String>,
}

impl ComponentEntry {
    pub fn new(name: impl Into<String>, kind: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            kind: kind.into(),
            status: ComponentStatus::Unknown,
            endpoint: None,
            last_updated: Utc::now(),
            error: None,
        }
    }

    pub fn set_status(&mut self, status: ComponentStatus) {
        self.status = status;
        self.last_updated = Utc::now();
        self.error = None;
    }

    pub fn set_error(&mut self, err: impl Into<String>) {
        self.status = ComponentStatus::Error;
        self.error = Some(err.into());
        self.last_updated = Utc::now();
    }
}

/// Thread-safe registry of managed components.
#[derive(Clone)]
pub struct Registry(Arc<RwLock<HashMap<String, ComponentEntry>>>);

impl Registry {
    pub fn new() -> Self {
        Self(Arc::new(RwLock::new(HashMap::new())))
    }

    pub fn upsert(&self, entry: ComponentEntry) {
        self.0.write().unwrap().insert(entry.name.clone(), entry);
    }

    pub fn get(&self, name: &str) -> Option<ComponentEntry> {
        self.0.read().unwrap().get(name).cloned()
    }

    pub fn list(&self) -> Vec<ComponentEntry> {
        self.0.read().unwrap().values().cloned().collect()
    }

    pub fn set_status(&self, name: &str, status: ComponentStatus) {
        if let Some(entry) = self.0.write().unwrap().get_mut(name) {
            entry.set_status(status);
        }
    }

    pub fn set_error(&self, name: &str, err: impl Into<String>) {
        if let Some(entry) = self.0.write().unwrap().get_mut(name) {
            entry.set_error(err);
        }
    }

    pub fn set_endpoint(&self, name: &str, endpoint: impl Into<String>) {
        if let Some(entry) = self.0.write().unwrap().get_mut(name) {
            entry.endpoint = Some(endpoint.into());
            entry.last_updated = Utc::now();
        }
    }
}
