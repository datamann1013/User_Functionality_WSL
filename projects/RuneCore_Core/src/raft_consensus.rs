// Raft consensus state machine for the RuneCore service registry
use raft::prelude::*;
use raft::{Config as RaftConfig, StateRole};
use raft::raw_node::RawNode;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
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

/// In-memory state machine for the service registry
#[derive(Debug, Clone)]
pub struct RegistryStateMachine {
    services: HashMap<String, ServiceEntry>,
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
                Ok(serde_json::json!({ "registered": true, "name": name }))
            }
            RegistryCommand::UpdateHeartbeat { name, status, metadata: _ } => {
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

    /// Serialise registry state for snapshotting
    pub fn snapshot(&self) -> Vec<u8> {
        bincode::serialize(&self.services).unwrap_or_default()
    }

    /// Restore from a snapshot
    pub fn restore(&mut self, data: &[u8]) -> Result<()> {
        if let Ok(services) = bincode::deserialize(data) {
            self.services = services;
        }
        Ok(())
    }

    pub fn get_services(&self) -> Vec<ServiceEntry> {
        self.services.values().cloned().collect()
    }

    pub fn get_service(&self, name: &str) -> Option<ServiceEntry> {
        self.services.get(name).cloned()
    }
}

/// Raft node manager with persistent storage
///
/// Uses `RawNode<PersistentStorage>` (the public raft-rs API) rather than
/// the internal `Raft<T>` type.  Methods like `has_ready`, `ready`,
/// `advance`, and `advance_apply` are only available on `RawNode`.
pub struct RaftManager {
    node: Arc<Mutex<RawNode<PersistentStorage>>>,
    state_machine: Arc<Mutex<RegistryStateMachine>>,
    node_id: u64,
    peers: Vec<u64>,
    tick_interval: Duration,
    last_tick: Instant,
    /// Number of log entries between automatic snapshots
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

        let storage = PersistentStorage::new(storage_path)
            .map_err(|e| anyhow::anyhow!("Failed to create persistent storage: {:?}", e))?;

        // RawNode::new — this is the correct public entry point in raft-rs 0.7
        let raft_node = RawNode::new(&config, storage, &raft::default_logger())?;

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

    /// Bootstrap the cluster by applying an initial conf change for this node
    pub fn bootstrap_cluster(&mut self) -> Result<()> {
        let mut conf_change = ConfChange::default();
        conf_change.set_change_type(ConfChangeType::AddNode);
        conf_change.node_id = self.node_id;

        let mut node = self.node.lock().unwrap();
        node.apply_conf_change(&conf_change)?;

        Ok(())
    }

    /// Advance the Raft logical clock (call periodically)
    pub fn tick(&mut self) -> Result<()> {
        if self.last_tick.elapsed() >= self.tick_interval {
            let mut node = self.node.lock().unwrap();
            node.tick();
            self.last_tick = Instant::now();
        }
        Ok(())
    }

    /// Propose a command through Raft consensus (synchronous — no async work needed)
    pub fn propose(&self, cmd: RegistryCommand) -> Result<serde_json::Value> {
        let data = bincode::serialize(&cmd)?;

        let mut node = self.node.lock().unwrap();
        node.propose(vec![], data)?;

        // In a full implementation we would wait for the entry to be committed.
        Ok(serde_json::json!({"ok": true, "pending": true}))
    }

    /// Process the Raft ready state and return messages to send to peers.
    ///
    /// The storage borrow (`node.raft.store()`) must be released before calling
    /// `node.advance(ready)`, which requires a mutable borrow of `node`.
    /// We use an explicit block `{ ... }` to drop the storage reference first.
    pub fn process_ready(&mut self) -> Result<Vec<raft::eraftpb::Message>> {
        let mut node = self.node.lock().unwrap();

        if !node.has_ready() {
            return Ok(Vec::new());
        }

        let mut ready = node.ready();

        // ── Persist phase ────────────────────────────────────────────────────
        // `node.raft.store()` borrows `node` immutably.  We drop it before
        // calling `node.advance(ready)` which needs a mutable borrow.
        {
            let storage = node.raft.store();

            if !ready.entries().is_empty() {
                storage
                    .append_entries(ready.entries())
                    .map_err(|e| anyhow::anyhow!("Failed to append entries: {:?}", e))?;
            }

            if let Some(hs) = ready.hs() {
                storage
                    .set_hardstate_persist(hs.clone())
                    .map_err(|e| anyhow::anyhow!("Failed to persist hard state: {:?}", e))?;
            }

            if !ready.snapshot().is_empty() {
                storage
                    .apply_snapshot_persist(ready.snapshot().clone())
                    .map_err(|e| anyhow::anyhow!("Failed to persist snapshot: {:?}", e))?;
            }
        } // storage borrow dropped here

        // ── Apply committed entries to state machine ─────────────────────────
        if !ready.committed_entries().is_empty() {
            let mut state_machine = self.state_machine.lock().unwrap();

            for entry in ready.committed_entries() {
                if entry.data.is_empty() {
                    continue;
                }
                if let Ok(cmd) = bincode::deserialize::<RegistryCommand>(&entry.data) {
                    let _ = state_machine.apply(entry.index, cmd);
                }
            }
        }

        // ── Extract outgoing messages ─────────────────────────────────────────
        let messages = ready.messages().to_vec();

        // ── Advance Raft state machine ────────────────────────────────────────
        let light_ready = node.advance(ready);

        if let Some(commit_idx) = light_ready.commit_index() {
            tracing::debug!("Commit index advanced to {}", commit_idx);
        }

        node.advance_apply();

        Ok(messages)
    }

    /// Create a snapshot if enough entries have accumulated since the last one
    pub fn maybe_create_snapshot(&mut self) -> Result<()> {
        let last_index;
        let is_leader;

        {
            let node = self.node.lock().unwrap();
            let storage = node.raft.store();

            last_index = storage
                .last_index()
                .map_err(|e| anyhow::anyhow!("Failed to get last index: {:?}", e))?;

            is_leader = node.raft.state == StateRole::Leader;
        } // lock released

        let entries_since_snapshot = last_index.saturating_sub(self.last_snapshot_index);
        if entries_since_snapshot < self.snapshot_interval {
            return Ok(());
        }

        // Only the leader creates snapshots
        if !is_leader {
            return Ok(());
        }

        tracing::info!(
            "Creating snapshot at index {} ({} entries since last snapshot)",
            last_index,
            entries_since_snapshot
        );

        let snapshot_data = {
            let state_machine = self.state_machine.lock().unwrap();
            state_machine.snapshot()
        };

        // Build the Snapshot protobuf
        let mut snapshot = Snapshot::default();
        snapshot.set_data(snapshot_data.into()); // Vec<u8> → bytes::Bytes

        let (term, conf_state) = {
            let node = self.node.lock().unwrap();
            let storage = node.raft.store();

            let term = storage
                .term(last_index)
                .map_err(|e| anyhow::anyhow!("Failed to get term: {:?}", e))?;

            let conf_state = storage
                .snapshot(0, 0)
                .map_err(|e| anyhow::anyhow!("Failed to get snapshot: {:?}", e))?
                .get_metadata()
                .get_conf_state()
                .clone();

            (term, conf_state)
        };

        {
            let metadata = snapshot.mut_metadata();
            metadata.index = last_index;
            metadata.term = term;
            metadata.set_conf_state(conf_state);
        }

        {
            let node = self.node.lock().unwrap();
            let storage = node.raft.store();
            storage
                .apply_snapshot_persist(snapshot)
                .map_err(|e| anyhow::anyhow!("Failed to persist snapshot: {:?}", e))?;
        }

        self.compact_log(last_index)?;
        self.last_snapshot_index = last_index;

        tracing::info!("Snapshot created and log compacted up to index {}", last_index);
        Ok(())
    }

    /// Compact log entries up to the given index
    fn compact_log(&mut self, compact_index: u64) -> Result<()> {
        let node = self.node.lock().unwrap();
        let storage = node.raft.store();
        storage
            .compact(compact_index)
            .map_err(|e| anyhow::anyhow!("Failed to compact log: {:?}", e))?;
        tracing::debug!("Log compacted up to index {}", compact_index);
        Ok(())
    }

    /// Step the Raft state machine with an incoming message from a peer
    pub fn step(&mut self, msg: raft::eraftpb::Message) -> Result<()> {
        let mut node = self.node.lock().unwrap();
        node.step(msg)?;
        Ok(())
    }

    /// Returns true if this node is currently the Raft leader
    pub fn is_leader(&self) -> bool {
        let node = self.node.lock().unwrap();
        node.raft.state == StateRole::Leader
    }

    /// Returns the node ID of the current Raft leader
    pub fn leader_id(&self) -> u64 {
        let node = self.node.lock().unwrap();
        node.raft.leader_id
    }

    pub fn get_state_machine(&self) -> Arc<Mutex<RegistryStateMachine>> {
        Arc::clone(&self.state_machine)
    }

    pub fn read_service(&self, name: &str) -> Option<ServiceEntry> {
        let state_machine = self.state_machine.lock().unwrap();
        state_machine.get_service(name)
    }

    pub fn list_services(&self) -> Vec<ServiceEntry> {
        let state_machine = self.state_machine.lock().unwrap();
        state_machine.get_services()
    }
}

/// Raft network message wrapper (used for inter-node serialisation via protobuf)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RaftMessage {
    pub from: u64,
    pub to: u64,
    pub message: Vec<u8>,
}

/// Construct a RaftManager for a 3-node cluster with persistent storage
pub fn create_three_node_cluster(node_id: u64, storage_path: &str) -> Result<RaftManager> {
    let peers = match node_id {
        1 => vec![2, 3],
        2 => vec![1, 3],
        3 => vec![1, 2],
        _ => return Err(anyhow::anyhow!("Invalid node_id, must be 1, 2, or 3")),
    };

    RaftManager::new(node_id, peers, storage_path)
}
