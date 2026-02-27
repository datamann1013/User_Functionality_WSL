# RuneCore_Mind — AI Intelligence Module

> **Module:** `RuneCore_Mind` | **Folder:** `projects/RuneCore_AI/`
> **Status:** Active Development — Core features working
> **Branch:** `Integration_before_test`
> **Last Updated:** February 2026

RuneCore_Mind is the AI intelligence module of the RuneCore ecosystem. It provides a multi-agent chat interface backed by locally-running Ollama models, with per-agent conversation history, user profile injection, background memory curation, and graceful integration with the broader RuneCore stack.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser  :3000                                          │
│  React Frontend (Steel Blue UI)                          │
│  ┌──────────────┬────────────────────────────────────┐  │
│  │ Agent Sidebar│ Chat area + Model Manager + Profile │  │
│  └──────────────┴────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ nginx proxy /api/ → :5000
┌──────────────────────▼──────────────────────────────────┐
│  Backend  :5000  (Flask + Gunicorn)                      │
│  app.py — agents, chat, models, user profile             │
│  ├── async_agent_manager.py  (concurrent per-agent queues)│
│  ├── model_manager.py        (Ollama model CRUD)         │
│  ├── conversation_cache.py   (local history, 10 messages)│
│  ├── user_profile.py         (profile storage + inject)  │
│  ├── profile_curator.py      (background fact extraction)│
│  ├── core_memory_bridge.py   (CoreMemory integration)    │
│  ├── service_discovery.py    (standalone/integrated/limb)│
│  └── security.py             (rate limiting, sanitization)│
└──────────────────────┬──────────────────────────────────┘
                       │ http://ollama_wrapper:5002
┌──────────────────────▼──────────────────────────────────┐
│  Ollama Wrapper  :5002  (Flask + Gunicorn, 4 workers)    │
│  ollama_api.py — chat proxy, streaming model pull        │
└──────────────────────┬──────────────────────────────────┘
                       │ http://ollama:11434
┌──────────────────────▼──────────────────────────────────┐
│  Ollama  :11434                                          │
│  Local LLM inference (llama3.2:1b, gemma:2b, etc.)      │
└─────────────────────────────────────────────────────────┘
```

---

## Ports

| Service | Port | Description |
|---------|------|-------------|
| Frontend (nginx) | 3000 | React UI, proxies `/api/` to backend |
| Backend | 5000 | Flask API, direct access |
| Ollama Wrapper | 5002 | HTTP wrapper around Ollama |
| Ollama | 11434 | Local model inference engine |

---

## Quick Start

```bash
# From repository root
bash scripts/start_ai_only.sh
```

The script builds and starts all 4 containers, waits up to 40s for the backend to be ready (it takes ~12s to load), then prints access URLs and health status.

Or manually:

```bash
cd projects/RuneCore_AI
docker compose -f docker-compose.dev.yml up -d --build
```

**Access:**
- UI: http://localhost:3000
- Backend health: http://localhost:5000/health

**Stop:**
```bash
docker compose -f projects/RuneCore_AI/docker-compose.dev.yml down
```

**Logs:**
```bash
docker logs -f runecore_ai-backend-1
docker logs -f runecore_ai-frontend-1
docker logs -f runecore-ollama-wrapper
docker logs -f runecore-ollama
```

---

## Features

### Multi-Agent Chat
- Create agents with a name, avatar, model, system prompt, temperature, top_p, max_tokens
- Each agent has its own independent conversation history
- Agents persist across restarts (stored in `backend/data/agents.json`)
- Discord DM-style UI — agents shown as contacts in a left sidebar
- Unread message badges when a background agent responds
- Markdown rendering in AI responses

### Model Management
- View all locally downloaded models
- Download new models from Ollama (streaming progress, non-blocking)
- Pull any model by name (e.g. `llama3.1:70b`) via the Model Manager modal
- Download triggered correctly — backend initiates pull, Ollama streams progress in background

### User Profile
- Edit your profile (name, role, expertise, tone preferences) via the Settings modal
- Profile is injected into every agent's system prompt as a non-chat context block
- Stored in `backend/data/user_profile.json`, persists across restarts

### Background Profile Curator
- After each AI response, a daemon thread submits the exchange to a small model
- Extracts user facts and silently updates the user profile
- Rate-limited (once per 3 messages per agent) so it doesn't hammer Ollama
- Configurable via `CURATOR_MODEL` env var (defaults to `qwen2:0.5b`)

### Conversation Context
- Last 10 messages kept per agent (configurable via `LOCAL_CACHE_MESSAGE_LIMIT`)
- Role-based message format — sent to Ollama as `[{role, content}]` array
- System prompt prepended as `role: system` on every call

### CoreMemory Bridge
- If RuneCore_Memory is running, conversation history is stored there for cross-session persistence
- Falls back to local in-memory cache if CoreMemory is unavailable
- Automatic reconnect when CoreMemory comes back online

### Service Modes
Detected automatically at startup by `service_discovery.py`:
- **Standalone** — no RuneCore Core or CoreMemory; local cache only
- **Integrated** — registered with RuneCore Core, using CoreMemory
- **Limb** — RuneCore Core temporarily unreachable; writes to local SQLite, syncs when reconnected

---

## Project Structure

```
RuneCore_AI/
├── backend/
│   ├── app.py                    Main Flask API (agents, chat, models, profile)
│   ├── async_agent_manager.py    Concurrent per-agent request queues
│   ├── model_manager.py          Ollama model list, pull, delete
│   ├── service_discovery.py      Mode detection and CoreMemory registration
│   ├── user_profile.py           Profile load/save/update/inject
│   ├── profile_curator.py        Background fact extraction after responses
│   ├── core_memory_bridge.py     CoreMemory REST integration (graceful fallback)
│   ├── security.py               Rate limiting, input sanitization
│   ├── auth.py                   Auth scaffolding (not enforced in dev)
│   ├── error_codes.py            RuneGuard error code definitions
│   ├── cache/
│   │   └── conversation_cache.py Local conversation history (Redis or file fallback)
│   └── data/
│       ├── agents.json           Persisted agent configurations
│       └── user_profile.json     User profile data
├── frontend/
│   ├── src/
│   │   ├── App.jsx               Main React application
│   │   ├── theme.css             Steel Blue industrial theme
│   │   ├── components/
│   │   │   ├── CreateAgentModal.jsx
│   │   │   ├── ModelManager.jsx
│   │   │   └── UserProfileModal.jsx
│   │   └── utils/
│   │       └── errorLogger.js    RuneGuard frontend error reporting
│   └── package.json
├── ollama_service/
│   ├── ollama_api.py             Ollama proxy (chat, streaming pull, health)
│   ├── requirements.txt
│   └── Dockerfile
├── docker/
│   ├── Dockerfile.backend.dev    Backend container (Python 3.11, gunicorn)
│   ├── Dockerfile.frontend       Frontend container (Node build + nginx)
│   └── nginx.conf                nginx: serves React, proxies /api/ to backend
└── docker-compose.dev.yml        Dev stack: backend, frontend, ollama, ollama_wrapper
```

---

## API Reference

### Agents
```
GET    /api/agents                   List all agents
POST   /api/agents                   Create agent (JSON or multipart with avatar)
PUT    /api/agents/{id}              Update agent
DELETE /api/agents/{id}              Delete agent
GET    /api/agents/{id}/conversations Conversation history
```

### Chat
```
POST /api/chat
Body: { agent_id, message, user_id? }
Returns: { response, agent_id, request_id }
```
If the model isn't available locally, the backend triggers a background pull and returns a 202 with a poll URL.

### Models
```
GET  /api/models                          List downloaded models
POST /api/models/pull                     Start model download { name }
GET  /api/models/pull/{name}/status       Pull progress { status, progress% }
GET  /api/models/pulls                    All active pulls
POST /api/model_pull_cancel/{op_id}       Cancel a pull
```

### User Profile
```
GET /api/user/profile     Load profile
PUT /api/user/profile     Update profile (fields merged, not replaced)
```

### Health
```
GET /health               { status: ok, service, timestamp }
```

---

## Configuration (Environment Variables)

Set in `docker-compose.dev.yml` or passed to the container:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_SERVICE_URL` | `http://ollama_wrapper:5002` | Ollama wrapper address |
| `OLLAMA_AUTO_PULL` | `1` | Auto-trigger model download if missing |
| `OLLAMA_AUTO_PULL_WAIT` | `30` | Seconds to wait before returning 202 |
| `LOCAL_CACHE_MESSAGE_LIMIT` | `10` | Messages kept per agent |
| `LOCAL_CACHE_CONTEXT_SIZE` | `5` | Messages sent to model as context |
| `CURATOR_MODEL` | `qwen2:0.5b` | Model used for background fact extraction |
| `PYTHONUNBUFFERED` | `1` | Ensures gunicorn logs appear in docker logs |

---

## Known Behaviour

- **Startup time**: Backend takes ~12 seconds to load (large Python import + Redis probe). The start script retries for 40s.
- **Ollama cold start**: First inference after startup is slower (model loading into VRAM).
- **Model downloads**: Tracked via streaming ndjson from Ollama. Progress visible in Model Manager.
- **CoreMemory offline**: Silently falls back to local 10-message cache. No data loss.
- **Error logging**: Backend sends errors to RuneGuard on port 5001. If RuneGuard isn't running, errors are written to `backend/logs/fallback_errors.jsonl`.

---

## Future Plans

### Councils — Multi-Agent Groups
Planned but not yet implemented. A Council is a named group of agents that work together on a single prompt.

Two modes:

**Orchestrator mode** — one designated lead agent receives the prompt, breaks it into sub-tasks, delegates each to a specialist agent, and synthesises a unified response back to the user. The individual sub-task exchanges are hidden; only the final answer is shown.

**Council mode** — all agents in the group independently answer the same prompt. Their responses are displayed side by side so the user can compare perspectives or approaches. Useful for tasks where multiple valid solutions exist (e.g. ask three code-focused agents to solve the same bug).

Both council types appear in the agent sidebar alongside individual agents, visually distinguished by a group icon and member count.

### Planned Integrations
- **Web search tool** — agents can be given a tool that queries a search engine before responding
- **System action tools** — agents can query RuneCore system state, trigger actions
- **RuneRemote** — control and chat with agents from the phone app
- **Persistent cross-session memory** — requires RuneCore_Memory to be running

---

## RuneCore Integration

RuneCore_Mind registers with RuneCore Core (port 11440, mTLS) when `RUNECORE_REGISTER_WITH_CORE` is set. In standalone mode (default for dev), it runs fully independently.

All errors follow the RuneGuard error code format: `[Type][Origin][Component][Subcomponent][Number]` — see `RuneGuard_Logger/error_codes.py`.
