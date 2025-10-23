#!/usr/bin/env python3
"""
Ollama API Service - Optimized
High-performance AI chat service
"""
import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
try:
    from flask_cors import CORS
except Exception:
    # Running in a constrained environment where Flask-Cors isn't available.
    # We'll provide a no-op CORS placeholder so the app can start.
    def CORS(app, *args, **kwargs):
        return None
import time

app = Flask(__name__)
CORS(app)

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
                _ollama_cache["status"] = {
                    "running": False,
                    "models_available": [],
                    "last_check": datetime.now().isoformat(),
                }
        except:
            _ollama_cache["status"] = {
                "running": False,
                "models_available": [],
                "last_check": datetime.now().isoformat(),
            }
        _ollama_cache["last_check"] = now
    return _ollama_cache["status"]


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
        # Debug: log incoming fields to help trace missing user content
        try:
            print(f"[OLLAMA_DEBUG] incoming message: '{message[:200]}' system_prompt: '{system_prompt[:200]}'")
        except Exception:
            pass

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

        # Try the generate endpoint with retries to mitigate transient timeouts
        max_retries = 3
        backoff = 1
        response = None
        for attempt in range(max_retries):
            try:
                print(f"[OLLAMA_RETRY] attempt {attempt+1}/{max_retries} -> {OLLAMA_HOST}/api/generate")
                start_ts = datetime.now()
                response = requests.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json=ollama_payload,
                    timeout=180,
                )
                duration_ms = int((datetime.now() - start_ts).total_seconds() * 1000)
                if response is not None:
                    print(f"[OLLAMA_RETRY] response status={response.status_code} duration_ms={duration_ms}")

                # Break on successful HTTP response code
                if response and response.status_code == 200:
                    break
                else:
                    # non-200 - wait and retry
                    try:
                        # attempt to show snippet of response body for diagnostics
                        body_snippet = response.text[:300] if response is not None else "<no-body>"
                        print(f"[OLLAMA_RETRY] non-200 response body_snippet={body_snippet}")
                    except Exception:
                        pass
                    time.sleep(backoff)
                    backoff *= 2
            except requests.exceptions.Timeout as te:
                print(f"[OLLAMA_RETRY] timeout on attempt {attempt+1}: {repr(te)}")
                # retry on timeout
                time.sleep(backoff)
                backoff *= 2
                response = None
            except Exception as ex:
                # Log unexpected exceptions to help diagnose connection issues
                try:
                    print(f"[OLLAMA_RETRY] exception on attempt {attempt+1}: {repr(ex)}")
                except Exception:
                    pass
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
            # If we couldn't obtain a good response after retries, surface a timeout
            return jsonify({"error": "Request timeout or upstream failure"}), 504

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("🤖 Ollama Service Starting (Optimized)")
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
