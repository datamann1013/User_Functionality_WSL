// Raft network transport module for inter-node communication
use crate::raft_consensus::RaftManager;
use anyhow::{Context, Result};
use parking_lot::Mutex;
use raft::eraftpb::Message as RaftMessage;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::time::{timeout, Duration};

/// Transport layer for sending Raft messages to peer nodes
#[derive(Clone)]
pub struct RaftTransport {
    /// HTTP client for sending messages
    client: reqwest::Client,
    /// Map of node IDs to their HTTP URLs
    peer_urls: HashMap<u64, String>,
    /// Current node's ID
    node_id: u64,
}

impl RaftTransport {
    /// Create a new Raft transport
    ///
    /// # Arguments
    /// * `node_id` - Current node's ID
    /// * `peer_urls` - Comma-separated list of peer URLs in format "node_id=url,node_id=url"
    ///   Example: "1=http://core_primary:11440,2=http://core_secondary:11441,3=http://runecore_ha:11442"
    pub fn new(node_id: u64, peer_urls_str: &str) -> Result<Self> {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .context("Failed to create HTTP client")?;

        let mut peer_urls = HashMap::new();
        for entry in peer_urls_str.split(',') {
            let parts: Vec<&str> = entry.trim().split('=').collect();
            if parts.len() == 2 {
                if let Ok(id) = parts[0].parse::<u64>() {
                    // Don't include self in peer URLs
                    if id != node_id {
                        peer_urls.insert(id, parts[1].to_string());
                    }
                }
            }
        }

        tracing::info!(
            "Raft transport initialized for node {} with {} peers",
            node_id,
            peer_urls.len()
        );

        Ok(Self {
            client,
            peer_urls,
            node_id,
        })
    }

    /// Send a Raft message to a peer node
    pub async fn send_message(&self, to: u64, msg: &RaftMessage) -> Result<()> {
        let url = match self.peer_urls.get(&to) {
            Some(url) => format!("{}/api/v1/raft/message", url),
            None => {
                tracing::warn!("No URL found for node {}", to);
                return Ok(()); // Not an error - peer might not be configured yet
            }
        };

        // Serialize message with bincode
        let payload = bincode::serialize(msg)
            .context("Failed to serialize Raft message")?;

        // Send with timeout
        let send_future = self.client
            .post(&url)
            .header("Content-Type", "application/octet-stream")
            .body(payload)
            .send();

        match timeout(Duration::from_secs(2), send_future).await {
            Ok(Ok(response)) => {
                if response.status().is_success() {
                    tracing::trace!("Sent Raft message to node {}", to);
                    Ok(())
                } else {
                    tracing::warn!("Failed to send to node {}: HTTP {}", to, response.status());
                    Ok(()) // Don't fail - Raft handles unreachable peers
                }
            }
            Ok(Err(e)) => {
                tracing::warn!("Network error sending to node {}: {}", to, e);
                Ok(()) // Don't fail - Raft handles unreachable peers
            }
            Err(_) => {
                tracing::warn!("Timeout sending message to node {}", to);
                Ok(()) // Don't fail - Raft handles timeouts
            }
        }
    }

    /// Send multiple Raft messages to various peers
    pub async fn send_messages(&self, messages: Vec<RaftMessage>) -> Result<()> {
        if messages.is_empty() {
            return Ok(());
        }

        // Send all messages concurrently
        let mut tasks = Vec::new();
        for msg in messages {
            let to = msg.to;
            let transport = self.clone();
            tasks.push(tokio::spawn(async move {
                transport.send_message(to, &msg).await
            }));
        }

        // Wait for all sends to complete (ignore individual failures)
        for task in tasks {
            let _ = task.await;
        }

        Ok(())
    }
}

/// Handle incoming Raft message from a peer node
pub async fn handle_raft_message(
    raft_manager: Arc<Mutex<RaftManager>>,
    payload: Vec<u8>,
) -> Result<()> {
    // Deserialize message
    let msg: RaftMessage = bincode::deserialize(&payload)
        .context("Failed to deserialize Raft message")?;

    tracing::trace!("Received Raft message from node {}", msg.from);

    // Step the Raft state machine with this message
    {
        let mut manager = raft_manager.lock();
        manager.step(msg)?;
    }

    Ok(())
}

/// Background task to process Raft ready state and send messages
pub async fn raft_network_task(
    raft_manager: Arc<Mutex<RaftManager>>,
    transport: RaftTransport,
) -> Result<()> {
    let mut interval = tokio::time::interval(Duration::from_millis(100));
    let mut snapshot_check_counter = 0u64;

    loop {
        interval.tick().await;

        // Process Raft state machine
        let messages = {
            let mut manager = raft_manager.lock();
            
            // Advance Raft tick
            if let Err(e) = manager.tick() {
                tracing::error!("Raft tick error: {}", e);
                continue;
            }

            // Get ready state and extract messages
            match manager.process_ready() {
                Ok(messages) => messages,
                Err(e) => {
                    tracing::error!("Raft process_ready error: {}", e);
                    continue;
                }
            }
        };

        // Send messages to peers
        if !messages.is_empty() {
            tracing::trace!("Sending {} Raft messages to peers", messages.len());
            if let Err(e) = transport.send_messages(messages).await {
                tracing::error!("Failed to send Raft messages: {}", e);
            }
        }
        
        // Check for snapshot creation every 10 seconds (100 ticks)
        snapshot_check_counter += 1;
        if snapshot_check_counter >= 100 {
            snapshot_check_counter = 0;
            
            let mut manager = raft_manager.lock();
            if let Err(e) = manager.maybe_create_snapshot() {
                tracing::error!("Failed to create snapshot: {}", e);
            }
        }
    }
}
                tracing::error!("Failed to send Raft messages: {}", e);
            }
        }
    }
}
