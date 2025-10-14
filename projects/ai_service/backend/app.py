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
    """Chat endpoint with mock AI responses"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        agent_id = data.get('agent_id', 'assistant-1')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        log_to_errorlogger('AI_CHAT_REQUEST', f'Chat request: "{message[:50]}..."', 
                          extra={'agent_id': agent_id, 'message_length': len(message)})
        
        # Generate contextual response
        message_lower = message.lower()
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            response = "Hello! I'm the AI service demonstration assistant. How can I help you today?"
        elif any(word in message_lower for word in ['test', 'testing']):
            response = "Great! The AI service is working correctly. All systems are operational."
        elif any(word in message_lower for word in ['error', 'log']):
            response = "I'm integrated with the ErrorLogger service for comprehensive monitoring and debugging."
        else:
            response = random.choice(MOCK_RESPONSES)
        
        result = {
            'response': response,
            'agent_id': agent_id,
            'timestamp': datetime.now().isoformat(),
            'mode': 'demonstration'
        }
        
        log_to_errorlogger('AI_CHAT_RESPONSE', f'Response sent: "{response[:50]}..."',
                          extra={'agent_id': agent_id, 'response_length': len(response)})
        
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
