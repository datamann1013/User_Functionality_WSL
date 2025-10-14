#!/usr/bin/env python3
"""
AI Service Backend
Connects to existing ErrorLogger service for logging
"""
import os
import sys
import json
import random
import argparse
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Configuration
ERRORLOGGER_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://127.0.0.1:5001/log')
SERVICE_NAME = 'ai_service'
MODELS_FILE = os.path.join(os.path.dirname(__file__), 'models.json')
FRONTEND_BUILD_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'build')
FRONTEND_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'build', 'static')

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

# Mock AI responses for MVP
MOCK_RESPONSES = [
    "I'm an AI assistant running in demonstration mode. How can I help you?",
    "This is a test response from the AI service backend.",
    "Hello! I'm here to demonstrate the AI service functionality.",
    "I understand you're testing the system. Everything appears to be working correctly.",
    "Welcome to the AI service! This is a simulated response for testing.",
    "Thank you for testing the AI backend. The service is operational.",
]

# Model management
def load_models():
    """Load models from JSON file"""
    try:
        if os.path.exists(MODELS_FILE):
            with open(MODELS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log_to_errorlogger('AI_MODEL_LOAD_ERROR', f'Failed to load models: {e}', e)
    
    # Default model
    return [{
        'id': 'demo-assistant',
        'name': 'Demo Assistant',
        'icon': '🤖',
        'state': 'online',
        'version': '1.0.0',
        'description': 'Demonstration AI assistant'
    }]

def save_models(models):
    """Save models to JSON file"""
    try:
        with open(MODELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(models, f, indent=2)
        return True
    except Exception as e:
        log_to_errorlogger('AI_MODEL_SAVE_ERROR', f'Failed to save models: {e}', e)
        return False

# Initialize models
if not os.path.exists(MODELS_FILE):
    save_models(load_models())

# Frontend serving routes
@app.route('/')
def serve_frontend():
    """Serve the React frontend"""
    try:
        if os.path.exists(os.path.join(FRONTEND_BUILD_DIR, 'index.html')):
            return send_from_directory(FRONTEND_BUILD_DIR, 'index.html')
        else:
            return jsonify({'error': 'Frontend not built. Run: cd frontend && npm run build'}), 404
    except Exception as e:
        log_to_errorlogger('FRONTEND_SERVE_ERROR', f'Failed to serve frontend: {e}', e)
        return jsonify({'error': 'Frontend not available'}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files for React frontend"""
    try:
        return send_from_directory(FRONTEND_STATIC_DIR, filename)
    except Exception:
        return jsonify({'error': 'Static file not found'}), 404

@app.route('/api/log-frontend-error', methods=['POST'])
def log_frontend_error():
    """Log errors from frontend to ErrorLogger"""
    try:
        data = request.get_json()
        error_code = data.get('error_code', 'FRONTEND_ERROR')
        message = data.get('message', 'Frontend error')
        extra = data.get('extra', {})
        exception = data.get('exception')
        
        # Add frontend context
        extra.update({
            'source': 'frontend',
            'user_agent': request.headers.get('User-Agent', ''),
            'ip': request.remote_addr
        })
        
        log_to_errorlogger(error_code, message, exception, extra)
        return jsonify({'status': 'logged'})
        
    except Exception as e:
        log_to_errorlogger('FRONTEND_LOG_ERROR', f'Failed to log frontend error: {e}', e)
        return jsonify({'error': 'Failed to log error'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    log_to_errorlogger('AI_HEALTH_CHECK', 'Health check requested')
    
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
        'models_available': len(load_models()),
        'errorlogger_status': errorlogger_status
    })

@app.route('/api/models', methods=['GET'])
def list_models():
    """List available models"""
    try:
        models = load_models()
        log_to_errorlogger('AI_MODELS_LISTED', f'{len(models)} models retrieved')
        return jsonify(models)
    except Exception as e:
        log_to_errorlogger('AI_MODELS_ERROR', 'Failed to list models', e)
        return jsonify({'error': 'Failed to list models'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with mock AI responses"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        model_id = data.get('model_id', 'demo-assistant')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        log_to_errorlogger('AI_CHAT_REQUEST', f'Chat request: "{message[:50]}..."', 
                          extra={'model_id': model_id, 'message_length': len(message)})
        
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
            'model_id': model_id,
            'timestamp': datetime.now().isoformat(),
            'mode': 'demonstration'
        }
        
        log_to_errorlogger('AI_CHAT_RESPONSE', f'Response sent: "{response[:50]}..."',
                          extra={'model_id': model_id, 'response_length': len(response)})
        
        return jsonify(result)
        
    except Exception as e:
        log_to_errorlogger('AI_CHAT_ERROR', 'Chat request failed', e)
        return jsonify({'error': 'Chat request failed', 'details': str(e)}), 500

@app.route('/api/inference', methods=['POST'])
def inference():
    """Inference endpoint for direct model interaction"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '').strip()
        model_id = data.get('model_id', 'demo-assistant')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        log_to_errorlogger('AI_INFERENCE_REQUEST', f'Inference request: "{prompt[:50]}..."',
                          extra={'model_id': model_id, 'prompt_length': len(prompt)})
        
        # Mock inference response
        response_text = f"[Demo Response] {random.choice(MOCK_RESPONSES)}"
        
        result = {
            'generated_text': response_text,
            'model_id': model_id,
            'timestamp': datetime.now().isoformat(),
            'mode': 'demonstration'
        }
        
        log_to_errorlogger('AI_INFERENCE_RESPONSE', f'Inference completed for model: {model_id}')
        return jsonify(result)
        
    except Exception as e:
        log_to_errorlogger('AI_INFERENCE_ERROR', 'Inference failed', e)
        return jsonify({'error': 'Inference failed', 'details': str(e)}), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI Service Backend')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on (default: 5000)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"🤖 Starting AI Service Backend")
    print(f"   Host: {args.host}:{args.port}")
    print(f"   ErrorLogger: {ERRORLOGGER_URL}")
    print(f"   Models: {len(load_models())} available")
    
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
