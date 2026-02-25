# RuneCore_HA — High Availability node for the RuneCore Raft cluster
#
# Reuses the compiled RuneCore_Core binary. No separate Rust build needed.
# Configured via environment variables to run in HA mode (heartbeats + Raft only).
# See docker-compose.dev.yml for runtime configuration.
FROM runecore_core-core:latest

EXPOSE 11442

ENTRYPOINT ["/app/runecore_core"]
