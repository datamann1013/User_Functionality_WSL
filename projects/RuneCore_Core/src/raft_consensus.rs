// Persistent storage for Raft consensus
use raft::prelude::*;
use raft::{Config as RaftConfig, Raft as RaftNode, StateRole};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::sync::mpsc;
use serde::{Deserialize, Serialize};
use anyhow::Result;

use crate::raft_storage::PersistentStorage;

/// Commands that can be applied to the service registry state machine
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RegistryCommand {
    RegisterService {
        name: String,
        version: Option<String>,
        rest_url: Option<String>,
        ws_url: Option<String>,
        dependencies: Vec<String>,
        wishlist: Vec<String>,
        container_name: Option<String>,
    },
    UpdateHeartbeat {
        name: String,
        status: String,
        metadata: Option<serde_json::Value>,
    },
    MarkOffline {
        name: String,
    },
    RemoveService {
        name: String,
    },
}

/// Raft state machine for service registry
#[derive(Debug, Clone)]
pub struct RegistryStateMachine {
    /// Applied service registry state
    services: HashMap<String, ServiceEntry>,
    /// Last applied index
    last_applied: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceEntry {
    pub name: String,
    pub version: Option<String>,
    pub rest_url: Option<String>,
    pub ws_url: Option<String>,
    pub dependencies: Vec<String>,
    pub wishlist: Vec<String>,
    pub container_name: Option<String>,
    pub status: String,
    pub last_seen: i64,
    pub registered_at: i64,
}

impl RegistryStateMachine {
    pub fn new() -> Self {
        RegistryStateMachine {
            services: HashMap::new(),
            last_applied: 0,
        }
    }
    
    /// Apply a command to the state machine
    pub fn apply(&mut self, index: u64, cmd: RegistryCommand) -> Result<serde_json::Value> {
        self.last_applied = index;
        
        match cmd {
            RegistryCommand::RegisterService {
                name,
                version,
                rest_url,
                ws_url,
                dependencies,
                wishlist,
                container_name,
            } => {
                let now = chrono::Utc::now().timestamp();
                let entry = ServiceEntry {
                    name: name.clone(),
                    version,
                    rest_url,
                    ws_url,
                    dependencies: dependencies.clone(),
                    wishlist,
                    container_name,
                    status: if dependencies.is_empty() {
                        "running".to_string()
                    } else {
                        "limb_mode".to_string()
                    },
                    last_seen: now,
                    registered_at: now,
                };
                
                self.services.insert(name.clone(), entry);
                
                Ok(serde_json::json!({
                    "registered": true,
                    "name": name,
                    "status": "running",
                }))
            }
            RegistryCommand::UpdateHeartbeat { name, status, metadata } => {
                if let Some(entry) = self.services.get_mut(&name) {
                    entry.status = status;
                    entry.last_seen = chrono::Utc::now().timestamp();
                    Ok(serde_json::json!({"ok": true}))
                } else {
                    Ok(serde_json::json!({"ok": false, "error": "service not found"}))
                }
            }
            RegistryCommand::MarkOffline { name } => {
                if let Some(entry) = self.services.get_mut(&name) {
                    entry.status = "offline".to_string();
                    Ok(serde_json::json!({"ok": true}))
                } else {
                    Ok(serde_json::json!({"ok": false, "error": "service not found"}))
                }
            }
            RegistryCommand::RemoveService { name } => {
                self.services.remove(&name);
                Ok(serde_json::json!({"ok": true}))
            }
        }
    }
    
    /// Get current registry snapshot
    pub fn snapshot(&self) -> Vec<u8> {
        bincode::serialize(&self.services).unwrap_or_default()
    }
    
    /// Restore from snapshot
    pub fn restore(&mut self, data: &[u8]) -> Result<()> {
        if let Ok(services) = bincode::deserialize(data) {
            self.services = services;
        }
        Ok(())
    }
    
    /// Get all services
    pub fn get_services(&self) -> Vec<ServiceEntry> {
        self.services.values().cloned().collect()
    }
    
    /// Get service by name
    pub fn get_service(&self, name: &str) -> Option<ServiceEntry> {
        self.services.get(name).cloned()
    }
}

/// Raft node manager with persistent storage
pub struct RaftManager {
    node: Arc<Mutex<RaftNode<PersistentStorage>>>,
    state_machine: Arc<Mutex<RegistryStateMachine>>,
    node_id: u64,
    peers: Vec<u64>,
    tick_interval: Duration,
    last_tick: Instant,
    /// Number of log entries between snapshots
    snapshot_interval: u64,
    /// Last index that was snapshotted
    last_snapshot_index: u64,
}

impl RaftManager {
    pub fn new(node_id: u64, peers: Vec<u64>, storage_path: &str) -> Result<Self> {
        let config = RaftConfig {
            id: node_id,
            election_tick: 10,
            heartbeat_tick: 3,
            max_size_per_msg: 1024 * 1024,
            max_inflight_msgs: 256,
            ..Default::default()
        };
        
        // Use persistent storage instead of MemStorage
        let storage = PersistentStorage::new(storage_path)
            .map_err(|e| anyhow::anyhow!("Failed to create persistent storage: {:?}", e))?;
        
        let raft_node = RaftNode::new(&config, storage, &raft::default_logger())?;
        
        // Get snapshot interval from environment or use default (1000 entries)
        let snapshot_interval = std::env::var("RAFT_SNAPSHOT_INTERVAL")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(1000);
        
        Ok(RaftManager {
            node: Arc::new(Mutex::new(raft_node)),
            state_machine: Arc::new(Mutex::new(RegistryStateMachine::new())),
            node_id,
            peers,
            tick_interval: Duration::from_millis(100),
            last_tick: Instant::now(),
            snapshot_interval,
            last_snapshot_index: 0,
        })
    }
    
    /// Start the Raft node as a cluster
    pub fn bootstrap_cluster(&mut self) -> Result<()> {
        let mut conf_change = ConfChange::default();
        conf_change.set_change_type(ConfChangeType::AddNode);
        conf_change.node_id = self.node_id;
        
        let mut node = self.node.lock().unwrap();
        node.apply_conf_change(&conf_change)?;
        
        Ok(())
    }
    
    /// Tick the Raft node (call periodically)
    pub fn tick(&mut self) -> Result<()> {
        if self.last_tick.elapsed() >= self.tick_interval {
            let mut node = self.node.lock().unwrap();
            node.tick();
            self.last_tick = Instant::now();
        }
        Ok(())
    }
    
    /// Propose a command to the Raft cluster
    pub async fn propose(&self, cmd: RegistryCommand) -> Result<serde_json::Value> {
        let data = bincode::serialize(&cmd)?;
        
        let mut node = self.node.lock().unwrap();
        node.propose(vec![], data)?;
        
        // In a real implementation, we would wait for the entry to be committed
        // and then apply it to the state machine. For now, we'll return a placeholder.
        Ok(serde_json::json!({"ok": true, "pending": true}))
    }
    
    /// Process ready events and return messages to send to peers
    pub fn process_ready(&mut self) -> Result<Vec<raft::eraftpb::Message>> {
        let mut node = self.node.lock().unwrap();
        
        if !node.has_ready() {
            return Ok(Vec::new());
        }
        
        let mut ready = node.ready();
        
        // Persist entries and hard state to stable storage
        let storage = node.mut_store();
        
        if !ready.entries().is_empty() {
            storage.append_entries(ready.entries())
                .map_err(|e| anyhow::anyhow!("Failed to append entries: {:?}", e))?;
        }
        
        if let Some(hs) = ready.hs() {
            storage.set_hardstate_persist(hs.clone())
                .map_err(|e| anyhow::anyhow!("Failed to persist hard state: {:?}", e))?;
        }
        
        if !ready.snapshot().is_empty() {
            storage.apply_snapshot_persist(ready.snapshot().clone())
                .map_err(|e| anyhow::anyhow!("Failed to persist snapshot: {:?}", e))?;
        }
        
        // Apply committed entries to state machine
        if !ready.committed_entries().is_empty() {
            let mut state_machine = self.state_machine.lock().unwrap();
            
            for entry in ready.committed_entries() {
                if entry.data.is_empty() {
                    // Empty entry (e.g., from leader election)
                    continue;
                }
                
                if let Ok(cmd) = bincode::deserialize::<RegistryCommand>(&entry.data) {
                    let _ = state_machine.apply(entry.index, cmd);
                }
            }
        }
        
        // Extract messages to send to peers
        let messages = ready.messages().to_vec();
        
        // Advance the Raft node
        let mut light_ready = node.advance(ready);
        
        // Process light ready if needed
        if let Some(commit_idx) = light_ready.commit_index() {
            tracing::debug!("Commit index advanced to {}", commit_idx);
        }
        
        node.advance_apply();
        
        Ok(messages)
    }
    
    /// Check if snapshot should be created and do so if needed
    pub fn maybe_create_snapshot(&mut self) -> Result<()> {
        let node = self.node.lock().unwrap();
        let storage = node.store();
        
        // Get current applied index
        let last_index = storage.last_index()
            .map_err(|e| anyhow::anyhow!("Failed to get last index: {:?}", e))?;
        
        // Check if we should create a snapshot
        let entries_since_snapshot = last_index.saturating_sub(self.last_snapshot_index);
        
        if entries_since_snapshot < self.snapshot_interval {
            return Ok(()); // Not time yet
        }
        
        // Only leader creates snapshots to avoid wasted work
        if node.state != StateRole::Leader {
            return Ok(());
        }
        
        drop(node); // Release lock before snapshot creation
        
        tracing::info!(
            "Creating snapshot at index {} ({} entries since last snapshot)",
            last_index,
            entries_since_snapshot
        );
        
        // Create snapshot from state machine
        let state_machine = self.state_machine.lock().unwrap();
        let snapshot_data = state_machine.snapshot();
        drop(state_machine);
        
        // Create snapshot metadata
        let mut snapshot = Snapshot::default();
        snapshot.set_data(snapshot_data);
        
        let metadata = snapshot.mut_metadata();
        metadata.index = last_index;
        metadata.term = {
            let node = self.node.lock().unwrap();
            let storage = node.store();
            storage.term(last_index)
                .map_err(|e| anyhow::anyhow!("Failed to get term: {:?}", e))?
        };
        
        // Set conf_state
        let conf_state = {
            let node = self.node.lock().unwrap();
            let storage = node.store();
            storage.snapshot(0, 0)
                .map_err(|e| anyhow::anyhow!("Failed to get snapshot: {:?}", e))?
                .get_metadata()
                .get_conf_state()
                .clone()
        };
        metadata.set_conf_state(conf_state);
        
        // Apply snapshot to storage
        let node = self.node.lock().unwrap();
        let storage = node.store();
        storage.apply_snapshot_persist(snapshot.clone())
            .map_err(|e| anyhow::anyhow!("Failed to persist snapshot: {:?}", e))?;
        
        drop(node);
        
        // Compact log entries older than snapshot
        self.compact_log(last_index)?;
        
        self.last_snapshot_index = last_index;
        
        tracing::info!("Snapshot created and log compacted up to index {}", last_index);
        
        Ok(())
    }
    
    /// Compact log entries up to the given index
    fn compact_log(&mut self, compact_index: u64) -> Result<()> {
        let node = self.node.lock().unwrap();
        let storage = node.store();
        
        // Compact removes all entries before compact_index
        storage.compact(compact_index)
            .map_err(|e| anyhow::anyhow!("Failed to compact log: {:?}", e))?;
        
        tracing::debug!("Log compacted up to index {}", compact_index);
        
        Ok(())
    }
    
    /// Process an incoming Raft message from a peer
    pub fn step(&mut self, msg: raft::eraftpb::Message) -> Result<()> {
        let mut node = self.node.lock().unwrap();
        node.step(msg)?;
        Ok(())
    }
    
    /// Check if this node is the leader
    pub fn is_leader(&self) -> bool {
        let node = self.node.lock().unwrap();
        node.state == StateRole::Leader
    }
    
    /// Get leader node ID
    pub fn leader_id(&self) -> u64 {
        let node = self.node.lock().unwrap();
        node.leader_id
    }
    
    /// Get current state machine
    pub fn get_state_machine(&self) -> Arc<Mutex<RegistryStateMachine>> {
        Arc::clone(&self.state_machine)
    }
    
    /// Read from state machine (does not require consensus)
    pub fn read_service(&self, name: &str) -> Option<ServiceEntry> {
        let state_machine = self.state_machine.lock().unwrap();
        state_machine.get_service(name)
    }
    
    /// List all services (read-only)
    pub fn list_services(&self) -> Vec<ServiceEntry> {
        let state_machine = self.state_machine.lock().unwrap();
        state_machine.get_services()
    }
}

/// Raft network message for inter-node communication
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RaftMessage {
    pub from: u64,
    pub to: u64,
    pub message: Vec<u8>,
}

/// Create a Raft manager for a 3-node cluster with persistent storage
pub fn create_three_node_cluster(node_id: u64, storage_path: &str) -> Result<RaftManager> {
    let peers = match node_id {
        1 => vec![2, 3],
        2 => vec![1, 3],
        3 => vec![1, 2],
        _ => return Err(anyhow::anyhow!("Invalid node_id, must be 1, 2, or 3")),
    };
    
    RaftManager::new(node_id, peers, storage_path)
}
