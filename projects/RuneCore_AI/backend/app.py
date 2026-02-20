#!/usr/bin/env python3
"""
AI Service Backend - RuneCore AI with Multi-Agent Support

Features:
- Async multi-agent processing with per-agent queues
- Conversation caching with Memory Core integration
- Model management through Ollama
- Rate limiting and input sanitization
- Proper error codes following RuneGuard conventions
"""
import os
import json
import requests
import asyncio
import threading
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Optional integration with RuneCore Core for mTLS and service registration
try:
    from shared_utils.core_client import CoreClient
except Exception:
    CoreClient = None

# Import service discovery and integrated mode support
try:
    import service_discovery
except ImportError as e:
    print(f"[WAFX07] Service discovery module not available: {e}")
    service_discovery = None

# Import conversation cache with robust path handling
import sys

# Add backend root and cache directory to sys.path for robust import
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, ".."))
cache_dir = os.path.join(backend_dir, "cache")
for p in [backend_dir, project_root, cache_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

conversation_cache = None
async_agent_manager = None
model_manager = None
rate_limiter = None
input_sanitizer = None

# User profile — always available (graceful fallback if import fails)
try:
    import user_profile as _user_profile_mod
except ImportError:
    _user_profile_mod = None

# Profile curator — background fact extraction after each AI response
try:
    import profile_curator as _curator_mod
except ImportError:
    _curator_mod = None

# CoreMemory bridge — retrieve/store long-term memories (graceful fallback)
try:
    import core_memory_bridge as _cmb
except ImportError:
    _cmb = None

# Try multiple import paths and emit diagnostics if imports fail so
# running containers don't silently fall back to the mock cache.
import importlib
import traceback

def _try_import_modules():
    """Import all required modules with fallback handling"""
    global conversation_cache, async_agent_manager, model_manager, rate_limiter, input_sanitizer

    # Import conversation cache
    cache_candidates = [
        "cache.conversation_cache",
        "conversation_cache",
        "projects.RuneCore_AI.backend.cache.conversation_cache",
    ]
    for mod_name in cache_candidates:
        try:
            mod = importlib.import_module(mod_name)
            cache_obj = getattr(mod, "conversation_cache", None)
            if cache_obj is not None:
                conversation_cache = cache_obj
                print(f"[IABC01] Conversation cache loaded from {mod_name}")
                break
        except Exception as e:
            print(f"[IMPORT_DEBUG] Failed to import {mod_name}: {e}")

    # Import async agent manager
    manager_candidates = [
        "async_agent_manager",
        "projects.RuneCore_AI.backend.async_agent_manager",
    ]
    for mod_name in manager_candidates:
        try:
            mod = importlib.import_module(mod_name)
            mgr = getattr(mod, "async_agent_manager", None)
            if mgr is not None:
                async_agent_manager = mgr
                print(f"[IABA02] Async agent manager loaded from {mod_name}")
                break
        except Exception as e:
            print(f"[IMPORT_DEBUG] Failed to import async_agent_manager from {mod_name}: {e}")

    # Import model manager
    model_candidates = [
        "model_manager",
        "projects.RuneCore_AI.backend.model_manager",
    ]
    for mod_name in model_candidates:
        try:
            mod = importlib.import_module(mod_name)
            mgr = getattr(mod, "model_manager", None)
            if mgr is not None:
                model_manager = mgr
                print(f"[IABM01] Model manager loaded from {mod_name}")
                break
        except Exception as e:
            print(f"[IMPORT_DEBUG] Failed to import model_manager from {mod_name}: {e}")

    # Import security module
    security_candidates = [
        "security",
        "projects.RuneCore_AI.backend.security",
    ]
    for mod_name in security_candidates:
        try:
            mod = importlib.import_module(mod_name)
            rate_limiter = getattr(mod, "rate_limiter", None)
            input_sanitizer = getattr(mod, "input_sanitizer", None)
            if rate_limiter and input_sanitizer:
                print(f"[IABS01] Security module loaded from {mod_name}")
                break
        except Exception as e:
            print(f"[IMPORT_DEBUG] Failed to import security from {mod_name}: {e}")


# Try to import all modules
_try_import_modules()

# Create mock classes for testing environments if imports failed
if conversation_cache is None:
    class MockConversationCache:
        def get_cache_stats(self):
            return {
                "enabled": False,
                "using_redis": False,
                "message_limit": 10,
                "context_size": 5,
            }

        def format_context_for_ai(self, agent_id):
            return []

        def format_chat_history_to_string(self, history):
            if not history:
                return ""
            formatted_lines = []
            for message in history:
                role = message.get("role", "")
                content = message.get("content", "")
                if role == "system":
                    formatted_lines.append(f"System: {content}")
                elif role == "user":
                    formatted_lines.append(f"User: {content}")
                elif role == "assistant":
                    formatted_lines.append(f"Assistant: {content}")
            return "\n\n".join(formatted_lines)

        def get_full_conversation(self, agent_id):
            return []

        def add_conversation(self, agent_id, user_msg, ai_msg):
            pass

        def get_conversation_context(self, agent_id):
            return []

    conversation_cache = MockConversationCache()
    print("[WABC02] Using mock conversation cache")

if async_agent_manager is None:
    class MockAsyncAgentManager:
        async def submit_request(self, agent_id, user_id, message, priority=0, timeout=None):
            return "mock_request_id"

        async def get_response(self, request_id):
            return None

        async def get_request_status(self, request_id):
            return "completed"

        async def start_workers(self):
            pass

        def get_stats(self):
            return {"mock": True}

        def update_agent_config(self, agent_id, config):
            pass

    async_agent_manager = MockAsyncAgentManager()
    print("[WABA01] Using mock async agent manager")

app = Flask(__name__)
CORS(app)

# Database connection (optional, None for now as we use file-based storage)
db = None

# Log which cache implementation is being used
try:
    cache_type = conversation_cache.__class__.__name__
except Exception:
    cache_type = str(type(conversation_cache))
print(f"[RuneCore] Using conversation cache: {cache_type}")

# Configuration
ERRORLOGGER_URL = os.environ.get("ERRORLOGGER_SERVICE_URL", "http://127.0.0.1:5001/log")
OLLAMA_SERVICE_URL = os.environ.get("OLLAMA_SERVICE_URL", "http://127.0.0.1:5002")

# Track background model-pull operations so callers can poll/cancel
# operation_id -> {model, status, started_at, last_checked, error, stop_flag}
MODEL_PULL_STATUS = {}


def start_background_model_pull(model_name, operation_id, poll_interval=2.0):
    """Start a daemon thread that monitors model availability after initiating pull.

    The thread updates MODEL_PULL_STATUS[operation_id] with progress and final state.
    """

    def _worker():
        entry = MODEL_PULL_STATUS.get(operation_id)
        if entry is None:
            return
        # best-effort trigger pull once
        try:
            requests.post(f"{OLLAMA_SERVICE_URL}/api/pull", json={"name": model_name}, timeout=10)
        except Exception:
            pass

        # Poll until model appears or stop flag set
        while True:
            entry = MODEL_PULL_STATUS.get(operation_id)
            if entry is None:
                return
            if entry.get("stop", False):
                entry["status"] = "cancelled"
                entry["last_checked"] = datetime.now().isoformat()
                return
            try:
                mr = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=5)
                if mr.status_code == 200:
                    jr = mr.json()
                    candidates = []
                    raw = jr.get("models") if isinstance(jr, dict) else None
                    if isinstance(raw, list):
                        for m in raw:
                            if isinstance(m, dict) and "name" in m:
                                candidates.append(m["name"])
                            elif isinstance(m, str):
                                candidates.append(m)
                    elif isinstance(jr, list):
                        for m in jr:
                            if isinstance(m, str):
                                candidates.append(m)
                    if model_name in candidates:
                        entry["status"] = "available"
                        entry["last_checked"] = datetime.now().isoformat()
                        return
                    else:
                        entry["status"] = "pulling"
                        entry["last_checked"] = datetime.now().isoformat()
                else:
                    entry["last_checked"] = datetime.now().isoformat()
            except Exception as e:
                entry["error"] = str(e)
                entry["last_checked"] = datetime.now().isoformat()
            time.sleep(poll_interval)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# Pre-defined agent data for fast response
AGENTS_DATA = {
    "agents": [
        {
            "id": "71dc06c0-7b49-4a7d-9afb-a2d7fdcde53b",
            "name": "Gary",
            "avatar_image": None,
            "model_name": "llama3.2:1b",
            "temperature": 0.7,
            "top_p": 0.9,
            "system_prompt": "You are a helpful AI assistant.",
            "max_tokens": 2048,
            "status": "idle",
            "created_at": "2025-10-19T13:10:15.634648+00:00",
            "last_active": "2025-10-19T14:12:06.915751+00:00",
            "metadata": {},
        },
        {
            "id": "3c3f3ac6-8be1-4e97-aec8-e2d529e4b436",
            "name": "Kora",
            "avatar_image": None,
            "model_name": "gemma:2b",
            "temperature": 0.8,
            "top_p": 0.9,
            "system_prompt": "You are a creative AI assistant.",
            "max_tokens": 2048,
            "status": "idle",
            "created_at": "2025-10-19T13:10:20.634648+00:00",
            "last_active": "2025-10-19T14:12:06.915751+00:00",
            "metadata": {},
        },
    ],
    "count": 2,
}

# Agents persistence (simple JSON file) to preserve created agents across restarts
AGENTS_FILE = os.path.join(os.path.dirname(__file__), "agents.json")


def load_agents_from_file():
    global AGENTS_DATA
    try:
        if os.path.exists(AGENTS_FILE):
            with open(AGENTS_FILE, "r", encoding="utf-8") as f:
                AGENTS_DATA = json.load(f)
                print(f"[AGENTS] Loaded {len(AGENTS_DATA.get('agents', []))} agents from {AGENTS_FILE}")
    except Exception as e:
        try:
            print(f"[AGENTS] Failed to load agents file: {e}")
        except Exception:
            pass


def save_agents_to_file():
    try:
        with open(AGENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(AGENTS_DATA, f, default=str)
    except Exception as e:
        try:
            print(f"[AGENTS] Failed to save agents file: {e}")
        except Exception:
            pass


# Load persisted agents if present
load_agents_from_file()


def log_error(error_code, message=None, extra=None):
    """Optimized error logging with minimal overhead"""
    try:
        payload = {
            "error_code": error_code,
            "message": message or error_code,
            "service": "ai_service",
            "extra": extra or {},
        }
        requests.post(ERRORLOGGER_URL, json=payload, timeout=1)
    except (requests.RequestException, requests.Timeout) as e:
        # Fail silently for performance, but emit a brief stderr line for diagnostics
        try:
            import sys

            print(f"[log_error_request_exception] {type(e).__name__}: {str(e)}", file=sys.stderr)
        except Exception:
            pass
            # Also persist a local fallback copy so diagnostics survive restarts when
            # the central ErrorLogger is not available (useful in dev environments).
            try:
                import json as _json
                import os as _os
                from datetime import datetime

                _log_dir = _os.path.join(_os.path.dirname(__file__), "logs")
                _os.makedirs(_log_dir, exist_ok=True)
                _file = _os.path.join(_log_dir, "fallback_errors.jsonl")
                entry = {"timestamp": datetime.now().isoformat(), **payload, "local_fallback": True}
                with open(_file, "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps(entry, separators=(",", ":")))
                    _f.write("\n")
            except Exception:
                pass
    except Exception:
        # Catch any other unexpected errors; print to stderr as a last resort
        try:
            import sys

            print(f"[log_error_exception] {error_code} - {message}", file=sys.stderr)
        except Exception:
            pass  # nosec B110


def maybe_register_with_core():
    """Attempt registration with RuneCore core when RUNECORE_REGISTER_WITH_CORE is set."""
    if not os.environ.get("RUNECORE_REGISTER_WITH_CORE"):
        return
    if CoreClient is None:
        print("CoreClient not available; skipping AI registration")
        return
    try:
        cc = CoreClient(core_url=os.environ.get("RUNECORE_CORE_URL"), disable_mtls=os.environ.get("RUNECORE_DISABLE_MTLS") in ("1","true","True"))
        info = {"name": "AIService", "version": "0.1.0", "rest_url": os.environ.get("AI_SERVICE_URL", "http://127.0.0.1:5000/api/chat")}
        res = cc.register_service(info)
        print(f"Registered AI with core: {res}")
    except Exception as e:
        print(f"Failed to register AI with core: {e}")


@app.route("/api/log-frontend-error", methods=["POST"])
def log_frontend_error():
    """Optimized frontend error logging"""
    try:
        data = request.get_json() or {}
        log_error(
            data.get("error_code", "FRONTEND_ERROR"),
            data.get("message", "Frontend error"),
            {"source": "frontend", **data.get("extra", {})},
        )
        return jsonify({"status": "logged"})
    except Exception as e:
        return jsonify({"error": "Logging failed", "details": str(e)}), 500


@app.route("/api/user/profile", methods=["GET"])
def get_user_profile():
    """Return the current user profile."""
    if _user_profile_mod is None:
        return jsonify({"error": "User profile module unavailable"}), 503
    try:
        return jsonify(_user_profile_mod.load())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/user/profile", methods=["PUT"])
def update_user_profile():
    """Merge partial fields into the user profile and save."""
    if _user_profile_mod is None:
        return jsonify({"error": "User profile module unavailable"}), 503
    try:
        data = request.get_json() or {}
        updated = _user_profile_mod.update(data)
        return jsonify(updated)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents", methods=["GET"])
def get_agents():
    """Agent list retrieval. Prefer database-backed list when available."""
    try:
        if db:
            agents = db.list_agents()
            return jsonify({"agents": agents, "count": len(agents)})
    except Exception as e:
        # Fall back to static data and log
        log_error("EAB#02", str(e))

    return jsonify(AGENTS_DATA)


@app.route("/api/agents", methods=["POST"])
def create_agent():
    """Create a new agent. Accepts JSON or multipart/form-data for avatar uploads."""
    try:
        # Support both JSON and FormData submissions
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            form = request.form
            name = form.get("name", "").strip()
            model_name = form.get("model_name", "llama3.2:1b")
            temperature = float(form.get("temperature", 0.7))
            top_p = float(form.get("top_p", 0.9))
            system_prompt = form.get("system_prompt", "You are a helpful AI assistant.")
            max_tokens = int(form.get("max_tokens", 2048))
            metadata = {}
            if form.get("metadata"):
                try:
                    metadata = json.loads(form.get("metadata"))
                except Exception:
                    metadata = {"raw_metadata": form.get("metadata")}
            avatar = None
            if "avatar_image" in request.files:
                f = request.files["avatar_image"]
                avatar = f.filename or "uploaded"
        else:
            data = request.get_json() or {}
            name = (data.get("name") or "").strip()
            model_name = data.get("model_name", "llama3.2:1b")
            temperature = float(data.get("temperature", 0.7))
            top_p = float(data.get("top_p", 0.9))
            system_prompt = data.get("system_prompt", "You are a helpful AI assistant.")
            max_tokens = int(data.get("max_tokens", 2048))
            metadata = data.get("metadata", {}) or {}
            avatar = data.get("avatar_image") if isinstance(data.get("avatar_image"), str) else None

        if not name:
            return jsonify({"error": "Name is required", "error_code": "E_MISSING_NAME"}), 400

        new_agent = {
            "id": str(uuid.uuid4()),
            "name": name,
            "avatar_image": avatar,
            "model_name": model_name,
            "temperature": temperature,
            "top_p": top_p,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "status": "idle",
            "created_at": datetime.now().isoformat(),
            "last_active": None,
            "metadata": metadata,
        }

        AGENTS_DATA.setdefault("agents", []).append(new_agent)

        # Log creation event
        try:
            log_error("IAB#03", f"Agent created: {new_agent['id']}", {"service": "ai_service", "agent": new_agent['id']})
        except Exception:
            pass

        # Persist agents to disk to survive restarts
        try:
            save_agents_to_file()
        except Exception:
            pass

        return jsonify(new_agent), 201
    except Exception as e:
        log_error("EAB#03", str(e))
        return jsonify({"error": "Failed to create agent", "message": str(e)}), 500


@app.route("/api/cache/stats", methods=["GET"])
def get_cache_stats():
    """Get conversation cache statistics"""
    try:
        stats = conversation_cache.get_cache_stats()
        # Add a friendly suggestion when Redis is not in use
        suggestion = None
        if not stats.get("using_redis") and stats.get("enabled"):
            suggestion = (
                "In-memory conversation cache is active (last "
                f"{stats.get('message_limit', 10)} messages). "
                "For longer-term, shared memory across services, "
                "deploy the Memory Core (Postgres + Redis) and point "
                "the AI service at it."
            )
        core_memory_status = None
        if _cmb is not None:
            core_memory_status = {
                "available": _cmb.is_available(),
                "url": os.environ.get("CORE_MEMORY_URL", "http://core_memory:5003/v1"),
            }
        return jsonify({
            "status": "ok",
            "cache": stats,
            "suggestion": suggestion,
            "core_memory": core_memory_status,
        })
    except Exception as e:
        return jsonify({"error": f"Cache stats failed: {str(e)}"}), 500


@app.route("/api/agents", methods=["POST"])
def create_agent_endpoint():
    """Create a new agent. Uses DB when available, otherwise stores in-memory."""
    try:
        # Accept JSON or form-data
        if request.content_type and "multipart/form-data" in request.content_type:
            form = request.form.to_dict()
            # convert numeric fields if present
            try:
                form["temperature"] = float(form.get("temperature", 0.7))
            except Exception:
                form["temperature"] = 0.7
            try:
                form["top_p"] = float(form.get("top_p", 0.9))
            except Exception:
                form["top_p"] = 0.9
            # metadata may be JSON string
            if "metadata" in form:
                try:
                    import json as _json

                    form["metadata"] = _json.loads(form["metadata"])
                except Exception:
                    pass
            payload = form
        else:
            payload = request.get_json() or {}

        # Basic validation
        if not payload.get("name") or not payload.get("model_name"):
            return (
                jsonify({"error": "Missing required fields: name and model_name"}),
                400,
            )

        if db:
            created = db.create_agent(payload)
            return jsonify(created), 201

        # Fallback: append to AGENTS_DATA in-memory list
        import uuid

        agent_id = str(uuid.uuid4())
        agent = {
            "id": agent_id,
            "name": payload.get("name"),
            "avatar_image": payload.get("avatar_image"),
            "model_name": payload.get("model_name"),
            "temperature": float(payload.get("temperature", 0.7)),
            "top_p": float(payload.get("top_p", 0.9)),
            "system_prompt": payload.get("system_prompt", "You are a helpful AI assistant."),
            "max_tokens": int(payload.get("max_tokens", 2048)),
            "status": "idle",
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "metadata": payload.get("metadata", {}),
        }
        AGENTS_DATA.setdefault("agents", []).insert(0, agent)
        AGENTS_DATA["count"] = len(AGENTS_DATA.get("agents", []))
        return jsonify(agent), 201

    except Exception as e:
        log_error("EAB#03", str(e))
        return jsonify({"error": "Failed to create agent", "details": str(e)}), 500


@app.route("/api/agents/<agent_id>/conversations", methods=["GET"])
def get_agent_conversations(agent_id):
    """Get conversation history for specific agent"""
    try:
        limit = request.args.get("limit", 50, type=int)

        # Get from cache (limited by cache size)
        conversations = conversation_cache.get_full_conversation(agent_id)

        # Format for frontend compatibility; skip malformed entries instead of failing
        formatted_conversations = []
        skipped = 0
        for idx, msg in enumerate(conversations):
            if not isinstance(msg, dict):
                skipped += 1
                continue
            # Safely extract fields with defaults
            cid = msg.get("id") or f"{agent_id}-{idx}"
            user_message = msg.get("user_message") or ""
            ai_response = msg.get("ai_response") or ""
            timestamp = msg.get("timestamp") or datetime.now().isoformat()
            model_used = msg.get("model_used", "cached")

            formatted_conversations.append(
                {
                    "id": cid,
                    "user_message": user_message,
                    "ai_response": ai_response,
                    "timestamp": timestamp,
                    "model_used": model_used,
                    "agent_id": agent_id,
                }
            )

        # Return the most recent `limit` conversations while preserving chronological order
        if limit and len(formatted_conversations) > limit:
            sliced = formatted_conversations[-limit:]
        else:
            sliced = formatted_conversations

        resp = {
            "conversations": sliced,
            "count": len(sliced),
            "source": "local_cache",
        }
        if skipped > 0:
            resp["skipped_malformed"] = skipped

        return jsonify(resp)

    except Exception as e:
        log_error("EABC01", str(e))
        return (
            jsonify(
                {
                    "conversations": [],
                    "count": 0,
                    "error": "Failed to retrieve conversations",
                }
            ),
            500,
        )


@app.route("/api/agents/<agent_id>", methods=["PUT"])
def update_agent(agent_id):
        """Update agent data via DB when available, otherwise update in-memory."""
        try:
            payload = request.get_json() or {}
            if db:
                ok = db.update_agent(agent_id, payload)
                if not ok:
                    return jsonify({"error": "Agent not found"}), 404
                updated = db.get_agent(agent_id)
                return jsonify(updated)

            # Fallback: update in-memory AGENTS_DATA
            agents = AGENTS_DATA.get("agents", [])
            for i, a in enumerate(agents):
                if a.get("id") == agent_id:
                    agents[i] = {**a, **payload}
                    AGENTS_DATA["agents"] = agents
                    save_agents_to_file()
                    return jsonify(agents[i])

            return jsonify({"error": "Agent not found"}), 404
        except Exception as e:
            log_error("EAB#04", str(e))
            return jsonify({"error": "Failed to update agent", "details": str(e)}), 500


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
        """Delete agent and associated data via DB when available, otherwise in-memory."""
        try:
            if db:
                ok = db.delete_agent(agent_id)
                if not ok:
                    return jsonify({"error": "Agent not found"}), 404
                return jsonify({"status": "deleted"})

            agents = AGENTS_DATA.get("agents", [])
            new_agents = [a for a in agents if a.get("id") != agent_id]
            if len(new_agents) == len(agents):
                return jsonify({"error": "Agent not found"}), 404
            AGENTS_DATA["agents"] = new_agents
            AGENTS_DATA["count"] = len(new_agents)
            save_agents_to_file()
            return jsonify({"status": "deleted"})
        except Exception as e:
            log_error("EAB#05", str(e))
            return jsonify({"error": "Failed to delete agent", "details": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Optimized health check"""
    return jsonify(
        {
            "status": "ok",
            "service": "ai_service",
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/internal/dependency_available", methods=["POST"])
def dependency_available():
    """
    Called by Core when a missing dependency becomes available.
    Triggers reconnection and syncs limb mode data if applicable.
    """
    try:
        data = request.get_json() or {}
        service_name = data.get("service_name")
        
        if not service_name:
            return jsonify({"error": "service_name required"}), 400
        
        print(f"[DEPENDENCY] Notified that {service_name} is available")
        
        # If we're in limb mode and service_discovery is available
        if service_discovery and service_discovery.LIMB_MODE:
            # Wait random delay (0-5s) to avoid thundering herd
            import random
            import time
            delay = random.uniform(0, 5)
            print(f"[DEPENDENCY] Waiting {delay:.1f}s before reconnect attempt")
            time.sleep(delay)
            
            # Try to re-register with Core
            try:
                standalone, integrated, limb = service_discovery.detect_mode()
                
                if integrated:
                    # Successfully transitioned to integrated mode!
                    print("[DEPENDENCY] Successfully transitioned to integrated mode")
                    
                    # Sync limb storage to CoreMemoryAPI if it's the Memory service
                    if service_name == "CoreMemoryAPI":
                        limb_storage = service_discovery.get_limb_storage()
                        if limb_storage:
                            # Get all agents with local data
                            all_agents = limb_storage.get_all_agent_ids()
                            synced_count = 0
                            
                            for agent_id in all_agents:
                                conversations = limb_storage.get_last_n_conversations(agent_id, 10)
                                
                                # Send to CoreMemoryAPI via Core proxy
                                try:
                                    memory_url = service_discovery.get_service_url("CoreMemoryAPI")
                                    if memory_url:
                                        # Batch upload conversations
                                        for conv in conversations:
                                            payload = {
                                                "agent_id": agent_id,
                                                "user_message": conv.get("user_message"),
                                                "ai_response": conv.get("ai_response"),
                                                "timestamp": conv.get("timestamp"),
                                                "synced_from_limb": True
                                            }
                                            requests.post(
                                                f"{memory_url}/api/conversations/store",
                                                json=payload,
                                                timeout=10
                                            )
                                        
                                        synced_count += len(conversations)
                                        print(f"[LIMB_SYNC] Synced {len(conversations)} conversations for agent {agent_id}")
                                except Exception as sync_error:
                                    print(f"[LIMB_SYNC] Failed to sync agent {agent_id}: {sync_error}")
                            
                            print(f"[LIMB_SYNC] Total synced: {synced_count} conversations")
                            
                            # Clear local limb storage after successful sync
                            limb_storage.clear_all()
                            
                    # Start heartbeat thread if not already running
                    service_discovery.start_heartbeat_thread()
                    
                    return jsonify({
                        "status": "transitioned_to_integrated",
                        "service": service_name
                    }), 200
                elif limb:
                    print(f"[DEPENDENCY] Still in limb mode after {service_name} available")
                    return jsonify({
                        "status": "still_limb_mode",
                        "service": service_name
                    }), 200
                else:
                    print(f"[DEPENDENCY] Now in standalone mode")
                    return jsonify({
                        "status": "standalone_mode",
                        "service": service_name
                    }), 200
                    
            except Exception as e:
                print(f"[DEPENDENCY] Reconnect failed: {e}")
                return jsonify({
                    "status": "reconnect_failed",
                    "error": str(e)
                }), 500
        else:
            # Not in limb mode, just acknowledge
            return jsonify({
                "status": "acknowledged",
                "service": service_name,
                "current_mode": "integrated" if service_discovery and service_discovery.INTEGRATION_MODE else "standalone"
            }), 200
            
    except Exception as e:
        log_error("EABB08", f"Dependency notification failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat endpoint with conversation cache, rate limiting, and input sanitization"""
    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        agent_id = data.get("agent_id", "assistant-1")

        if not message:
            return jsonify({"error": "Message is required", "error_code": "EABB06"}), 400

        # Rate limiting check
        if rate_limiter:
            allowed, error_msg = rate_limiter.check_rate_limit(agent_id)
            if not allowed:
                log_error("EABS01", error_msg, {"agent_id": agent_id})
                return jsonify({
                    "error": "Rate limit exceeded",
                    "error_code": "EABS01",
                    "message": error_msg,
                }), 429

        # Input sanitization
        if input_sanitizer:
            message, warnings = input_sanitizer.sanitize_message(message)
            for warning in warnings:
                log_error("WABS01", warning, {"agent_id": agent_id})
            if not message:
                return jsonify({"error": "Message is empty after sanitization", "error_code": "EABS02"}), 400

        # Get conversation history as role-based pairs (oldest first)
        history_pairs = conversation_cache.format_context_for_ai(agent_id)

        ai_response = None
        response_mode = "fallback"

        # Diagnostic log: incoming request and cache mode
        try:
            print(f"[CHAT_REQ] agent_id={agent_id} message_preview='{message[:120]}' cache_using_redis={conversation_cache.get_cache_stats().get('using_redis')}")
        except Exception:
            pass
        # Try Ollama service first
        try:
            # Adjust timeout based on message complexity. Make these values
            # configurable via environment variables so long-running prompts
            # can be supported in dev environments.
            try:
                print(f"[CHAT_CTX] history_len={len(history_pairs)} for agent={agent_id}")
            except Exception:
                pass
            message_length = len(message)
            BASE_TIMEOUT = int(os.environ.get("OLLAMA_BASE_TIMEOUT", "20"))
            COMPLEX_TIMEOUT = int(os.environ.get("OLLAMA_COMPLEX_TIMEOUT", "180"))
            # Use complex timeout for longer messages, otherwise base timeout
            complex_timeout = (
                COMPLEX_TIMEOUT
                if message_length > 100 or len(message.split()) > 40
                else BASE_TIMEOUT
            )

            # Reload agents from disk so multi-worker gunicorn stays in sync
            load_agents_from_file()
            # Lookup agent config from AGENTS_DATA
            agent_config = next(
                (a for a in AGENTS_DATA["agents"] if a["id"] == agent_id), None
            )
            model_name = (
                agent_config["model_name"]
                if agent_config and "model_name" in agent_config
                else "llama3.2:1b"
            )
            # Check model availability in Ollama wrapper and apply safeguards.
            # Behavior controlled via env vars:
            # - OLLAMA_AUTO_PULL=1  -> attempt to start a model download asynchronously
            # - OLLAMA_FALLBACK_MODEL=<model> -> use this model if requested model missing
            try:
                try:
                    models_resp = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=5)
                    available_models = []
                    if models_resp.status_code == 200:
                        jr = models_resp.json()
                        # `models` may be a list of strings or dicts depending on wrapper
                        raw = jr.get("models") if isinstance(jr, dict) else None
                        if isinstance(raw, list):
                            for m in raw:
                                if isinstance(m, dict) and "name" in m:
                                    available_models.append(m["name"])
                                elif isinstance(m, str):
                                    available_models.append(m)
                        else:
                            # fallback: flatten any top-level list
                            if isinstance(jr, list):
                                for m in jr:
                                    if isinstance(m, str):
                                        available_models.append(m)
                    else:
                        available_models = []
                except Exception:
                    available_models = []

                if model_name not in available_models:
                    # Model missing — try fallback, or trigger download and optionally wait.
                    fallback = os.environ.get("OLLAMA_FALLBACK_MODEL")
                    auto_pull = os.environ.get("OLLAMA_AUTO_PULL", "1") in ("1", "true", "True")
                    wait_seconds = int(os.environ.get("OLLAMA_AUTO_PULL_WAIT", "60"))
                    poll_interval = float(os.environ.get("OLLAMA_AUTO_PULL_POLL", "2"))

                    if fallback:
                        try:
                            print(f"[AI_MODEL] Requested model '{model_name}' missing; using fallback '{fallback}'")
                        except Exception:
                            pass
                        model_name = fallback
                    elif auto_pull:
                        # Trigger pull synchronously (best-effort) and poll for availability
                        try:
                            print(f"[AI_MODEL] Requested model '{model_name}' missing; triggering pull and waiting up to {wait_seconds}s")
                        except Exception:
                            pass

                        try:
                            requests.post(f"{OLLAMA_SERVICE_URL}/api/pull", json={"name": model_name}, timeout=10)
                        except Exception:
                            # best-effort trigger; continue to polling which will surface failures
                            pass

                        # Poll models endpoint until model appears or short timeout
                        deadline = time.time() + wait_seconds
                        pulled = False
                        while time.time() < deadline:
                            try:
                                mr = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=5)
                                if mr.status_code == 200:
                                    jr = mr.json()
                                    candidates = []
                                    raw = jr.get("models") if isinstance(jr, dict) else None
                                    if isinstance(raw, list):
                                        for m in raw:
                                            if isinstance(m, dict) and "name" in m:
                                                candidates.append(m["name"])
                                            elif isinstance(m, str):
                                                candidates.append(m)
                                    elif isinstance(jr, list):
                                        for m in jr:
                                            if isinstance(m, str):
                                                candidates.append(m)
                                    if model_name in candidates:
                                        pulled = True
                                        break
                            except Exception:
                                pass
                            # Informational log so the request shows progress
                            try:
                                elapsed = int(time.time() - (deadline - wait_seconds))
                                print(f"[AI_MODEL] still pulling '{model_name}' (elapsed {elapsed}s)")
                            except Exception:
                                pass
                            time.sleep(poll_interval)

                        if not pulled:
                            # Start background monitor to continue pulling after the request's short wait
                            operation_id = str(uuid.uuid4())
                            MODEL_PULL_STATUS[operation_id] = {
                                "model": model_name,
                                "status": "pulling",
                                "started_at": datetime.now().isoformat(),
                                "last_checked": None,
                                "error": None,
                                "stop": False,
                            }
                            start_background_model_pull(model_name, operation_id, poll_interval=poll_interval)

                            # Return 202 so UI can poll status or cancel; inform user we're continuing in background
                            user_msg = (
                                f"Requested model '{model_name}' is being downloaded. "
                                f"This request timed out waiting ({wait_seconds}s) but the pull will continue in the background. "
                                f"Poll /api/model_pull_status/{operation_id} or cancel."
                            )
                            return (
                                jsonify(
                                    {
                                        "error": "MODEL_PULL_IN_PROGRESS",
                                        "error_code": "E_MODEL_PULL_IN_PROGRESS",
                                        "message": user_msg,
                                        "response": user_msg,
                                        "operation_id": operation_id,
                                        "estimated_wait": wait_seconds,
                                    }
                                ),
                                202,
                            )
                        else:
                            try:
                                print(f"[AI_MODEL] Model '{model_name}' is now available after pull")
                            except Exception:
                                pass
                    else:
                        error_payload = {
                            "error": "MODEL_MISSING",
                            "error_code": "E_MODEL_MISSING",
                            "message": f"Requested model '{model_name}' is not available on the upstream AI service.",
                        }
                        return jsonify(error_payload), 503
            except Exception as e:
                # If model-check fails, continue and let the retrying call surface the error.
                try:
                    print(f"[AI_MODEL] model availability check failed: {e}")
                except Exception:
                    pass
            temperature = (
                agent_config["temperature"]
                if agent_config and "temperature" in agent_config
                else 0.7
            )
            top_p = (
                agent_config["top_p"]
                if agent_config and "top_p" in agent_config
                else 0.9
            )
            max_tokens = (
                agent_config["max_tokens"]
                if agent_config and "max_tokens" in agent_config
                else 2048
            )
            system_prompt = (
                agent_config["system_prompt"]
                if agent_config and "system_prompt" in agent_config
                else ""
            )

            # Inject user profile context into the system prompt
            if _user_profile_mod is not None:
                try:
                    system_prompt = _user_profile_mod.inject_into_system_prompt(system_prompt)
                except Exception:
                    pass

            # Retrieve relevant long-term memories from CoreMemory (if available)
            memory_block = ""
            if _cmb is not None:
                try:
                    memories = _cmb.get_context(agent_id, message)
                    memory_block = _cmb.build_memory_block(memories)
                except Exception:
                    pass

            # Combine: system prompt + memory block
            final_system = system_prompt
            if memory_block:
                final_system = (memory_block + "\n" + system_prompt) if system_prompt else memory_block

            # Build proper role-based messages array for Ollama /api/chat
            messages = []
            if final_system:
                messages.append({"role": "system", "content": final_system})
            messages.extend(history_pairs)
            messages.append({"role": "user", "content": message})

            payload = {
                "messages": messages,
                "agent_id": agent_id,
                "model_name": model_name,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "timestamp": datetime.now().isoformat(),
            }

            # Debug: log what we're sending to Ollama (truncated for safety)
            try:
                print(
                    f"[AI_DEBUG] Sending to Ollama for agent {agent_id}: "
                    f"messages={len(messages)} system_prompt='{system_prompt[:100]}'"
                )
            except Exception:
                pass

            # Call Ollama synchronously with retries/backoff to handle
            # transient upstream failures in a predictable manner.
            def call_ollama_with_retries(payload, per_request_timeout, max_retries=3):
                attempt = 0
                backoff = 1.0
                last_error = None
                status_code = None
                while attempt < max_retries:
                    attempt += 1
                    try:
                        try:
                            print(f"[AI_CALL] Ollama attempt {attempt}/{max_retries}")
                        except Exception:
                            pass

                        resp = requests.post(
                            f"{OLLAMA_SERVICE_URL}/api/chat",
                            json=payload,
                            timeout=per_request_timeout,
                        )
                        status_code = resp.status_code
                        if resp.status_code == 200:
                            jr = resp.json()
                            return jr.get("response", "No response from AI"), None, 200
                        else:
                            last_error = f"non-200: {resp.status_code} body={resp.text[:300]}"
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                    except requests.exceptions.Timeout as te:
                        last_error = f"timeout: {str(te)}"
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    except requests.RequestException as re:
                        last_error = f"request_exception: {str(re)}"
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    except Exception as e:
                        last_error = f"exception: {str(e)}"
                        time.sleep(backoff)
                        backoff *= 2
                        continue

                return None, last_error or "unknown_error", status_code or 503

            JOIN_TIMEOUT = int(os.environ.get("OLLAMA_JOIN_TIMEOUT", "115"))
            ai_response, error_text, status_code = call_ollama_with_retries(
                payload, per_request_timeout=complex_timeout, max_retries=3
            )

            # Normalize empty responses: empty-string responses should still be
            # visible to users as a placeholder rather than being treated as
            # a complete failure (which previously resulted in no UI text).
            if ai_response is None:
                error_payload = {
                    "error": "OLLAMA_UNAVAILABLE",
                    "error_code": "EABB5",
                    "message": "Upstream AI service unavailable",
                    "details": error_text,
                    "status_code": status_code,
                }
                return (
                    jsonify(error_payload),
                    504 if ("timeout" in (error_text or "").lower()) else 503,
                )
            # If response is an empty string, show a friendly placeholder
            if isinstance(ai_response, str) and ai_response.strip() == "":
                ai_response = "[No response from model]"
            response_mode = "ollama"

        except Exception as e:
            # Log and print the exception for debugging; then return a
            # standardized 503 so the frontend can react to upstream failures.
            log_error("EABB05", str(e))
            try:
                print(f"[AI_EXCEPTION] chat handler exception: {str(e)}")
            except Exception:
                pass

            error_payload = {
                "error": "OLLAMA_UNAVAILABLE",
                "error_code": "EABB5",
                "message": "Upstream AI service unavailable or failed to complete the request",
                "details": str(e),
            }
            return jsonify(error_payload), 503

        try:
            print(f"[CHAT_RESP] agent_id={agent_id} response_preview='{str(ai_response)[:200]}'")
        except Exception:
            pass
        
        # Store conversation in cache (integrated/standalone mode)
        try:
            conversation_cache.add_conversation(agent_id, message, ai_response)
            log_error("IABC02", f"Conversation cached for agent {agent_id}")
        except Exception as cache_error:
            log_error(
                "EABC02", f"Failed to cache conversation: {str(cache_error)}"
            )
            # Continue anyway - caching failure shouldn't break the response
        
        # Store in limb mode local storage if in limb mode
        if service_discovery and service_discovery.LIMB_MODE:
            try:
                limb_storage = service_discovery.get_limb_storage()
                if limb_storage:
                    limb_storage.store_conversation(agent_id, message, ai_response)
                    print(f"[LIMB] Stored conversation for agent {agent_id}")
            except Exception as limb_error:
                log_error("EABB07", f"Failed to store in limb storage: {str(limb_error)}")

        # Fire-and-forget profile curation (rate-limited, non-blocking)
        if _curator_mod is not None:
            try:
                _curator_mod.curate_async(message, ai_response)
            except Exception:
                pass

        # Store conversation turn in CoreMemory for long-term retrieval
        if _cmb is not None:
            try:
                _cmb.store_turn(agent_id, message, ai_response)
            except Exception:
                pass

        # Return response
        return jsonify(
            {
                "response": ai_response,
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
                "mode": response_mode,
                "context_used": len(history_pairs)
                > 0,  # True if there is prior conversation history
                "cached_messages": len(
                    conversation_cache.get_conversation_context(agent_id)
                ),
            }
        )

        try:
            print(f"[CHAT_STORE] stored conversation for agent={agent_id}")
        except Exception:
            pass

    except Exception as e:
        import traceback
        try:
            print(f"[CHAT_OUTER_EXCEPTION] {str(e)}\n{traceback.format_exc()}")
        except Exception:
            pass
        log_error("EABB05", str(e))
        return jsonify({"error": "Chat failed"}), 500


@app.route("/api/debug/payload", methods=["POST"])
def debug_payload():
    """Return the constructed payload for inspection without sending to Ollama"""
    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        agent_id = data.get("agent_id", "assistant-1")

        # Diagnostic: show which cache implementation we're using
        try:
            print(
                f"[DEBUG_PAYLOAD] conversation_cache type: {conversation_cache.__class__.__name__}"
            )
        except Exception:
            pass

        chat_history = conversation_cache.format_context_for_ai(agent_id)
        print(f"[DEBUG_PAYLOAD] raw chat_history before append: {chat_history}")
        chat_history.append({"role": "user", "content": message})
        print(f"[DEBUG_PAYLOAD] chat_history after append: {chat_history}")
        try:
            enhanced_message = conversation_cache.format_chat_history_to_string(
                chat_history
            )
        except Exception as e:
            print(f"[DEBUG_PAYLOAD] format_chat_history_to_string error: {e}")
            enhanced_message = ""

        agent_config = next(
            (a for a in AGENTS_DATA["agents"] if a["id"] == agent_id), None
        )
        system_prompt = (
            agent_config["system_prompt"]
            if agent_config and "system_prompt" in agent_config
            else ""
        )

        return jsonify(
            {
                "agent_id": agent_id,
                "message_preview": enhanced_message[:200],
                "system_prompt": system_prompt,
                "full_message": enhanced_message,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/model_pull_status/<operation_id>", methods=["GET"])
def model_pull_status(operation_id):
    """Return status for a background model-pull operation (operation_id)."""
    entry = MODEL_PULL_STATUS.get(operation_id)
    if not entry:
        return jsonify({"error": "not_found"}), 404
    return jsonify(entry)


@app.route("/api/model_pull_cancel/<operation_id>", methods=["POST"])
def model_pull_cancel(operation_id):
    """Request cancellation of a background model-pull operation."""
    entry = MODEL_PULL_STATUS.get(operation_id)
    if not entry:
        return jsonify({"error": "not_found"}), 404
    entry["stop"] = True
    entry["status"] = "cancelling"
    entry["last_checked"] = datetime.now().isoformat()
    return jsonify({"status": "cancelling", "operation_id": operation_id})


@app.route("/api/cache/raw/<agent_id>", methods=["GET"])
def cache_raw(agent_id):
    """Return raw cached entries for an agent (diagnostic)."""
    try:
        # Attempt to return Redis raw list if available
        if hasattr(conversation_cache, "using_redis") and conversation_cache.using_redis:
            try:
                key = conversation_cache._get_key(agent_id)
                raw = conversation_cache.redis_client.lrange(key, 0, conversation_cache.message_limit - 1)
                return (
                    jsonify({"source": "redis", "raw": raw, "count": len(raw)}),
                    200,
                )
            except Exception as e:
                # Fall through to fallback
                print(f"[cache_raw] redis read failed for {agent_id}: {e}")

        # Fallback: return fallback cache contents
        fallback = []
        try:
            fallback = list(conversation_cache.fallback_cache.get(agent_id, []))
        except Exception as e:
            print(f"[cache_raw] fallback read failed for {agent_id}: {e}")

        return jsonify({"source": "fallback", "raw": fallback, "count": len(fallback)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cache/force_mode", methods=["POST"])
def cache_force_mode():
    """Force conversation cache mode for testing: {"mode": "fallback"|"redis"} """
    try:
        data = request.get_json() or {}
        mode = data.get("mode")
        if mode not in ("fallback", "redis"):
            return jsonify({"error": "mode must be 'fallback' or 'redis'"}), 400

        if mode == "fallback":
            conversation_cache.using_redis = False
            conversation_cache.redis_client = None
            return jsonify({"status": "forced_fallback"}), 200

        # attempt to re-init redis
        try:
            conversation_cache._init_redis()
            return jsonify({"status": "attempted_redis_init", "using_redis": conversation_cache.using_redis}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cache/clear/<agent_id>", methods=["POST"])
def cache_clear_agent(agent_id):
    """Clear conversation cache for given agent (both redis and fallback)."""
    try:
        ok = conversation_cache.clear_agent_cache(agent_id)
        return jsonify({"cleared": bool(ok)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === ASYNC MULTI-AGENT ENDPOINTS ===


@app.route("/api/chat/async", methods=["POST"])
def submit_async_chat():
    """
    Submit a chat request for async processing and return immediately with a tag/request_id
    User can then poll for the response using the request_id
    """
    try:
        data = request.json or {}
        message = data.get("message", "").strip()
        agent_id = data.get("agent_id", "71dc06c0-7b49-4a7d-9afb-a2d7fdcde53b")
        user_id = data.get("user_id", "anonymous")
        priority = data.get("priority", 0)
        timeout = data.get("timeout", 60.0)

        if not message:
            return jsonify({"error": "Message is required", "error_code": "EABB06"}), 400

        # Rate limiting check
        if rate_limiter:
            allowed, error_msg = rate_limiter.check_rate_limit(agent_id)
            if not allowed:
                log_error("EABS01", error_msg, {"agent_id": agent_id})
                return jsonify({
                    "error": "Rate limit exceeded",
                    "error_code": "EABS01",
                    "message": error_msg,
                }), 429

        # Input sanitization
        if input_sanitizer:
            message, warnings = input_sanitizer.sanitize_message(message)
            for warning in warnings:
                log_error("WABS01", warning, {"agent_id": agent_id})
            if not message:
                return jsonify({"error": "Message is empty after sanitization", "error_code": "EABS02"}), 400

        # Update agent config in async manager
        agent_config = next((a for a in AGENTS_DATA["agents"] if a["id"] == agent_id), None)
        if agent_config and async_agent_manager:
            async_agent_manager.update_agent_config(agent_id, agent_config)

        # Submit async request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Start workers if not already running
            loop.run_until_complete(async_agent_manager.start_workers())

            # Submit the request
            request_id = loop.run_until_complete(
                async_agent_manager.submit_request(
                    agent_id=agent_id,
                    user_id=user_id,
                    message=message,
                    priority=priority,
                    timeout=timeout,
                )
            )

            return jsonify(
                {
                    "request_id": request_id,
                    "status": "submitted",
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                    "estimated_time": "30-60 seconds",
                    "poll_url": f"/api/chat/async/{request_id}",
                }
            )

        finally:
            loop.close()

    except Exception as e:
        log_error("EABA07", str(e))
        return jsonify({"error": "Failed to submit async request", "error_code": "EABA07"}), 500


@app.route("/api/chat/async/<request_id>", methods=["GET"])
def get_async_response(request_id):
    """
    Poll for async chat response by request_id (tag)
    Returns response if ready, or status if still processing
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Get response
            response = loop.run_until_complete(
                async_agent_manager.get_response(request_id)
            )

            if response:
                # Response is ready
                return jsonify(
                    {
                        "request_id": request_id,
                        "status": response.status.value,
                        "response": response.response,
                        "agent_id": response.agent_id,
                        "user_id": response.user_id,
                        "timestamp": response.timestamp,
                        "processing_time": response.processing_time,
                        "model_used": response.model_used,
                        "tokens_used": response.tokens_used,
                        "error_message": response.error_message,
                        "ready": True,
                    }
                )
            else:
                # Still processing or not found
                status = loop.run_until_complete(
                    async_agent_manager.get_request_status(request_id)
                )

                if status:
                    return jsonify(
                        {
                            "request_id": request_id,
                            "status": status.value,
                            "ready": False,
                            "message": "Request is still being processed",
                            "poll_again_in": "5-10 seconds",
                        }
                    )
                else:
                    return (
                        jsonify(
                            {
                                "request_id": request_id,
                                "status": "not_found",
                                "ready": False,
                                "error": "Request not found",
                            }
                        ),
                        404,
                    )

        finally:
            loop.close()

    except Exception as e:
        log_error("EABA05", str(e))
        return jsonify({"error": "Failed to get async response"}), 500


@app.route("/api/chat/async/batch", methods=["POST"])
def submit_batch_requests():
    """
    Submit multiple chat requests simultaneously and return request_ids for each
    Enables parallel processing of multiple agents
    """
    try:
        data = request.json
        requests_data = data.get("requests", [])

        if not requests_data:
            return jsonify({"error": "Requests array is required"}), 400

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Start workers if not already running
            loop.run_until_complete(async_agent_manager.start_workers())

            # Submit all requests
            request_ids = []
            for req_data in requests_data:
                message = req_data.get("message", "")
                agent_id = req_data.get(
                    "agent_id", "71dc06c0-7b49-4a7d-9afb-a2d7fdcde53b"
                )
                user_id = req_data.get("user_id", "anonymous")
                priority = req_data.get("priority", 0)

                if message:
                    request_id = loop.run_until_complete(
                        async_agent_manager.submit_request(
                            agent_id=agent_id,
                            user_id=user_id,
                            message=message,
                            priority=priority,
                        )
                    )
                    request_ids.append(
                        {
                            "request_id": request_id,
                            "agent_id": agent_id,
                            "message": (
                                message[:50] + "..." if len(message) > 50 else message
                            ),
                        }
                    )

            return jsonify(
                {
                    "batch_id": str(datetime.now().timestamp()),
                    "request_ids": request_ids,
                    "total_submitted": len(request_ids),
                    "timestamp": datetime.now().isoformat(),
                    "poll_url": "/api/chat/async/batch/status",
                }
            )

        finally:
            loop.close()

    except Exception as e:
        log_error("EABA07", str(e))
        return jsonify({"error": "Failed to submit batch requests"}), 500


@app.route("/api/chat/async/batch/status", methods=["POST"])
def get_batch_status():
    """
    Get status of multiple async requests at once
    Accepts list of request_ids and returns status for each
    """
    try:
        data = request.json
        request_ids = data.get("request_ids", [])

        if not request_ids:
            return jsonify({"error": "request_ids array is required"}), 400

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = []
            for request_id in request_ids:
                # Try to get completed response first
                response = loop.run_until_complete(
                    async_agent_manager.get_response(request_id)
                )

                if response:
                    results.append(
                        {
                            "request_id": request_id,
                            "status": response.status.value,
                            "ready": True,
                            "response": response.response,
                            "processing_time": response.processing_time,
                            "agent_id": response.agent_id,
                        }
                    )
                else:
                    # Check if still processing
                    status = loop.run_until_complete(
                        async_agent_manager.get_request_status(request_id)
                    )
                    results.append(
                        {
                            "request_id": request_id,
                            "status": status.value if status else "not_found",
                            "ready": False,
                            "processing": True if status else False,
                        }
                    )

            # Calculate summary stats
            completed = sum(1 for r in results if r.get("ready", False))
            processing = sum(1 for r in results if r.get("processing", False))
            failed = sum(1 for r in results if r.get("status") in ["failed", "timeout"])

            return jsonify(
                {
                    "results": results,
                    "summary": {
                        "total": len(results),
                        "completed": completed,
                        "processing": processing,
                        "failed": failed,
                        "completion_rate": (
                            f"{(completed/len(results)*100):.1f}%" if results else "0%"
                        ),
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )

        finally:
            loop.close()

    except Exception as e:
        log_error("EABA05", str(e))
        return jsonify({"error": "Failed to get batch status"}), 500


@app.route("/api/chat/async/stats", methods=["GET"])
def get_async_stats():
    """
    Get statistics about the async agent system
    """
    try:
        stats = async_agent_manager.get_stats()
        return jsonify(
            {
                "async_system": stats,
                "cache_system": conversation_cache.get_cache_stats(),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        log_error("EABA07", str(e))
        return jsonify({"error": "Failed to get stats", "error_code": "EABA07"}), 500


# === MODEL MANAGEMENT ENDPOINTS ===


@app.route("/api/models", methods=["GET"])
def list_models():
    """List all available models from Ollama"""
    try:
        if model_manager:
            models = model_manager.list_models()
            return jsonify({
                "models": [{"name": m.name, "size": m.size, "modified_at": m.modified_at} for m in models],
                "count": len(models),
                "timestamp": datetime.now().isoformat(),
            })
        else:
            # Fallback: direct call to ollama service
            try:
                response = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=10)
                if response.status_code == 200:
                    return jsonify(response.json())
                return jsonify({"models": [], "error": "Failed to fetch models"}), 503
            except Exception as e:
                return jsonify({"models": [], "error": str(e), "error_code": "EABM01"}), 503
    except Exception as e:
        log_error("EABM01", str(e))
        return jsonify({"error": "Failed to list models", "error_code": "EABM01"}), 500


@app.route("/api/models/<path:model_name>", methods=["GET"])
def get_model_info(model_name):
    """Get detailed information about a specific model"""
    try:
        # Validate model name
        if input_sanitizer:
            valid, error = input_sanitizer.validate_model_name(model_name)
            if not valid:
                return jsonify({"error": error, "error_code": "EABM05"}), 400

        if model_manager:
            model = model_manager.get_model(model_name)
            if model:
                details = model_manager.get_model_details(model_name)
                return jsonify({
                    "name": model.name,
                    "size": model.size,
                    "modified_at": model.modified_at,
                    "details": details,
                    "available": True,
                })
            return jsonify({"error": "Model not found", "error_code": "EABM04"}), 404
        else:
            return jsonify({"error": "Model manager not available", "error_code": "EABM01"}), 503
    except Exception as e:
        log_error("EABM01", str(e))
        return jsonify({"error": str(e), "error_code": "EABM01"}), 500


@app.route("/api/models/pull", methods=["POST"])
def pull_model():
    """Initiate a model download/pull"""
    try:
        data = request.get_json() or {}
        model_name = data.get("name") or data.get("model")

        if not model_name:
            return jsonify({"error": "Model name is required", "error_code": "EABM05"}), 400

        # Validate model name
        if input_sanitizer:
            valid, error = input_sanitizer.validate_model_name(model_name)
            if not valid:
                return jsonify({"error": error, "error_code": "EABM05"}), 400

        if model_manager:
            status = model_manager.pull_model(model_name)
            return jsonify({
                "model": status.model,
                "status": status.status,
                "progress": status.progress,
                "started_at": status.started_at,
                "message": f"Pull initiated for {model_name}",
            })
        else:
            # Fallback: direct call
            try:
                response = requests.post(
                    f"{OLLAMA_SERVICE_URL}/api/pull",
                    json={"name": model_name},
                    timeout=10
                )
                if response.status_code in (200, 202):
                    return jsonify({"status": "started", "model": model_name})
                return jsonify({"error": "Failed to initiate pull", "error_code": "EABM03"}), 503
            except Exception as e:
                return jsonify({"error": str(e), "error_code": "EABM03"}), 503
    except Exception as e:
        log_error("EABM03", str(e))
        return jsonify({"error": str(e), "error_code": "EABM03"}), 500


@app.route("/api/models/pull/<path:model_name>/status", methods=["GET"])
def get_pull_status(model_name):
    """Get the status of a model pull operation"""
    try:
        if model_manager:
            status = model_manager.get_pull_status(model_name)
            if status:
                return jsonify({
                    "model": status.model,
                    "status": status.status,
                    "progress": status.progress,
                    "started_at": status.started_at,
                    "last_update": status.last_update,
                    "error": status.error,
                })
            return jsonify({"error": "No active pull for this model", "error_code": "WABM03"}), 404
        else:
            return jsonify({"error": "Model manager not available", "error_code": "EABM01"}), 503
    except Exception as e:
        return jsonify({"error": str(e), "error_code": "EABM01"}), 500


@app.route("/api/models/pulls", methods=["GET"])
def list_active_pulls():
    """List all active model pull operations"""
    try:
        if model_manager:
            pulls = model_manager.list_active_pulls()
            return jsonify({
                "pulls": {
                    name: {
                        "status": s.status,
                        "progress": s.progress,
                        "started_at": s.started_at,
                    }
                    for name, s in pulls.items()
                },
                "count": len(pulls),
            })
        else:
            return jsonify({"pulls": {}, "count": 0})
    except Exception as e:
        return jsonify({"error": str(e), "error_code": "EABM01"}), 500


@app.route("/api/models/<path:model_name>", methods=["DELETE"])
def delete_model(model_name):
    """Delete a model from Ollama"""
    try:
        # Validate model name
        if input_sanitizer:
            valid, error = input_sanitizer.validate_model_name(model_name)
            if not valid:
                return jsonify({"error": error, "error_code": "EABM05"}), 400

        if model_manager:
            success = model_manager.delete_model(model_name)
            if success:
                return jsonify({"status": "deleted", "model": model_name})
            return jsonify({"error": "Failed to delete model", "error_code": "EABM02"}), 500
        else:
            return jsonify({"error": "Model manager not available", "error_code": "EABM01"}), 503
    except Exception as e:
        log_error("EABM02", str(e))
        return jsonify({"error": str(e), "error_code": "EABM02"}), 500


@app.route("/api/models/stats", methods=["GET"])
def get_model_stats():
    """Get model manager statistics"""
    try:
        if model_manager:
            return jsonify(model_manager.get_stats())
        return jsonify({"error": "Model manager not available", "error_code": "EABM01"}), 503
    except Exception as e:
        return jsonify({"error": str(e), "error_code": "EABM01"}), 500


# === RATE LIMITING ENDPOINT ===


@app.route("/api/rate_limit/stats", methods=["GET"])
def get_rate_limit_stats():
    """Get rate limiting statistics"""
    try:
        agent_id = request.args.get("agent_id")
        if rate_limiter:
            return jsonify(rate_limiter.get_stats(agent_id))
        return jsonify({"error": "Rate limiter not available"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(
        "🤖 RuneCore AI Service Starting - Multi-Agent System with Model Management"
    )

    # Detect operation mode and register with Core if available
    if service_discovery:
        print("\n🔍 Detecting operation mode...")
        standalone, integrated, limb = service_discovery.detect_mode()
        
        if standalone:
            print("📍 Mode: STANDALONE (no Core integration)")
        elif limb:
            print("⚠️  Mode: LIMB (missing dependencies, using local storage)")
            print(f"💾 Local storage: {service_discovery.LOCAL_DB_PATH}")
        else:
            print("✅ Mode: INTEGRATED (fully connected to Core)")
        
        # Start heartbeat thread if in integrated mode
        if integrated:
            service_discovery.start_heartbeat_thread()
            print("💓 Heartbeat thread started")
    else:
        print("📍 Mode: STANDALONE (service discovery not available)")

    # Print cache configuration
    cache_status = conversation_cache.get_cache_stats()
    print(
        f"\n💾 Cache Status: {'Memory Core Redis' if cache_status['using_redis'] else 'Fallback (in-memory)'}"
    )
    print(f"📝 Message Limit: {cache_status['message_limit']} per agent")
    print(f"🧠 Context Size: {cache_status['context_size']} messages for AI")

    # Print async system info
    async_stats = async_agent_manager.get_stats()
    print(
        f"⚡ Async System: {'Available' if not async_stats.get('mock') else 'Mock Mode'}"
    )

    # Print model manager info
    if model_manager:
        model_stats = model_manager.get_stats()
        print(f"📦 Model Manager: {model_stats['total_models']} models available")
    else:
        print("📦 Model Manager: Using direct Ollama calls")

    # Print security info
    if rate_limiter and input_sanitizer:
        print("🔒 Security: Rate limiting and input sanitization enabled")
    else:
        print("🔒 Security: Basic mode (no rate limiting)")

    port = int(os.environ.get("PORT", 5000))
    print(f"\n🌐 Starting server on port {port}")
    print("")
    print("📡 Available Endpoints:")
    print("  Chat:")
    print("    POST /api/chat - Synchronous chat")
    print("    POST /api/chat/async - Submit async request")
    print("    GET  /api/chat/async/<id> - Poll for response")
    print("    POST /api/chat/async/batch - Submit multiple requests")
    print("  Models:")
    print("    GET  /api/models - List available models")
    print("    POST /api/models/pull - Download a model")
    print("    DELETE /api/models/<name> - Delete a model")
    print("  Agents:")
    print("    GET/POST /api/agents - List/create agents")
    print("    PUT/DELETE /api/agents/<id> - Update/delete agent")
    print("")

    # Attempt registration with RuneCore Core if configured
    maybe_register_with_core()

    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
