#!/usr/bin/env python3
"""
Ollama API Service - Optimized
High-performance AI chat service
"""
import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import threading
import re
import time as _time

# Track active model pulls and progress
_active_pulls = {}
_active_pulls_lock = threading.Lock()

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ollama_service")

# Configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "llama3.2:1b"

# Cache for Ollama status
_ollama_cache = {"status": None, "last_check": 0}


def get_ollama_status():
    """Cached Ollama status check"""
    now = datetime.now().timestamp()
    if now - _ollama_cache["last_check"] > 30:  # Cache for 30 seconds
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
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
            # Attempt to call local ollama binary and stream stdout/stderr
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

            # Read lines and try to parse progress percentages
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
                    pass

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
            # best-effort; we do not raise here
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
        except Exception:
            # best-effort; we do not raise here
            try:
                logger.exception("Background ollama pull failed for %s", model_name)
            except Exception:
                pass

    th = threading.Thread(target=_runner, args=(name,), daemon=True)
    th.start()


def download_model_via_ollama(name):
    """Try multiple strategies to request Ollama to download/pull the model.

    Returns True if a pull was initiated (not necessarily completed).
    """
    # 1) Try HTTP endpoints that some Ollama versions may expose
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
                # Invalidate cache so status reflects the new model after some time
                _ollama_cache["last_check"] = 0
                # mark pull as started (http-driven)
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

    # 2) Fallback to spawning local ollama cli if present
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

    This endpoint will attempt to instruct the underlying Ollama host to
    download the requested model. It returns 200 if the pull was initiated
    (not necessarily completed) or 500/503 if initiation failed.
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
    """Compatibility route used by frontend ModelManager: POST /api/models/download/<model>"""
    try:
        # model may be URL-encoded in the path
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
        # shallow copy
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
    """Optimized chat endpoint"""
    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        agent_id = data.get("agent_id", "default")

        if not message:
            return jsonify({"error": "Message required"}), 400

        # Use provided parameters or defaults
        model_name = data.get("model_name", DEFAULT_MODEL)
        temperature = float(data.get("temperature", 0.7))
        top_p = float(data.get("top_p", 0.9))
        max_tokens = int(data.get("max_tokens", 2048))
        system_prompt = data.get("system_prompt", "")

        # Build prompt
        full_prompt = (
            f"{system_prompt}\n\nUser: {message}\n\nAssistant:"
            if system_prompt
            else message
        )

        # Ollama request
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

        request_timeout = int(os.environ.get("OLLAMA_REQUEST_TIMEOUT", "60"))
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate", json=ollama_payload, timeout=request_timeout
        )

        if response.status_code == 200:
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
            # Log details for debugging
            try:
                logger.error("Ollama /api/generate returned %s: %s", response.status_code, response.text)
            except Exception:
                logger.exception("Ollama /api/generate returned %s and response body could not be read", response.status_code)
            return jsonify({"error": f"Ollama error: {response.status_code}", "body": response.text}), 502

    except requests.exceptions.Timeout:
        return jsonify({"error": "Ollama request timeout"}), 504
    except Exception as e:
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("🤖 Ollama Service Starting (Optimized)")
    app.run(host="0.0.0.0", port=5002, debug=False)  # nosec B104
