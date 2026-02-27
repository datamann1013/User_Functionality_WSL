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
        """Read the streaming pull response and track progress."""
        try:
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    progress = int(completed / total * 100) if total > 0 else 0

                    with _active_pulls_lock:
                        entry = _active_pulls.get(model_name)
                        if entry is None:
                            return
                        entry["last_update"] = datetime.now().isoformat()
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
    """Get available models"""
    status = get_ollama_status()
    return jsonify(
        {
            "models": status["models_available"],
            "running": status["running"],
            "last_check": status["last_check"],
        }
    )


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
                "content": msg.get("content") or None,
                "tool_calls": tool_calls,
                "done": False,
            })

        # Pure text response
        content = msg.get("content", "")

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


if __name__ == "__main__":
    logger.info("🤖 Ollama Service Starting (merged entrypoint)")
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
