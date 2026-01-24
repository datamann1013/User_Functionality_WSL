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
    """Try multiple strategies to request Ollama to download/pull the model.

    Returns True if a pull was initiated (not necessarily completed).
    """
    candidates = [
        (f"{OLLAMA_HOST}/api/models/download", {"name": name}),
        (f"{OLLAMA_HOST}/api/pull", {"name": name}),
        (f"{OLLAMA_HOST}/api/models/{name}/pull", None),
        (f"{OLLAMA_HOST}/api/pull/{name}", None),
    ]

    for url, payload in candidates:
        try:
            if payload is not None:
                r = requests.post(url, json=payload, timeout=10)
            else:
                r = requests.post(url, timeout=10)
            if r.status_code in (200, 202):
                _ollama_cache["last_check"] = 0
                with _active_pulls_lock:
                    _active_pulls[name] = {
                        "model": name,
                        "status": "started",
                        "progress": 0,
                        "started_at": datetime.now().isoformat(),
                        "last_update": datetime.now().isoformat(),
                        "output": r.text[:0],
                    }
                return True
        except Exception:
            continue

    # Fallback to local CLI
    try:
        _spawn_ollama_pull(name)
        return True
    except Exception:
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


@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat/generate endpoint with retries and diagnostics."""
    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        agent_id = data.get("agent_id", "default")

        if not message:
            return jsonify({"error": "Message required"}), 400

        model_name = data.get("model_name", DEFAULT_MODEL)
        temperature = float(data.get("temperature", 0.7))
        top_p = float(data.get("top_p", 0.9))
        max_tokens = int(data.get("max_tokens", 2048))
        system_prompt = data.get("system_prompt", "")

        # Build prompt
        full_prompt = (
            f"{system_prompt}\n\nUser: {message}\n\nAssistant:" if system_prompt else message
        )

        ollama_payload = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }

        # Use environment override for timeout
        request_timeout = int(os.environ.get("OLLAMA_REQUEST_TIMEOUT", "60"))

        # Retry loop with exponential backoff (from the dev variant)
        max_retries = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
        backoff = float(os.environ.get("OLLAMA_RETRY_BASE_S", "1"))
        response = None
        for attempt in range(max_retries):
            try:
                logger.info("[OLLAMA_RETRY] attempt %s/%s -> %s/api/generate", attempt + 1, max_retries, OLLAMA_HOST)
                start_ts = datetime.now()
                response = requests.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json=ollama_payload,
                    timeout=max(request_timeout, 10),
                )
                duration_ms = int((datetime.now() - start_ts).total_seconds() * 1000)
                if response is not None:
                    logger.info("[OLLAMA_RETRY] status=%s duration_ms=%s", response.status_code, duration_ms)

                if response and response.status_code == 200:
                    break
                else:
                    try:
                        body_snippet = response.text[:300] if response is not None else "<no-body>"
                        logger.debug("[OLLAMA_RETRY] non-200 response snippet=%s", body_snippet)
                    except Exception:
                        pass
                    _time.sleep(backoff)
                    backoff *= 2
            except requests.exceptions.Timeout as te:
                logger.warning("[OLLAMA_RETRY] timeout on attempt %s: %s", attempt + 1, repr(te))
                _time.sleep(backoff)
                backoff *= 2
                response = None
            except Exception as ex:
                logger.exception("[OLLAMA_RETRY] exception on attempt %s: %s", attempt + 1, ex)
                response = None

        if response and response.status_code == 200:
            result = response.json()
            ai_response = result.get("response", "No response")

            return jsonify(
                {
                    "response": ai_response,
                    "agent_id": agent_id,
                    "model_id": model_name,
                    "model_name": model_name,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "ollama_powered",
                    "tokens_used": len(ai_response.split()),
                    "parameters_used": {
                        "temperature": temperature,
                        "top_p": top_p,
                        "max_tokens": max_tokens,
                        "system_prompt": system_prompt,
                    },
                }
            )
        else:
            logger.error("Ollama generate failed after retries: status=%s", getattr(response, 'status_code', None))
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
