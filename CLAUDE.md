# RuneCore Ecosystem

Personal computing ecosystem: makes all devices (PC, phone, tablet, servers) into one coherent sphere.
Personal project with serious long-term ambitions (potential company, potential OS base).
**Security-first** — cross-device VPN, hosted servers, and restricted systems are part of the vision.

## Value Points

- **One Core, many limbs**: every service registers with RuneCore_Core (service registry + PKI + Raft consensus + cross-VLAN proxy). Services keep working in degraded "limb mode" (local SQLite fallback) when Core is unreachable.
- **Security by default**: Core runs its own CA; mTLS between services in prod; Docker network VLANs isolate databases and AI internals; native Windows daemon (Marshal) uses DPAPI-encrypted keys + CN-based RBAC.
- **Local-first AI**: all inference local (Ollama + ONNX/DirectML for NPU). No cloud dependency.
- **Observability built-in**: all services log errors to RuneGuard_Logger with structured error codes; Sentinel collects host telemetry; Insight collects container metrics; Dashboard visualizes.

## Naming Convention

| Prefix | Domain |
|---|---|
| `RuneCore_*` | central components (Core, Mind, Memory, HA) |
| `RuneGuard_*` | security/guarding (Logger, Insight, Dashboard) |
| `RuneMesh_*` | cross-device connectivity (Drop) |
| `RunePulse_*` | monitoring/health UI |
| `RuneRemote_*` | remote/mobile control (planned) |

Note: folder `projects/RuneCore_AI/` = module **RuneCore_Mind**.

## Module Map

| Folder (under `projects/`) | Module | Stack | Port(s) | Status |
|---|---|---|---|---|
| `RuneCore_Core/` | RuneCore Foundation | Rust/Axum | 11440 (HTTPS mTLS), 11441 (internal HTTP proxy) | Running healthy |
| `RuneCore_HA/` | HA Raft node | Rust (reuses Core image, `RUNECORE_HA_MODE=1`) | 11442 | Running healthy |
| `RuneCore_AI/` | RuneCore_Mind | Python/Flask backend + React frontend + ollama_wrapper + onnx_service | 5000 backend, 3000 frontend, 5002 wrapper, 5006 onnx | Running healthy |
| `RuneCore_Memory/` | CoreMemory | Python/FastAPI + Postgres/Redis/InfluxDB | 5010 (dev DB ports: 15432/16379/18086) | Running healthy, most mature |
| `RuneGuard_Logger/` | RuneGuard | Python/Flask | 5001 | Running healthy |
| `RuneGuard_Insight/` | Container metrics collector | Python daemon (docker.sock) | — | New |
| `RuneGuard_Dashboard/` | Dashboard | FastAPI + React/Vite | 5004 backend, 3001 frontend | New |
| `RuneMesh_Drop/` | RuneDrop file transfer | Rust/Actix | 5100 host → 5010 container | Prototype |
| `RuneCore_Sentinel/` | Host telemetry daemon | Rust (native Windows, no container) | IPC/CBOR → CoreMemory | Alpha |
| `RuneCore_Marshal/` | Native Windows host-action daemon | Rust, NSSM service | 11443 (HTTPS mTLS), 11444 (localhost tray) | Built, service installed |
| `RuneDev_Code/` | CLI coding agent + MCP server | Rust | stdio | Built (`target/release/runecode.exe`) |
| `shared_utils/` | Python foundation lib (`CoreClient`, constants) | Python | — | Implemented (NOT a stub) |
| `hidden_toolbar/` | RunePulse GTK toolbar | Python/GTK | — | **Deprecated, being removed — ignore** |

Other ports: 11434 Ollama (internal, ai_net only).

## Network Architecture (Docker VLANs)

```
runecore_dev            ← Core, HA, Logger, Dashboard backend, Insight, Mesh_Drop
runecore_ai_net         ← ollama, ollama_wrapper, ai_backend, frontend
runecore_memory_net     ← postgres, redis, influx, core_memory
runecore_dashboard_net  ← dashboard backend + frontend
```
- **Core joins all main nets** → acts as bridge/firewall between VLANs.
- Cross-VLAN calls go through Core proxy: `http://runecore_core:11441/api/proxy/{ServiceName}/{path}` (e.g. `/api/proxy/CoreMemoryAPI/...`).
- Python services register + heartbeat to Core on **11441 (plain HTTP, dev)**; prod uses 11440 HTTPS mTLS. Env: `RUNECORE_CORE_URL=http://runecore_core:11441`.
- Databases (postgres/redis/influx/ollama) fully isolated in their VLANs.
- Raft cluster: node 1 = runecore_core:11440 (primary), node 3 = runecore_ha:11442 (`RUNECORE_HA_MODE=1`), node 2 = stub. `RUNECORE_ENABLE_RAFT=true`, `RAFT_NODE_ID`, `RAFT_PEER_URLS`.

## How to Run

- **Per-module dev**: each module has `docker-compose.dev.yml` using **external networks** — pre-create networks first (or use `scripts/start_system.sh`, which orchestrates everything).
- **Full stack**: `docker/docker-compose.unified.yml` is the canonical orchestrator (10 services, healthchecks, mTLS cert volume).
- Dev disables mTLS: `RUNECORE_DISABLE_MTLS=1`.
- AI stack: `cd projects/RuneCore_AI && docker compose -f docker-compose.dev.yml up -d --build` (ONNX/NPU service needs `--profile npu`).
- Sentinel + Marshal are **native Windows** (not containerized). Marshal installs via `install_service.ps1` (NSSM).

## Branch Model

```
module branch (e.g. RuneCore_AI) → Integration_before_test → BETA → main
```
`main` = last stable snapshot (old). `Integration_before_test` = staging for integrated work.

## Conventions

- **Error codes**: `[Type][Origin][Component][Subcomponent][Number]` — defined in `projects/RuneGuard_Logger/error_codes.py` (and per-module `error_codes.py`).
- **Error logging**: POST to RuneGuard on port 5001 (`/log`).
- **Core registration**: reuse `projects/shared_utils/core_client.py` (`CoreClient.register_service`, `sign_csr`) — do not reinvent.
- **Tests**: pytest (Python), `cargo test` (Rust). CI: 8 GitHub workflows incl. CodeQL/Semgrep/TruffleHog/Gitleaks/Trivy.
- **Config**: TOML per module (Rust); env vars via compose (Python).

## Key Architecture Decisions

- **Databases belong to CoreMemory only.** RuneCore_Mind uses in-memory/file fallback cache — no Redis/Postgres of its own.
- **UI direction**: native compiled apps (Rust/C++) preferred long-term, NOT Electron/web wrappers. React frontends are interim.
- **Sentinel feeds data, RunePulse displays it** (Sentinel = daemon, RunePulse = widget).
- **Docker Compose is the deployment backbone** (Windows + Linux; Mac future).
- **Hardware-adaptive AI tiers**: NPU (ONNX orchestrator) / dGPU (heavy codegen) / iGPU (tool tasks) — Phase 1 implemented (onnx_service, port 5006).

## Planned / Not Started

RuneRemote (phone app), StudyBuddy (ESP32 companion), RuneEnv, RuneLab, RuneForge (Q2 2026).
