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

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate", json=ollama_payload, timeout=60
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
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("🤖 Ollama Service Starting (Optimized)")
    app.run(host="0.0.0.0", port=5002, debug=False)  # nosec B104
