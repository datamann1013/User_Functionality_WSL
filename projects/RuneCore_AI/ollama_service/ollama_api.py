#!/usr/bin/env python3
"""
Ollama API Service
Merged optimized features and dev-debug helpers into single entrypoint.

Features:
- Pull/download orchestration with background CLI fallback and progress tracking
- Robust `/api/generate` retries with backoff and diagnostic logs
- CORS fallback for constrained environments
"""
import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify

try:
    from flask_cors import CORS
except Exception:
    # Provide a no-op CORS for constrained environments
    def CORS(app, *args, **kwargs):
        return None

import json
import subprocess
import threading
import re
import time as _time

# App setup
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ollama_service")

# Configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "llama3.2:1b")

# Cache for Ollama status
_ollama_cache = {"status": None, "last_check": 0}

# Track active model pulls and progress
_active_pulls = {}
_active_pulls_lock = threading.Lock()

# ONNX backend integration
ONNX_SERVICE_URL = os.environ.get("ONNX_SERVICE_URL", "")
ONNX_REQUEST_TIMEOUT = int(os.environ.get("ONNX_REQUEST_TIMEOUT", "120"))
_onnx_models: dict = {}
_onnx_models_lock = threading.Lock()
_onnx_available = False

# Marshal integration — native host action daemon
MARSHAL_URL = os.environ.get("MARSHAL_URL", "")
MARSHAL_CERT_PATH = os.environ.get("MARSHAL_CERT_PATH", "")
MARSHAL_KEY_PATH  = os.environ.get("MARSHAL_KEY_PATH", "")
MARSHAL_CA_PATH   = os.environ.get("MARSHAL_CA_PATH", "")
MARSHAL_AUTO_SETUP = os.environ.get("MARSHAL_AUTO_SETUP", "").lower() in ("1", "true", "yes")
CORE_MEMORY_URL = os.environ.get("CORE_MEMORY_URL", "")

# Routing table populated by Marshal's /api/setup response
# key: component name (e.g. "ollama-gpu0"), value: endpoint URL
_marshal_endpoints: dict = {}
_marshal_endpoints_lock = threading.Lock()


def get_ollama_status():
    """Cached Ollama status check"""
    now = datetime.now().timestamp()
    if now - _ollama_cache["last_check"] > 30:  # Cache for 30 seconds
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
            if response.status_code == 200:
                models = [m.get("name") for m in response.json().get("models", [])]
                _ollama_cache["status"] = {
                    "running": True,
                    "models_available": models,
                    "last_check": datetime.now().isoformat(),
                }
            else:
                logger.warning("Ollama /api/tags returned %s", response.status_code)
                _ollama_cache["status"] = {
                    "running": False,
                    "models_available": [],
                    "last_check": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.exception("Failed to contact Ollama: %s", e)
            _ollama_cache["status"] = {
                "running": False,
                "models_available": [],
                "last_check": datetime.now().isoformat(),
            }
        _ollama_cache["last_check"] = now
    return _ollama_cache["status"]


def _fetch_onnx_models() -> list:
    """Fetch models from the ONNX service and update the internal registry.

    Sets _onnx_available based on connectivity. Safe to call from a background thread.
    Returns list of model dicts or empty list if ONNX service is unavailable.
    """
    global _onnx_available
    if not ONNX_SERVICE_URL:
        return []
    try:
        r = requests.get(f"{ONNX_SERVICE_URL}/api/models", timeout=5)
        if r.status_code == 200:
            raw = r.json().get("models", [])
            models = []
            for m in raw:
                entry = m if isinstance(m, dict) else {"name": m}
                entry["backend"] = "onnx"
                models.append(entry)
            with _onnx_models_lock:
                _onnx_models.clear()
                for m in models:
                    _onnx_models[m["name"]] = m
            _onnx_available = True
            logger.info("ONNX service: %d model(s) registered", len(models))
            return models
        logger.warning("ONNX service /api/models returned %s", r.status_code)
        _onnx_available = False
        return []
    except Exception as e:
        logger.warning("ONNX service unavailable: %s", e)
        _onnx_available = False
        return []


def _is_onnx_model(model_name: str) -> bool:
    """Return True if model_name is served by the ONNX backend."""
    with _onnx_models_lock:
        return model_name in _onnx_models


def _route_chat_to_onnx(model_name: str, messages: list, temperature: float = 0.7, max_tokens: int = 512) -> dict:
    """Send a chat request to the ONNX service.

    Returns dict: {response, model_id, backend}.
    Raises requests.RequestException on network failure, HTTPError on non-200.
    """
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = requests.post(
        f"{ONNX_SERVICE_URL}/api/chat",
        json=payload,
        timeout=ONNX_REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    result = r.json()
    content = result.get("message", {}).get("content", "")
    return {"response": content, "model_id": model_name, "backend": "onnx"}


def _spawn_ollama_pull(name):
    """Spawn a background 'ollama pull' process if available."""
    def _runner(model_name):
        try:
            # Mark started
            with _active_pulls_lock:
                _active_pulls[model_name] = {
                    "model": model_name,
                    "status": "running",
                    "progress": 0,
                    "started_at": datetime.now().isoformat(),
                    "last_update": datetime.now().isoformat(),
                    "output": "",
                }

            proc = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            percent_re = re.compile(r"(\d{1,3})%")
            for line in proc.stdout:
                try:
                    with _active_pulls_lock:
                        entry = _active_pulls.get(model_name)
                        if entry is None:
                            entry = {
                                "model": model_name,
                                "status": "running",
                                "progress": 0,
                                "started_at": datetime.now().isoformat(),
                                "last_update": datetime.now().isoformat(),
                                "output": "",
                            }
                            _active_pulls[model_name] = entry
                        entry["output"] += line
                        entry["last_update"] = datetime.now().isoformat()
                        m = percent_re.search(line)
                        if m:
                            try:
                                p = int(m.group(1))
                                entry["progress"] = max(0, min(100, p))
                            except Exception:
                                pass
                except Exception:
                    logger.exception("Error updating pull progress for %s", model_name)

            rc = proc.wait()
            with _active_pulls_lock:
                entry = _active_pulls.get(model_name)
                if entry:
                    entry["last_update"] = datetime.now().isoformat()
                    if rc == 0:
                        entry["status"] = "completed"
                        entry["progress"] = 100
                    else:
                        entry["status"] = "failed"
        except Exception:
            try:
                logger.exception("Background ollama pull failed for %s", model_name)
            except Exception:
                pass
        finally:
            # Invalidate cache so callers see new model list on next check
            try:
                _ollama_cache["last_check"] = 0
            except Exception:
                pass

    th = threading.Thread(target=_runner, args=(name,), daemon=True)
    th.start()


def download_model_via_ollama(name):
    """Initiate a model pull via Ollama's REST API.

    Uses stream=True so requests returns as soon as response headers arrive,
    without waiting for the full download to complete. A background thread
    reads the ndjson progress stream and updates _active_pulls.

    Returns True if the pull was successfully initiated.
    """
    pull_url = f"{OLLAMA_HOST}/api/pull"

    def _stream_reader(model_name, response):
        """Read the streaming pull response and track aggregate progress.

        Ollama reports progress per-layer (each layer has its own total/completed).
        Computing per-layer percentage causes the display to jump back toward 0
        whenever a new layer starts. Instead, we accumulate bytes across all layers
        so progress is always a fraction of the total bytes downloaded vs. total
        bytes to download — monotonically increasing throughout the pull.
        """
        # digest -> total bytes for that layer
        layer_totals: dict = {}
        # digest -> bytes downloaded so far for that layer
        layer_completed: dict = {}

        try:
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                    digest = data.get("digest")
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)

                    # Only count layers that report a real size
                    if digest and total > 0:
                        layer_totals[digest] = total
                        layer_completed[digest] = completed

                    # Aggregate progress across all layers seen so far
                    grand_total = sum(layer_totals.values())
                    grand_completed = sum(layer_completed.values())
                    if grand_total > 0:
                        # Cap at 99 until Ollama sends "success" — layers finishing
                        # doesn't mean the model is fully written and ready.
                        progress = min(int(grand_completed / grand_total * 100), 99)
                    else:
                        progress = 0

                    with _active_pulls_lock:
                        entry = _active_pulls.get(model_name)
                        if entry is None:
                            return
                        entry["last_update"] = datetime.now().isoformat()
                        # Belt-and-suspenders: never display lower than what we showed before
                        entry["progress"] = max(entry.get("progress", 0), progress)
                        if "error" in data:
                            entry["status"] = "failed"
                            entry["error"] = data["error"]
                        elif data.get("status") == "success":
                            entry["status"] = "completed"
                            entry["progress"] = 100
                        else:
                            entry["status"] = "running"
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Stream reader error for %s: %s", model_name, e)
            with _active_pulls_lock:
                entry = _active_pulls.get(model_name)
                if entry:
                    entry["status"] = "failed"
                    entry["error"] = str(e)
        finally:
            try:
                response.close()
            except Exception:
                pass
            _ollama_cache["last_check"] = 0  # Invalidate model cache on completion

    try:
        r = requests.post(
            pull_url,
            json={"name": name},
            stream=True,
            timeout=15,  # Only for connection + first byte; rest is read in thread
        )
        if r.status_code not in (200, 202):
            logger.warning("Ollama /api/pull returned HTTP %s for %s", r.status_code, name)
            return False

        with _active_pulls_lock:
            _active_pulls[name] = {
                "model": name,
                "status": "running",
                "progress": 0,
                "started_at": datetime.now().isoformat(),
                "last_update": datetime.now().isoformat(),
                "output": "",
            }

        th = threading.Thread(target=_stream_reader, args=(name, r), daemon=True)
        th.start()
        return True

    except Exception as e:
        logger.warning("Failed to initiate pull for %s: %s", name, e)
        return False


@app.route("/health", methods=["GET"])
def health():
    """Fast health check with cached status"""
    status = get_ollama_status()
    return jsonify(
        {
            "status": "ok",
            "service": "ollama_service",
            "timestamp": datetime.now().isoformat(),
            "ollama_status": status,
        }
    )


@app.route("/api/models", methods=["GET"])
def get_models():
    """Get available models from Ollama and ONNX service."""
    status = get_ollama_status()
    # Ollama models as dicts (frontend already normalizes via m?.name)
    unified = [{"name": n, "backend": "ollama"} for n in status["models_available"]]
    # Merge ONNX models — skip errored or still-downloading entries
    with _onnx_models_lock:
        for entry in _onnx_models.values():
            if entry.get("status") not in ("error", "downloading", "queued"):
                unified.append(dict(entry))
    return jsonify(
        {
            "models": unified,
            "running": status["running"],
            "last_check": status["last_check"],
            "onnx_available": _onnx_available,
        }
    )


@app.route("/api/onnx/refresh", methods=["POST"])
def onnx_refresh():
    """Manually refresh the ONNX model cache from the ONNX service."""
    models = _fetch_onnx_models()
    return jsonify({"onnx_models": len(models), "available": _onnx_available})


@app.route("/api/marshal/setup", methods=["POST"])
def marshal_setup():
    """Trigger Marshal auto-setup manually (same as startup auto-setup).

    Useful from CLI or web UI to re-run hardware setup after config changes.
    """
    if not MARSHAL_URL:
        return jsonify({"error": "MARSHAL_URL not configured"}), 503
    threading.Thread(target=_call_marshal_setup, daemon=True).start()
    return jsonify({"status": "started", "marshal_url": MARSHAL_URL})


@app.route("/api/marshal/endpoints", methods=["GET"])
def marshal_endpoints():
    """Return the current hardware endpoint routing table from Marshal."""
    with _marshal_endpoints_lock:
        return jsonify({"endpoints": dict(_marshal_endpoints), "marshal_available": bool(MARSHAL_URL)})


@app.route("/api/pull", methods=["POST"])
def pull_model():
    """Trigger a model pull/download. Accepts JSON {"name": "model_name"}.

    Returns 200 if initiated (not necessarily completed).
    """
    try:
        data = request.get_json() or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "Model name required"}), 400

        initiated = download_model_via_ollama(name)
        if initiated:
            return jsonify({"status": "started", "model": name}), 200
        else:
            return jsonify({"error": "Failed to initiate model download"}), 503
    except Exception as e:
        logger.exception("/api/pull failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/models/download/<path:model>", methods=["POST"])
def download_model_route(model):
    """Compatibility route used by frontend ModelManager"""
    try:
        name = model
        initiated = download_model_via_ollama(name)
        if initiated:
            return jsonify({"status": "started", "model": name}), 200
        return jsonify({"error": "Failed to initiate model download"}), 503
    except Exception as e:
        logger.exception("/api/models/download failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/pulls", methods=["GET"])
def list_pulls():
    """Return a list of active/known pulls with progress."""
    with _active_pulls_lock:
        payload = {k: dict(v) for k, v in _active_pulls.items()}
    return jsonify({"pulls": payload}), 200


@app.route("/api/pulls/<path:model>", methods=["GET"])
def get_pull(model):
    with _active_pulls_lock:
        entry = _active_pulls.get(model)
        if not entry:
            return jsonify({"error": "not found"}), 404
        return jsonify(entry), 200


def _mcp_to_ollama_tools(mcp_tools):
    """Convert MCP-format tool definitions to Ollama/OpenAI-compat format.

    MCP format:  {"name": "...", "description": "...", "inputSchema": {...}}
    Ollama format: {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    """
    result = []
    for tool in (mcp_tools or []):
        result.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": (
                    tool.get("inputSchema")
                    or tool.get("parameters")
                    or {"type": "object", "properties": {}}
                ),
            },
        })
    return result


@app.route("/api/agent", methods=["POST"])
def agent():
    """Single-step agent endpoint for RuneDev_Code and MCP-compatible clients.

    Accepts MCP-format tool definitions, translates to Ollama format internally,
    and returns a normalized response containing either tool_calls or content.
    The existing /api/chat endpoint is unchanged.

    Request body:
        {model, messages, tools (MCP format, optional), stream (bool), temperature}

    Response — tool calls:
        {"role": "assistant", "content": null, "tool_calls": [...], "done": false}

    Response — text, stream=false:
        {"role": "assistant", "content": "...", "tool_calls": null, "done": true}

    Response — text, stream=true:
        NDJSON stream: {"delta": "chunk", "done": false} ... {"delta": "", "done": true}
    """
    from flask import Response as FlaskResponse

    try:
        data = request.get_json() or {}
        model_name = data.get("model", DEFAULT_MODEL)
        messages = data.get("messages", [])
        mcp_tools = data.get("tools")
        stream = bool(data.get("stream", False))
        temperature = float(data.get("temperature", 0.2))

        if not messages:
            return jsonify({"error": "messages required"}), 400

        # ONNX routing — check before hitting Ollama
        if _is_onnx_model(model_name):
            if mcp_tools:
                return jsonify({
                    "error": f"Model '{model_name}' is an ONNX model and does not support tool calling yet.",
                    "backend": "onnx",
                }), 400
            try:
                result = _route_chat_to_onnx(model_name, messages, temperature=temperature)
                if stream:
                    def _onnx_stream():
                        yield json.dumps({"delta": result["response"], "done": False}) + "\n"
                        yield json.dumps({"delta": "", "done": True}) + "\n"
                    return FlaskResponse(
                        _onnx_stream(),
                        mimetype="application/x-ndjson",
                        headers={"X-Accel-Buffering": "no"},
                    )
                return jsonify({
                    "role": "assistant",
                    "content": result["response"],
                    "tool_calls": None,
                    "done": True,
                    "backend": "onnx",
                })
            except Exception as e:
                logger.error("ONNX agent call failed for %s: %s", model_name, e)
                return jsonify({"error": f"ONNX backend error: {str(e)}"}), 502

        # Translate MCP tools → Ollama format
        ollama_tools = _mcp_to_ollama_tools(mcp_tools) if mcp_tools else None

        request_timeout = int(os.environ.get("OLLAMA_REQUEST_TIMEOUT", "180"))

        # Streaming path: no tools, stream=true
        if stream and not ollama_tools:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "options": {"temperature": temperature},
            }

            def _stream_gen():
                try:
                    r = requests.post(
                        f"{OLLAMA_HOST}/api/chat",
                        json=payload,
                        stream=True,
                        timeout=request_timeout,
                    )
                    for raw_line in r.iter_lines():
                        if not raw_line:
                            continue
                        try:
                            chunk = json.loads(raw_line)
                            delta = chunk.get("message", {}).get("content", "")
                            done = chunk.get("done", False)
                            yield json.dumps({"delta": delta, "done": done}) + "\n"
                            if done:
                                break
                        except Exception:
                            pass
                except Exception as e:
                    yield json.dumps({"delta": "", "done": True, "error": str(e)}) + "\n"

            return FlaskResponse(
                _stream_gen(),
                mimetype="application/x-ndjson",
                headers={"X-Accel-Buffering": "no"},
            )

        # Non-streaming path (always used when tools are present)
        ollama_payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if ollama_tools:
            ollama_payload["tools"] = ollama_tools

        try:
            r = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json=ollama_payload,
                timeout=request_timeout,
            )
        except requests.exceptions.Timeout:
            return jsonify({"error": "Request timeout"}), 504

        if r.status_code != 200:
            logger.error("/api/agent: Ollama returned %s: %s", r.status_code, r.text[:200])
            return jsonify({"error": f"Ollama error: {r.status_code}"}), 502

        result = r.json()
        msg = result.get("message", {})

        # Check for tool calls in the response
        raw_tool_calls = msg.get("tool_calls")
        content = msg.get("content", "") or ""

        # Fallback: models without native tool-call support (e.g. qwen2.5-coder, codellama)
        # emit the tool call as raw JSON text in `content` instead of using `tool_calls`.
        # Detect and promote these so the agent loop can execute them properly.
        # Handles both raw JSON and JSON wrapped in markdown code fences (```json ... ```).
        #
        # IMPORTANT: we keep `content` intact (the original JSON text) so the Rust agent
        # can include it verbatim in the assistant message. The model needs to see its own
        # tool-call text in history to continue the conversation correctly. We also set
        # `promoted: true` so the Rust agent knows to feed results back as `role: "user"`
        # instead of `role: "tool"` (which text-format models don't understand).
        promoted = False
        if not raw_tool_calls and ollama_tools and content:
            stripped = content.strip()

            # Strip markdown code fence if the entire content is one fenced block
            import re as _re
            fence_m = _re.match(r"^```(?:json)?\s*\n([\s\S]+?)\n```\s*$", stripped)
            if fence_m:
                stripped = fence_m.group(1).strip()

            try:
                if stripped.startswith("{") and stripped.endswith("}"):
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict) and "name" in parsed and "arguments" in parsed:
                        raw_tool_calls = [{"function": {"name": parsed["name"], "arguments": parsed["arguments"]}}]
                        promoted = True
                        logger.debug("/api/agent: promoted text-format tool call: %s", parsed["name"])
                elif stripped.startswith("[") and stripped.endswith("]"):
                    parsed_list = json.loads(stripped)
                    if isinstance(parsed_list, list) and all(
                        isinstance(item, dict) and "name" in item for item in parsed_list
                    ):
                        raw_tool_calls = [
                            {"function": {"name": item["name"], "arguments": item.get("arguments", {})}}
                            for item in parsed_list
                        ]
                        promoted = True
                        logger.debug("/api/agent: promoted %d text-format tool calls", len(raw_tool_calls))
            except (json.JSONDecodeError, TypeError):
                pass

        if raw_tool_calls:
            tool_calls = []
            for i, tc in enumerate(raw_tool_calls):
                fn = tc.get("function", {})
                tool_calls.append({
                    "id": f"call_{i}",
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", {}),
                })
            return jsonify({
                "role": "assistant",
                "content": content or None,  # kept for promoted; None for native
                "tool_calls": tool_calls,
                "done": False,
                "promoted": promoted,
            })

        if stream:
            # stream=true was requested but tools were provided — emit as single NDJSON chunk
            def _single_chunk():
                yield json.dumps({"delta": content, "done": False}) + "\n"
                yield json.dumps({"delta": "", "done": True}) + "\n"

            return FlaskResponse(
                _single_chunk(),
                mimetype="application/x-ndjson",
                headers={"X-Accel-Buffering": "no"},
            )

        return jsonify({
            "role": "assistant",
            "content": content,
            "tool_calls": None,
            "done": True,
        })

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        logger.exception("/api/agent failed: %s", e)
        return jsonify({"error": f"Agent call failed: {str(e)}"}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat endpoint using Ollama /api/chat with role-based messages array."""
    try:
        data = request.get_json() or {}
        agent_id = data.get("agent_id", "default")
        model_name = data.get("model_name", DEFAULT_MODEL)
        temperature = float(data.get("temperature", 0.7))
        top_p = float(data.get("top_p", 0.9))
        max_tokens = int(data.get("max_tokens", 2048))

        # Accept either a pre-built messages array (preferred) or a legacy
        # single message string for backwards compatibility.
        messages = data.get("messages")
        if not messages:
            message = data.get("message", "").strip()
            if not message:
                return jsonify({"error": "messages or message required"}), 400
            system_prompt = data.get("system_prompt", "")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

        # ONNX routing — check before hitting Ollama
        if _is_onnx_model(model_name):
            try:
                result = _route_chat_to_onnx(model_name, messages, temperature=temperature, max_tokens=max_tokens)
                return jsonify({
                    "response": result["response"],
                    "agent_id": agent_id,
                    "model_id": model_name,
                    "model_name": model_name,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "onnx_powered",
                    "tokens_used": len(result["response"].split()),
                    "backend": "onnx",
                })
            except Exception as e:
                logger.error("ONNX chat failed for %s: %s", model_name, e)
                return jsonify({"error": f"ONNX backend error: {str(e)}"}), 502

        ollama_payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }

        request_timeout = int(os.environ.get("OLLAMA_REQUEST_TIMEOUT", "60"))
        max_retries = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
        backoff = float(os.environ.get("OLLAMA_RETRY_BASE_S", "1"))
        response = None
        for attempt in range(max_retries):
            try:
                logger.info(
                    "[OLLAMA_RETRY] attempt %s/%s -> %s/api/chat model=%s msgs=%s",
                    attempt + 1, max_retries, OLLAMA_HOST, model_name, len(messages),
                )
                start_ts = datetime.now()
                response = requests.post(
                    f"{OLLAMA_HOST}/api/chat",
                    json=ollama_payload,
                    timeout=max(request_timeout, 10),
                )
                duration_ms = int((datetime.now() - start_ts).total_seconds() * 1000)
                logger.info("[OLLAMA_RETRY] status=%s duration_ms=%s", response.status_code, duration_ms)

                if response.status_code == 200:
                    break
                else:
                    logger.debug("[OLLAMA_RETRY] non-200 snippet=%s", response.text[:300])
                    _time.sleep(backoff)
                    backoff *= 2
            except requests.exceptions.Timeout as te:
                logger.warning("[OLLAMA_RETRY] timeout attempt %s: %s", attempt + 1, repr(te))
                _time.sleep(backoff)
                backoff *= 2
                response = None
            except Exception as ex:
                logger.exception("[OLLAMA_RETRY] exception attempt %s: %s", attempt + 1, ex)
                response = None

        if response and response.status_code == 200:
            result = response.json()
            # Ollama /api/chat returns {"message": {"role": "assistant", "content": "..."}}
            msg_obj = result.get("message", {})
            ai_response = msg_obj.get("content") if isinstance(msg_obj, dict) else result.get("response", "")
            if not ai_response:
                ai_response = result.get("response", "No response")

            return jsonify(
                {
                    "response": ai_response,
                    "agent_id": agent_id,
                    "model_id": model_name,
                    "model_name": model_name,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "ollama_powered",
                    "tokens_used": result.get("eval_count", len(ai_response.split())),
                }
            )
        else:
            logger.error(
                "Ollama chat failed after retries: status=%s",
                getattr(response, "status_code", None),
            )
            return jsonify({"error": "Request timeout or upstream failure"}), 504

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        logger.exception("Chat failed: %s", e)
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500


def _get_marshal_session():
    """Build a requests Session with mTLS certs for calling Marshal.

    Returns None if Marshal is not configured.
    """
    if not MARSHAL_URL:
        return None
    session = requests.Session()
    if MARSHAL_CERT_PATH and MARSHAL_KEY_PATH:
        session.cert = (MARSHAL_CERT_PATH, MARSHAL_KEY_PATH)
    if MARSHAL_CA_PATH:
        session.verify = MARSHAL_CA_PATH
    else:
        session.verify = False  # Dev fallback — no CA cert configured
    return session


def _fetch_machine_profile() -> dict:
    """Fetch the machine hardware profile from CoreMemory.

    Returns the parsed metadata dict, or empty dict on failure.
    """
    if not CORE_MEMORY_URL:
        return {}
    try:
        url = f"{CORE_MEMORY_URL.rstrip('/')}/v1/memories"
        r = requests.get(url, params={"namespace": "machine_profile"}, timeout=5)
        if r.status_code == 200:
            items = r.json().get("memories", [])
            if items:
                return items[0].get("metadata", {})
    except Exception as e:
        logger.warning("Failed to fetch machine profile from CoreMemory: %s", e)
    return {}


def _build_setup_spec(profile: dict) -> dict:
    """Build a Marshal SetupSpec from a Sentinel machine profile.

    Always includes sentinel.ensure. Adds onnx_service if NPU present,
    and one ollama_gpu entry per discrete GPU found.
    """
    components = [{"type": "sentinel", "action": "ensure"}]

    npu_list = profile.get("npu") or []
    gpu_list = profile.get("gpu") or []

    # NPU present → request ONNX orchestrator service
    if npu_list:
        components.append({
            "type": "onnx_service",
            "action": "ensure",
            "config": {"device": "npu"},
        })

    # One Ollama container per discrete GPU
    base_port = 11435
    for i, gpu in enumerate(gpu_list):
        if gpu.get("gpu_type") == "discrete":
            components.append({
                "type": "ollama_gpu",
                "action": "ensure",
                "config": {
                    "name": f"ollama-gpu{i}",
                    "port": base_port + i,
                    "gpu_uuid": gpu.get("device_id", ""),
                },
            })

    return {"components": components}


def _call_marshal_setup():
    """Fetch machine profile, build setup spec, and call Marshal /api/setup.

    Updates _marshal_endpoints with the returned endpoint map.
    Called from a background thread on startup.
    """
    global _marshal_endpoints
    session = _get_marshal_session()
    if not session:
        return

    profile = _fetch_machine_profile()
    if not profile:
        logger.info("Marshal auto-setup: no machine profile available, sending sentinel-only spec")

    spec = _build_setup_spec(profile)
    logger.info("Marshal auto-setup: calling %s/api/setup with %d components", MARSHAL_URL, len(spec["components"]))

    try:
        r = session.post(
            f"{MARSHAL_URL.rstrip('/')}/api/setup",
            json=spec,
            timeout=30,
        )
        if r.status_code in (200, 207):
            result = r.json()
            endpoints = result.get("endpoints", {})
            with _marshal_endpoints_lock:
                _marshal_endpoints.update(endpoints)
            logger.info("Marshal setup complete: %s", result.get("actions_taken", []))
            if result.get("errors"):
                logger.warning("Marshal setup errors: %s", result["errors"])
        else:
            logger.warning("Marshal /api/setup returned %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("Marshal auto-setup failed (non-fatal): %s", e)


# On module import (each Gunicorn worker startup): fetch ONNX model list in background
if ONNX_SERVICE_URL:
    threading.Thread(target=_fetch_onnx_models, daemon=True).start()

# Marshal auto-setup: ensure Sentinel is running and configure hardware services
if MARSHAL_URL and MARSHAL_AUTO_SETUP:
    threading.Thread(target=_call_marshal_setup, daemon=True).start()


if __name__ == "__main__":
    logger.info("Ollama Service Starting (merged entrypoint)")
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
