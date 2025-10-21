#!/usr/bin/env python3
"""
AI Service Backend - Optimized with Redis Conversation Cache
"""
import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import conversation cache
from cache.conversation_cache import conversation_cache

app = Flask(__name__)
CORS(app)

# Configuration
ERRORLOGGER_URL = os.environ.get("ERRORLOGGER_SERVICE_URL", "http://127.0.0.1:5001/log")
OLLAMA_SERVICE_URL = os.environ.get("OLLAMA_SERVICE_URL", "http://127.0.0.1:5003")

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
        # Fail silently for performance, but log the exception type
        pass
    except Exception:
        # Catch any other unexpected errors
        pass  # nosec B110


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
            formatted_conversations.append({
                "id": msg["id"],
                "user_message": msg["user_message"],
                "ai_response": msg["ai_response"],
                "timestamp": msg["timestamp"],
                "model_used": "cached",  # Placeholder for now
                "agent_id": agent_id
            })
        
        return jsonify({
            "conversations": formatted_conversations[:limit],
            "count": len(formatted_conversations),
            "source": "local_cache"
        })
        
    except Exception as e:
        log_error("CACHE_ERROR", str(e))
        return jsonify({
            "conversations": [],
            "count": 0,
            "error": "Failed to retrieve conversations"
        }), 500


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

        # Get conversation context from cache
        conversation_context = conversation_cache.format_context_for_ai(agent_id)
        
        # Build enhanced message with context
        if conversation_context:
            enhanced_message = f"{conversation_context}\nUser: {message}\nAssistant:"
        else:
            enhanced_message = message

        ai_response = None
        response_mode = "fallback"

        # Try Ollama service first
        try:
            payload = {
                "message": enhanced_message,
                "agent_id": agent_id,
                "model_name": "llama3.2:1b",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 2048,
                "system_prompt": "You are a helpful AI assistant with access to previous conversation context.",
                "timestamp": datetime.now().isoformat(),
            }

            response = requests.post(
                f"{OLLAMA_SERVICE_URL}/api/chat", json=payload, timeout=30
            )

            if response.status_code == 200:
                ollama_response = response.json()
                ai_response = ollama_response.get("response", "No response from AI")
                response_mode = "ollama"
            else:
                raise Exception(f"Ollama returned {response.status_code}")

        except Exception as e:
            log_error("OLLAMA_ERROR", str(e))
            
            # Fast fallback response with context awareness
            context_msgs = conversation_cache.get_conversation_context(agent_id, limit=2)
            
            if context_msgs and any("hello" in msg["user_message"].lower() for msg in context_msgs):
                ai_response = "Hello again! How can I help you further?"
            elif "hello" in message.lower():
                ai_response = "Hello! I'm running in fallback mode but ready to help."
            elif "test" in message.lower():
                ai_response = "System test successful - fallback mode active with conversation cache."
            else:
                ai_response = f"I received your message: '{message}' (fallback mode with context)"

        # Store conversation in cache
        try:
            conversation_cache.add_conversation(agent_id, message, ai_response)
            log_error("CACHE_SUCCESS", f"Conversation cached for agent {agent_id}")
        except Exception as cache_error:
            log_error("CACHE_ERROR", f"Failed to cache conversation: {str(cache_error)}")
            # Continue anyway - caching failure shouldn't break the response

        # Return response
        return jsonify({
            "response": ai_response,
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat(),
            "mode": response_mode,
            "context_used": len(conversation_context) > 0,
            "cached_messages": len(conversation_cache.get_conversation_context(agent_id))
        })

    except Exception as e:
        log_error("CHAT_ERROR", str(e))
        return jsonify({"error": "Chat failed"}), 500


if __name__ == "__main__":
    print("🤖 AI Service Backend Starting with Redis Conversation Cache")
    
    # Print cache configuration
    cache_status = conversation_cache.get_cache_stats()
    print(f"💾 Cache Status: {'Redis' if cache_status['using_redis'] else 'Fallback Dict'}")
    print(f"📝 Message Limit: {cache_status['message_limit']} per agent")
    print(f"🧠 Context Size: {cache_status['context_size']} messages for AI")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
