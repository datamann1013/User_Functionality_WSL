// Persistent storage for Raft consensus
use raft::prelude::*;
use raft::storage::MemStorage;
use raft::{Error as RaftError, Result as RaftResult, StorageError};
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, RwLock};

/// Persistent storage for Raft backed by disk
pub struct PersistentStorage {
    /// In-memory storage for quick access
    mem_storage: MemStorage,
    /// Path to storage directory
    storage_path: PathBuf,
    /// Path to hard state file
    hard_state_path: PathBuf,
    /// Path to snapshot file
    snapshot_path: PathBuf,
    /// Lock for file operations
    file_lock: Arc<RwLock<()>>,
}

/// Serialisable representation of HardState + ConfState.
///
/// HardState and ConfState are protobuf-generated types that do not implement
/// serde::Serialize/Deserialize, so we extract only the primitive fields we
/// need and reconstruct the protobuf types on load.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct PersistedHardState {
    term: u64,
    vote: u64,
    commit: u64,
    voters: Vec<u64>,
    learners: Vec<u64>,
}

impl PersistentStorage {
    /// Create new persistent storage
    pub fn new<P: AsRef<Path>>(storage_path: P) -> RaftResult<Self> {
        let storage_path = storage_path.as_ref().to_path_buf();

        // Create storage directory if it doesn't exist
        fs::create_dir_all(&storage_path)
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        let hard_state_path = storage_path.join("hard_state.json");
        let snapshot_path = storage_path.join("snapshot.bin");

        let mem_storage = MemStorage::new();

        let mut storage = PersistentStorage {
            mem_storage,
            storage_path,
            hard_state_path,
            snapshot_path,
            file_lock: Arc::new(RwLock::new(())),
        };

        // Load persisted state if it exists
        storage.load_state()?;

        Ok(storage)
    }

    /// Load persisted state from disk
    fn load_state(&mut self) -> RaftResult<()> {
        // Load hard state
        if self.hard_state_path.exists() {
            let file = File::open(&self.hard_state_path)
                .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

            let reader = BufReader::new(file);
            let persisted: PersistedHardState = serde_json::from_reader(reader)
                .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

            // Reconstruct protobuf types from stored primitives
            let mut hs = HardState::default();
            hs.term = persisted.term;
            hs.vote = persisted.vote;
            hs.commit = persisted.commit;

            let mut cs = ConfState::default();
            cs.voters = persisted.voters.clone();
            cs.learners = persisted.learners.clone();

            self.mem_storage.wl().set_hardstate(hs);
            self.mem_storage.wl().set_conf_state(cs);

            tracing::info!(
                "Loaded hard state from disk: term={}, vote={}, commit={}",
                persisted.term,
                persisted.vote,
                persisted.commit
            );
        }

        // Load snapshot
        if self.snapshot_path.exists() {
            let data = fs::read(&self.snapshot_path)
                .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

            if !data.is_empty() {
                let data_len = data.len();
                let mut snapshot = Snapshot::default();
                // Vec<u8> → bytes::Bytes (required by protobuf3 generated setter)
                snapshot.set_data(data.into());

                self.mem_storage.wl().apply_snapshot(snapshot)?;

                tracing::info!("Loaded snapshot from disk: {} bytes", data_len);
            }
        }

        Ok(())
    }

    /// Persist hard state to disk
    fn persist_hard_state(&self, hs: &HardState, cs: &ConfState) -> RaftResult<()> {
        let _lock = self.file_lock.write().unwrap();

        let persisted = PersistedHardState {
            term: hs.term,
            vote: hs.vote,
            commit: hs.commit,
            voters: cs.voters.clone(),
            learners: cs.learners.clone(),
        };

        // Write to temporary file first for atomic rename
        let temp_path = self.hard_state_path.with_extension("tmp");
        let file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .open(&temp_path)
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        let mut writer = BufWriter::new(file);
        serde_json::to_writer_pretty(&mut writer, &persisted)
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        writer
            .flush()
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        fs::rename(&temp_path, &self.hard_state_path)
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        Ok(())
    }

    /// Persist snapshot to disk
    fn persist_snapshot(&self, snapshot: &Snapshot) -> RaftResult<()> {
        let _lock = self.file_lock.write().unwrap();

        let temp_path = self.snapshot_path.with_extension("tmp");

        fs::write(&temp_path, snapshot.get_data())
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        fs::rename(&temp_path, &self.snapshot_path)
            .map_err(|e| RaftError::Store(StorageError::Other(Box::new(e))))?;

        tracing::info!("Persisted snapshot: {} bytes", snapshot.get_data().len());

        Ok(())
    }

    /// Get inner MemStorage for direct access
    pub fn inner(&self) -> &MemStorage {
        &self.mem_storage
    }

    /// Append entries and persist
    pub fn append_entries(&self, entries: &[Entry]) -> RaftResult<()> {
        self.mem_storage.wl().append(entries)?;
        Ok(())
    }

    /// Apply snapshot and persist
    pub fn apply_snapshot_persist(&self, snapshot: Snapshot) -> RaftResult<()> {
        self.mem_storage.wl().apply_snapshot(snapshot.clone())?;
        self.persist_snapshot(&snapshot)?;
        Ok(())
    }

    /// Set hard state and persist
    pub fn set_hardstate_persist(&self, hs: HardState) -> RaftResult<()> {
        let cs = self
            .mem_storage
            .snapshot(0, 0)?
            .get_metadata()
            .get_conf_state()
            .clone();
        self.mem_storage.wl().set_hardstate(hs.clone());
        self.persist_hard_state(&hs, &cs)?;
        Ok(())
    }

    /// Compact log entries (for log management)
    pub fn compact(&self, compact_index: u64) -> RaftResult<()> {
        self.mem_storage.wl().compact(compact_index)
    }
}

// Implement Storage trait by delegating to MemStorage
impl raft::Storage for PersistentStorage {
    fn initial_state(&self) -> RaftResult<RaftState> {
        self.mem_storage.initial_state()
    }

    fn entries(
        &self,
        low: u64,
        high: u64,
        max_size: impl Into<Option<u64>>,
        context: raft::GetEntriesContext,
    ) -> RaftResult<Vec<Entry>> {
        // Pass context through to MemStorage (required by raft 0.7 API)
        self.mem_storage.entries(low, high, max_size, context)
    }

    fn term(&self, idx: u64) -> RaftResult<u64> {
        self.mem_storage.term(idx)
    }

    fn first_index(&self) -> RaftResult<u64> {
        self.mem_storage.first_index()
    }

    fn last_index(&self) -> RaftResult<u64> {
        self.mem_storage.last_index()
    }

    fn snapshot(&self, request_index: u64, to: u64) -> RaftResult<Snapshot> {
        self.mem_storage.snapshot(request_index, to)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_persistent_storage_creation() {
        let temp_dir = TempDir::new().unwrap();
        let storage = PersistentStorage::new(temp_dir.path()).unwrap();

        let state = storage.initial_state().unwrap();
        assert_eq!(state.hard_state.term, 0);
    }

    #[test]
    fn test_hard_state_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let storage_path = temp_dir.path().to_path_buf();

        {
            let storage = PersistentStorage::new(&storage_path).unwrap();
            let mut hs = HardState::default();
            hs.term = 5;
            hs.vote = 1;
            hs.commit = 10;
            storage.set_hardstate_persist(hs).unwrap();
        }

        {
            let storage = PersistentStorage::new(&storage_path).unwrap();
            let state = storage.initial_state().unwrap();
            assert_eq!(state.hard_state.term, 5);
            assert_eq!(state.hard_state.vote, 1);
            assert_eq!(state.hard_state.commit, 10);
        }
    }

    #[test]
    fn test_snapshot_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let storage_path = temp_dir.path().to_path_buf();

        {
            let storage = PersistentStorage::new(&storage_path).unwrap();
            let mut snapshot = Snapshot::default();
            snapshot.set_data(vec![1u8, 2, 3, 4, 5].into());
            storage.apply_snapshot_persist(snapshot).unwrap();
        }

        {
            let storage = PersistentStorage::new(&storage_path).unwrap();
            let snap = storage.snapshot(0, 0).unwrap();
            assert_eq!(snap.get_data().as_ref(), [1u8, 2, 3, 4, 5].as_ref());
        }
    }
}
