#!/usr/bin/env python3
"""
AI Service Backend - Optimized with Redis Conversation Cache
"""
import os
import requests
import asyncio
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

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
                return ""
            def get_full_conversation(self, agent_id):
                return []
            def add_conversation(self, agent_id, user_msg, ai_msg):
                pass
            def get_conversation_context(self, agent_id):
                return []
        class MockAsyncAgentManager:
            async def submit_request(self, agent_id, user_id, message, priority=0, timeout=60.0):
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
            # Adjust timeout based on message complexity
            message_length = len(message)
            base_timeout = 20
            complex_timeout = (
                35
                if message_length > 100 or len(message.split()) > 20
                else base_timeout
            )

            payload = {
                "message": enhanced_message,
                "agent_id": agent_id,
                "model_name": "llama3.2:1b",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 2048,
                "system_prompt": "",  # System prompt is now handled in chat history
                "timestamp": datetime.now().isoformat(),
            }

            response = requests.post(
                f"{OLLAMA_SERVICE_URL}/api/chat", json=payload, timeout=complex_timeout
            )

            if response.status_code == 200:
                ollama_response = response.json()
                ai_response = ollama_response.get("response", "No response from AI")
                response_mode = "ollama"
            else:
                raise Exception(f"Ollama returned {response.status_code}")

        except requests.exceptions.Timeout:
            log_error(
                "OLLAMA_TIMEOUT",
                f"Request timed out after {complex_timeout}s for message: {message[:50]}...",
            )
            ai_response = "I'm taking a bit longer to think about your question. Let me try to give you a quicker response: could you rephrase your question or break it into smaller parts?"
            response_mode = "timeout_fallback"
        except Exception as e:
            log_error("OLLAMA_ERROR", str(e))

            log_error("OLLAMA_CONNECTION_ERROR", str(e))

            # Simplified direct response without retry loops
            if any(
                word in message.lower()
                for word in ["hello", "hi", "hey", "how are you"]
            ):
                ai_response = "Hello! I'm doing well, thanks for asking. How can I help you today?"
            elif "poem" in message.lower():
                ai_response = "I'd be happy to write a poem for you! What theme or topic would you like me to focus on?"
            elif "weather" in message.lower():
                ai_response = "I don't have access to current weather data, but I can discuss weather topics or write about weather if you'd like!"
            elif any(
                word in message.lower() for word in ["why", "how", "what", "explain"]
            ):
                ai_response = "That's an interesting question! I'm having some technical difficulties right now, but I'd be happy to help explain that topic if you could try asking again."
            else:
                ai_response = "I received your message, but I'm experiencing some technical issues. Could you please try rephrasing your question or asking it again?"

            response_mode = "graceful_fallback"

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
                    timeout=timeout
                )
            )
            
            return jsonify({
                "request_id": request_id,
                "status": "submitted",
                "agent_id": agent_id,
                "user_id": user_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "estimated_time": "30-60 seconds",
                "poll_url": f"/api/chat/async/{request_id}"
            })
            
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
                return jsonify({
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
                    "ready": True
                })
            else:
                # Still processing or not found
                status = loop.run_until_complete(
                    async_agent_manager.get_request_status(request_id)
                )
                
                if status:
                    return jsonify({
                        "request_id": request_id,
                        "status": status.value,
                        "ready": False,
                        "message": "Request is still being processed",
                        "poll_again_in": "5-10 seconds"
                    })
                else:
                    return jsonify({
                        "request_id": request_id,
                        "status": "not_found",
                        "ready": False,
                        "error": "Request not found"
                    }), 404
                    
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
                agent_id = req_data.get("agent_id", "71dc06c0-7b49-4a7d-9afb-a2d7fdcde53b")
                user_id = req_data.get("user_id", "anonymous")
                priority = req_data.get("priority", 0)
                
                if message:
                    request_id = loop.run_until_complete(
                        async_agent_manager.submit_request(
                            agent_id=agent_id,
                            user_id=user_id,
                            message=message,
                            priority=priority
                        )
                    )
                    request_ids.append({
                        "request_id": request_id,
                        "agent_id": agent_id,
                        "message": message[:50] + "..." if len(message) > 50 else message
                    })
            
            return jsonify({
                "batch_id": str(datetime.now().timestamp()),
                "request_ids": request_ids,
                "total_submitted": len(request_ids),
                "timestamp": datetime.now().isoformat(),
                "poll_url": "/api/chat/async/batch/status"
            })
            
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
                    results.append({
                        "request_id": request_id,
                        "status": response.status.value,
                        "ready": True,
                        "response": response.response,
                        "processing_time": response.processing_time,
                        "agent_id": response.agent_id
                    })
                else:
                    # Check if still processing
                    status = loop.run_until_complete(
                        async_agent_manager.get_request_status(request_id)
                    )
                    results.append({
                        "request_id": request_id,
                        "status": status.value if status else "not_found",
                        "ready": False,
                        "processing": True if status else False
                    })
            
            # Calculate summary stats
            completed = sum(1 for r in results if r.get("ready", False))
            processing = sum(1 for r in results if r.get("processing", False))
            failed = sum(1 for r in results if r.get("status") in ["failed", "timeout"])
            
            return jsonify({
                "results": results,
                "summary": {
                    "total": len(results),
                    "completed": completed,
                    "processing": processing,
                    "failed": failed,
                    "completion_rate": f"{(completed/len(results)*100):.1f}%" if results else "0%"
                },
                "timestamp": datetime.now().isoformat()
            })
            
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
        return jsonify({
            "async_system": stats,
            "cache_system": conversation_cache.get_cache_stats(),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        log_error("ASYNC_STATS_ERROR", str(e))
        return jsonify({"error": "Failed to get stats"}), 500


if __name__ == "__main__":
    print("🤖 AI Service Backend Starting with Redis Conversation Cache & Async Multi-Agent System")

    # Print cache configuration
    cache_status = conversation_cache.get_cache_stats()
    print(
        f"💾 Cache Status: {'Redis' if cache_status['using_redis'] else 'Fallback Dict'}"
    )
    print(f"📝 Message Limit: {cache_status['message_limit']} per agent")
    print(f"🧠 Context Size: {cache_status['context_size']} messages for AI")
    
    # Print async system info
    async_stats = async_agent_manager.get_stats()
    print(f"⚡ Async System: {'Available' if not async_stats.get('mock') else 'Mock Mode'}")
    
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting server on port {port}")
    print("📡 Async Endpoints Available:")
    print("   POST /api/chat/async - Submit async request (returns request_id)")
    print("   GET  /api/chat/async/<request_id> - Poll for response") 
    print("   POST /api/chat/async/batch - Submit multiple requests")
    print("   POST /api/chat/async/batch/status - Check batch status")
    print("   GET  /api/chat/async/stats - System statistics")
    
    app.run(host="0.0.0.0", port=port, debug=False)  # nosec B104
