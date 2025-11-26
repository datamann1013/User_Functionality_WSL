#!/usr/bin/env python3
"""
AI Service Backend - Optimized with Redis Conversation Cache
"""
import os
import requests
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
# optional integration with core
try:
    from shared_utils.core_client import CoreClient
except Exception:
    CoreClient = None

# Import conversation cache with robust path handling
import sys
import os

# Add backend root and cache directory to sys.path for robust import
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, ".."))
cache_dir = os.path.join(backend_dir, "cache")
for p in [backend_dir, project_root, cache_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

conversation_cache = None
async_agent_manager = None
try:
    from cache.conversation_cache import conversation_cache
    from async_agent_manager import async_agent_manager
except (ModuleNotFoundError, ImportError):
    try:
        from conversation_cache import conversation_cache as _cache
        from async_agent_manager import async_agent_manager as _async_manager

        conversation_cache = _cache
        async_agent_manager = _async_manager
    except (ModuleNotFoundError, ImportError):
        # Create mock classes for testing environments
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
                """
                Minimal string formatter for mock cache so debug payloads include
                the user's message when the real cache implementation isn't available.
                """
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

        class MockAsyncAgentManager:
            async def submit_request(
                self, agent_id, user_id, message, priority=0, timeout=None
            ):
                return "mock_request_id"

            async def get_response(self, request_id):
                return None

            async def get_request_status(self, request_id):
                return "completed"

            async def start_workers(self):
                pass

            def get_stats(self):
                return {"mock": True}

        conversation_cache = MockConversationCache()
        async_agent_manager = MockAsyncAgentManager()

app = Flask(__name__)
CORS(app)

# Log which cache implementation is being used
try:
    cache_type = conversation_cache.__class__.__name__
except Exception:
    cache_type = str(type(conversation_cache))
print(f"[RuneCore] Using conversation cache: {cache_type}")

# Configuration
ERRORLOGGER_URL = os.environ.get("ERRORLOGGER_SERVICE_URL", "http://127.0.0.1:5001/log")
OLLAMA_SERVICE_URL = os.environ.get("OLLAMA_SERVICE_URL", "http://127.0.0.1:5002")

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


@app.route("/api/agents", methods=["GET"])
def get_agents():
    """Fast agent list retrieval - pre-computed data"""
    return jsonify(AGENTS_DATA)


@app.route("/api/cache/stats", methods=["GET"])
def get_cache_stats():
    """Get conversation cache statistics"""
    try:
        stats = conversation_cache.get_cache_stats()
        return jsonify({"status": "ok", "cache": stats})
    except Exception as e:
        return jsonify({"error": f"Cache stats failed: {str(e)}"}), 500


@app.route("/api/agents/<agent_id>/conversations", methods=["GET"])
def get_agent_conversations(agent_id):
    """Get conversation history for specific agent"""
    try:
        limit = request.args.get("limit", 50, type=int)

        # Get from cache (limited by cache size)
        conversations = conversation_cache.get_full_conversation(agent_id)

        # Format for frontend compatibility
        formatted_conversations = []
        for msg in conversations:
            formatted_conversations.append(
                {
                    "id": msg["id"],
                    "user_message": msg["user_message"],
                    "ai_response": msg["ai_response"],
                    "timestamp": msg["timestamp"],
                    "model_used": "cached",  # Placeholder for now
                    "agent_id": agent_id,
                }
            )

        return jsonify(
            {
                "conversations": formatted_conversations[:limit],
                "count": len(formatted_conversations),
                "source": "local_cache",
            }
        )

    except Exception as e:
        log_error("CACHE_ERROR", str(e))
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


@app.route("/api/chat", methods=["POST"])
def chat():
    """Optimized chat endpoint with conversation cache and context"""
    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        agent_id = data.get("agent_id", "assistant-1")

        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Get conversation context from cache as structured format
        chat_history = conversation_cache.format_context_for_ai(agent_id)

        # Add current user message to chat history
        chat_history.append({"role": "user", "content": message})

        # Convert to string format for Ollama
        enhanced_message = conversation_cache.format_chat_history_to_string(
            chat_history
        )

        # Add the assistant prompt at the end
        enhanced_message += "\n\nAssistant:"

        ai_response = None
        response_mode = "fallback"

        # Try Ollama service first
        try:
            # Adjust timeout based on message complexity. Make these values
            # configurable via environment variables so long-running prompts
            # can be supported in dev environments.
            message_length = len(message)
            BASE_TIMEOUT = int(os.environ.get("OLLAMA_BASE_TIMEOUT", "20"))
            COMPLEX_TIMEOUT = int(os.environ.get("OLLAMA_COMPLEX_TIMEOUT", "180"))
            # Use complex timeout for longer messages, otherwise base timeout
            complex_timeout = (
                COMPLEX_TIMEOUT
                if message_length > 100 or len(message.split()) > 40
                else BASE_TIMEOUT
            )

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

                        # Poll models endpoint until model appears or timeout
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
                            time.sleep(poll_interval)

                        if not pulled:
                            error_payload = {
                                "error": "MODEL_MISSING",
                                "error_code": "E_MODEL_MISSING_PULL_TIMEOUT",
                                "message": f"Requested model '{model_name}' is not yet available; we are still attempting to download it. Press cancel in the UI to stop attempts.",
                            }
                            return jsonify(error_payload), 503
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

            payload = {
                "message": enhanced_message,
                "agent_id": agent_id,
                "model_name": model_name,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "system_prompt": system_prompt,
                "timestamp": datetime.now().isoformat(),
            }

            # Debug: log what we're sending to Ollama (truncated for safety)
            try:
                print(
                    f"[AI_DEBUG] Sending to Ollama for agent {agent_id}: message_preview='{enhanced_message[:200]}' system_prompt='{system_prompt[:200]}'"
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

            if ai_response:
                response_mode = "ollama"
            else:
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

        except Exception as e:
            # Log and print the exception for debugging; then return a
            # standardized 503 so the frontend can react to upstream failures.
            log_error("OLLAMA_ERROR", str(e))
            log_error("OLLAMA_CONNECTION_ERROR", str(e))
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

        # Store conversation in cache
        try:
            conversation_cache.add_conversation(agent_id, message, ai_response)
            log_error("CACHE_SUCCESS", f"Conversation cached for agent {agent_id}")
        except Exception as cache_error:
            log_error(
                "CACHE_ERROR", f"Failed to cache conversation: {str(cache_error)}"
            )
            # Continue anyway - caching failure shouldn't break the response

        # Return response
        return jsonify(
            {
                "response": ai_response,
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
                "mode": response_mode,
                "context_used": len(chat_history)
                > 2,  # More than just system + current message
                "cached_messages": len(
                    conversation_cache.get_conversation_context(agent_id)
                ),
            }
        )

    except Exception as e:
        log_error("CHAT_ERROR", str(e))
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


# === ASYNC MULTI-AGENT ENDPOINTS ===


@app.route("/api/chat/async", methods=["POST"])
def submit_async_chat():
    """
    Submit a chat request for async processing and return immediately with a tag/request_id
    User can then poll for the response using the request_id
    """
    try:
        data = request.json
        message = data.get("message", "")
        agent_id = data.get("agent_id", "71dc06c0-7b49-4a7d-9afb-a2d7fdcde53b")
        user_id = data.get("user_id", "anonymous")
        priority = data.get("priority", 0)
        timeout = data.get("timeout", 60.0)

        if not message:
            return jsonify({"error": "Message is required"}), 400

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
        log_error("ASYNC_CHAT_SUBMIT_ERROR", str(e))
        return jsonify({"error": "Failed to submit async request"}), 500


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
        log_error("ASYNC_CHAT_GET_ERROR", str(e))
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
        log_error("ASYNC_BATCH_SUBMIT_ERROR", str(e))
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
        log_error("ASYNC_BATCH_STATUS_ERROR", str(e))
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
        log_error("ASYNC_STATS_ERROR", str(e))
        return jsonify({"error": "Failed to get stats"}), 500


if __name__ == "__main__":
    print(
        "🤖 AI Service Backend Starting with Redis Conversation Cache & Async Multi-Agent System"
    )

    # Print cache configuration
    cache_status = conversation_cache.get_cache_stats()
    print(
        f"💾 Cache Status: {'Redis' if cache_status['using_redis'] else 'Fallback Dict'}"
    )
    print(f"📝 Message Limit: {cache_status['message_limit']} per agent")
    print(f"🧠 Context Size: {cache_status['context_size']} messages for AI")

    # Print async system info
    async_stats = async_agent_manager.get_stats()
    print(
        f"⚡ Async System: {'Available' if not async_stats.get('mock') else 'Mock Mode'}"
    )

    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting server on port {port}")
    print("📡 Async Endpoints Available:")
    print("   POST /api/chat/async - Submit async request (returns request_id)")
    print("   GET  /api/chat/async/<request_id> - Poll for response")
    print("   POST /api/chat/async/batch - Submit multiple requests")
    print("   POST /api/chat/async/batch/status - Check batch status")
    print("   GET  /api/chat/async/stats - System statistics")

    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
