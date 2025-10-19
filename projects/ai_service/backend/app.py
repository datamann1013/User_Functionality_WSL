#!/usr/bin/env python3
"""
AI Service Backend - Simplified
Connects to ErrorLogger service for logging
"""
import os
import sys
import random
import argparse
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Configuration
ERRORLOGGER_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://127.0.0.1:5001/log')
SERVICE_NAME = 'ai_service'

# Error logging helper
def log_to_errorlogger(error_code, message=None, exception=None, extra=None):
    """Log to ErrorLogger service if available"""
    try:
        payload = {
            'error_code': error_code,
            'message': message or f'Event: {error_code}',
            'exception': str(exception) if exception else None,
            'extra': extra or {},
            'service': SERVICE_NAME
        }
        response = requests.post(ERRORLOGGER_URL, json=payload, timeout=2)
        return response.status_code == 200
    except Exception:
        # Fail silently if ErrorLogger unavailable
        return False

# Mock AI responses for demonstration
MOCK_RESPONSES = [
    "I'm an AI assistant running in demonstration mode. How can I help you?",
    "This is a test response from the AI service backend.",
    "I'm here to demonstrate the chat functionality. What would you like to know?",
    "The AI service is working correctly and integrated with error logging.",
    "Thanks for testing the system! Everything appears to be functioning properly."
]

@app.route('/api/log-frontend-error', methods=['POST'])
def log_frontend_error():
    """Receive error logs from frontend and forward to ErrorLogger"""
    try:
        data = request.get_json()
        
        # Forward to ErrorLogger with frontend context
        success = log_to_errorlogger(
            error_code=data.get('error_code', 'FRONTEND_ERROR'),
            message=data.get('message', 'Frontend error occurred'),
            exception=data.get('exception'),
            extra={
                **data.get('extra', {}),
                'source': 'frontend'
            }
        )
        
        if success:
            return jsonify({'status': 'logged'})
        else:
            return jsonify({'status': 'failed', 'reason': 'ErrorLogger unavailable'}), 503
            
    except Exception as e:
        print(f"Error processing frontend log: {e}")
        return jsonify({'error': 'Failed to process error log'}), 500

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get list of agents - simplified version"""
    try:
        # Return hardcoded agents for now to get frontend working
        agents = [
            {
                'id': '71dc06c0-7b49-4a7d-9afb-a2d7fdcde53b',
                'name': 'Gary',
                'avatar_image': None,
                'model_name': 'llama3.2:1b',
                'temperature': 0.7,
                'top_p': 0.9,
                'system_prompt': 'You are a helpful AI assistant.',
                'max_tokens': 2048,
                'status': 'idle',
                'created_at': '2025-10-19T13:10:15.634648+00:00',
                'last_active': '2025-10-19T14:12:06.915751+00:00',
                'metadata': {}
            },
            {
                'id': '3c3f3ac6-8be1-4e97-aec8-e2d529e4b436',
                'name': 'Kora',
                'avatar_image': None,
                'model_name': 'gemma:2b',
                'temperature': 0.8,
                'top_p': 0.9,
                'system_prompt': 'You are a creative AI assistant.',
                'max_tokens': 2048,
                'status': 'idle',
                'created_at': '2025-10-19T13:10:20.634648+00:00',
                'last_active': '2025-10-19T14:12:06.915751+00:00',
                'metadata': {}
            }
        ]
        
        return jsonify({'agents': agents, 'count': len(agents)})
        
    except Exception as e:
        log_to_errorlogger('GET_AGENTS_ERROR', 'Failed to retrieve agents', e)
        return jsonify({'error': 'Failed to retrieve agents', 'details': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""    
    # Check ErrorLogger connectivity
    errorlogger_status = 'disconnected'
    try:
        response = requests.get(ERRORLOGGER_URL.replace('/log', '/health'), timeout=2)
        if response.status_code == 200:
            errorlogger_status = 'connected'
    except Exception:
        pass
    
    return jsonify({
        'status': 'ok',
        'service': SERVICE_NAME,
        'timestamp': datetime.now().isoformat(),
        'errorlogger_status': errorlogger_status
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with Ollama integration"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        agent_id = data.get('agent_id', 'assistant-1')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        log_to_errorlogger('AI_CHAT_REQUEST', f'Chat request: "{message[:50]}..."', 
                          extra={'agent_id': agent_id, 'message_length': len(message)})
        
        # Try to connect to Ollama service
        try:
            ollama_service_url = os.environ.get('OLLAMA_SERVICE_URL', 'http://172.20.0.1:5002')
            
            # Test Ollama service connection
            health_response = requests.get(f"{ollama_service_url}/health", timeout=5)
            if health_response.status_code != 200:
                raise Exception("Ollama service not responding")
            
            # Send chat request to Ollama service
            payload = {
                'message': message,
                'agent_id': agent_id,
                'model_name': 'llama3.2:1b',  # Default model
                'temperature': 0.7,
                'top_p': 0.9,
                'max_tokens': 2048,
                'system_prompt': 'You are a helpful AI assistant.',
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{ollama_service_url}/api/chat",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                ollama_result = response.json()
                log_to_errorlogger('AI_CHAT_SUCCESS', f'Ollama response: "{ollama_result.get("response", "")[:50]}..."',
                                 extra={'agent_id': agent_id})
                return jsonify(ollama_result)
            else:
                raise Exception(f"Ollama service returned {response.status_code}")
                
        except Exception as ollama_error:
            log_to_errorlogger('OLLAMA_ERROR', f'Ollama service failed: {ollama_error}')
            
            # Fallback to mock response
            message_lower = message.lower()
            if any(word in message_lower for word in ['hello', 'hi', 'hey']):
                response_text = "Hello! I'm the AI service demonstration assistant. The Ollama service is currently unavailable, so I'm running in fallback mode."
            elif any(word in message_lower for word in ['test', 'testing']):
                response_text = "The AI service is working, but Ollama integration is currently unavailable. Running in demonstration mode."
            else:
                response_text = f"I received your message: '{message}'. However, the AI service is currently running in fallback mode because the Ollama service is unavailable."
            
            result = {
                'response': response_text,
                'agent_id': agent_id,
                'timestamp': datetime.now().isoformat(),
                'mode': 'fallback',
                'warning': 'Ollama service unavailable - using fallback responses'
            }
            
            return jsonify(result)
        
    except Exception as e:
        log_to_errorlogger('AI_CHAT_ERROR', 'Chat request failed', e)
        return jsonify({'error': 'Chat request failed', 'details': str(e)}), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI Service Backend')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on (default: 5000)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"🤖 Starting AI Service Backend")
    print(f"   Host: {args.host}:{args.port}")
    print(f"   ErrorLogger: {ERRORLOGGER_URL}")
    
    # Test ErrorLogger connection
    if log_to_errorlogger('AI_SERVICE_STARTUP', 'AI Service starting up'):
        print(f"   ✅ ErrorLogger connection: OK")
    else:
        print(f"   ⚠️  ErrorLogger connection: Failed (will run without logging)")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use!")
            sys.exit(1)
        else:
            raise
