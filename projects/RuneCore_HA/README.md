# RuneCore_HA - High Availability Node

## Overview
RuneCore_HA serves as the third node in the Raft consensus cluster, providing:
- Quorum for leader election (odd number of nodes)
- Automatic failover capability
- Read replica for load distribution
- Service registry replication

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ core_primary │ ←→  │core_secondary│ ←→  │ runecore_ha  │
│   (Node 1)   │     │   (Node 2)   │     │   (Node 3)   │
│   Leader     │     │  Follower    │     │  Follower    │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Responsibilities

1. **Raft Participant**: Votes in leader elections, maintains log replica
2. **Failover Node**: Can become leader if primary and secondary fail
3. **Quorum Provider**: Ensures 2-of-3 quorum for consensus
4. **Health Monitor**: Tracks cluster health and reports anomalies

## Configuration

### Environment Variables
```bash
RAFT_NODE_ID=3
RAFT_PEER_URLS=https://core_primary:11440,https://core_secondary:11441
RUNECORE_DATA_DIR=/data
RUNECORE_CA_PASSPHRASE=<from-secrets>
```

### Network
- On `core_ha_bridge` network (accessible by core_primary and core_secondary)
- Does NOT handle client requests (no public network access)
- Peer-to-peer Raft communication only

## Implementation Status

**Phase 4 (Current)**: Basic Raft integration in Core
- [x] Raft dependency added
- [x] State machine implemented
- [x] Leader election logic
- [ ] RuneCore_HA component (THIS)
- [ ] Network messaging between nodes
- [ ] Snapshot support
- [ ] Recovery from failure

**Next Steps**:
1. Create RuneCore_HA Rust project (copy from RuneCore_Core)
2. Configure as Raft follower (node_id=3)
3. Add peer discovery
4. Test 3-node cluster formation
5. Test failover scenarios

## Deployment

Currently RuneCore_HA is a **stub** - it will be fully implemented in Phase 4 completion.

For now, Core operates in:
- **Raft Disabled Mode**: Direct database writes (current default)
- **Raft Enabled Mode**: Set `RUNECORE_ENABLE_RAFT=true` (experimental)

## Testing

### Manual 3-Node Test
```bash
# Start all three nodes
docker-compose up core_primary core_secondary runecore_ha

# Check leader election
docker exec core_primary curl -k https://localhost:11440/api/v1/raft/status

# Stop primary, verify secondary becomes leader
docker stop core_primary
sleep 10
docker exec core_secondary curl -k https://localhost:11440/api/v1/raft/status
```

### Quorum Test
```bash
# Stop 2 nodes (lose quorum)
docker stop core_primary core_secondary

# Verify no leader elected (1 node cannot form quorum)
docker exec runecore_ha curl -k https://localhost:11440/api/v1/raft/status
```

## Differences from Core

| Feature | core_primary | core_secondary | runecore_ha |
|---------|-------------|----------------|-------------|
| Handles client requests | ✅ Yes | ✅ Yes | ❌ No |
| Participates in Raft | ✅ Yes | ✅ Yes | ✅ Yes |
| Can be leader | ✅ Yes | ✅ Yes | ✅ Yes |
| Public network | ✅ Yes | ✅ Yes | ❌ No |
| Certificate authority | ✅ Yes | ❌ No (uses primary's CA) | ❌ No |
| Service proxy | ✅ Yes | ✅ Yes | ❌ No |

## Future Enhancements

- **Automatic Recovery**: Restart failed nodes automatically
- **Split-Brain Prevention**: Network partition detection
- **Dynamic Membership**: Add/remove nodes without downtime
- **Read Scaling**: Distribute read queries across all nodes
- **Geo-Replication**: Deploy nodes in different regions

## References

- [Raft Consensus Algorithm](https://raft.github.io/)
- [tikv/raft-rs Documentation](https://docs.rs/raft/)
- [RuneCore Architecture](../ARCHITECTURE_IMPLEMENTATION_STATUS.md)
