# RuneCore_Sentinel

Status: Alpha (design) — skeleton added

Purpose

RuneCore_Sentinel is a lightweight, low-overhead system probe that runs natively on the host (not inside a container). Its responsibility is narrowly scoped: collect reliable, high-frequency system telemetry and deliver it to the RuneCore Memory core for storage and further analysis. The agent is intentionally passive — it observes and reports, it does not perform actions that change system state.

Design contract (short)

- Inputs: native OS metrics (CPU, memory, disk, network, processes, optionally sensors and power/BAT stats) and optionally configured custom probes (log tailing, service heartbeats).
- Outputs: structured telemetry messages (compact binary or JSON) sent to the RuneCore Memory core over a local IPC channel.
- Success criteria: <1% additional CPU overhead on an idle system, sub-second telemetry latency when configured for high-frequency metrics.
- Error modes: degraded connectivity to core (buffer small in-memory ring + persistent spool file), partial metric failures (skip and continue), permission errors (documented and reported back to core as status codes).

IPC & Data format recommendations

- IPC: use platform-appropriate local transport with fallbacks:
  - Linux/macOS: Unix domain socket (file socket) over loopback for very low overhead.
  - Windows: Named pipes or loopback TCP on 127.0.0.1 if pipe restrictions exist.
  - Provide a small adapter in the Memory core to accept either binary frames over socket or JSON lines on a local TCP port.

- Message format:
  - Primary: CBOR or MessagePack for compactness and speed (binary while remaining schema-flexible).
  - Optional: Protobuf if you want strict schema and versioning guarantees.
  - Fallback: newline-delimited JSON for ease of debugging and compatibility with the current JSON messaging pattern in the ecosystem.

Security and permissions

- Run as a dedicated service account with least privileges necessary.
- Use local authentication tokens (signed HMAC) for IPC if the Memory core expects verification of module identity.
- Avoid exposing any network-facing endpoints by default; bind only to local IPC channels.

Integration notes

- Registration: register with the central Service Registry / Core on startup, provide metadata (version, capabilities, pid, platform).
- Health: implement simple health endpoint (eg. local control socket command `STATUS`) and periodic heartbeat messages to the Memory core.
- Backpressure & durability: implement bounded in-memory buffer plus small on-disk ring (spool) when the Memory core is temporarily unavailable.

Deployment

- Ship as a small native binary per platform (Rust/cargo builds). Provide a service unit for systemd (Linux) and instructions for Windows Service via sc.exe or NSSM.
- Configuration: system-local `sentinel.toml` under `/etc/runecore/` (Linux) or `%PROGRAMDATA%\RuneCore\` (Windows) with machine-specific overrides.

Current alpha status

- Design phase: README and initial repository layout created.
- No telemetry collector code included yet in this repo; next step is a minimal Rust prototype that collects CPU and memory and sends JSON over a local socket to a small test memory core stub.

- Skeleton: minimal Rust prototype scaffold added under `projects/RuneCore_Sentinel/`.
- What it contains: Cargo manifest and a small Rust binary that samples CPU/memory, serializes telemetry into CBOR, and writes it to a local IPC endpoint (Unix domain socket on *nix, named pipe on Windows). It also contains a best-effort Core registration call.

What was added (closer to beta)

- Disk spool: failed payloads are persisted on-disk in a per-machine data directory so telemetry is not lost during short outages.
- HTTP fallback: when IPC delivery fails, the agent can forward CBOR payloads to CoreMemory's HTTP API (decoded to JSON when possible) after discovering CoreMemory via the Core service registry.
- Spool flusher: a background thread periodically retries spooled items and forwards them when possible.
- Service discovery: Sentinel queries Core's `/api/v1/services` to find CoreMemory's `rest_url` for HTTP forwarding.
- Error handling: simple best-effort registration and warnings; spool ensures durability.

Notes

- This scaffold uses CBOR for compact binary messages and Unix domain sockets / named pipes for local IPC as you requested. The HTTP fallback sends decoded JSON when possible (or base64-encoded CBOR in metadata) so CoreMemory doesn't need to immediately change.
- Security: registration currently uses a blocking request and accepts invalid TLS certs for simpler local testing; for beta we should enable mTLS / proper CA verification and use signed auth for IPC.
- Production hardening left for next iterations: robust exponential backoff, rate limiting, partial-write handling, permissions/documentation for service accounts, and integration tests.

Next development steps

1. Add a small local receiver/adapter (dev helper) that reads length-prefixed CBOR frames from the IPC endpoint and forwards decoded JSON to CoreMemory for local testing (recommended so CoreMemory doesn't need immediate change).
2. Add systemd unit template and Windows service instructions (packaging). I can add these next.
3. Wire mTLS for Core registration and secure the IPC channel with HMAC tokens.
4. Add integration tests and a small benchmark measuring CPU overhead.

If you want I can implement the dev receiver/adapter and the systemd + Windows service artifacts next. Tell me which you'd prefer to prioritize.

Next steps (suggested)

1. Confirm telemetry shape: which metrics and sampling frequency are required for v0.1.
2. Implement minimal Rust prototype (CPU, memory) and a test stub for Memory core receiver.
3. Add integration tests and resource-usage benchmarks.
4. Create cross-platform packaging scripts and service units.

Open questions for you

- Which OS targets are top priority (Linux distros, Windows versions)?
- Do you want binary-compact messages (CBOR/MessagePack/Protobuf) from the start or prefer JSON for visibility during alpha?
- How will Memory core accept Sentinel data today — is there an agreed IPC (socket, HTTP, WebSocket) used across the ecosystem?
- Do you require any privileged metrics (process list of other users, network packet capture) that would force elevated permissions?

If you want, I can scaffold a minimal Rust prototype (tokio-based) that samples CPU/memory and sends JSON lines over a Unix socket / TCP loopback to a small helper receiver.