#!/usr/bin/env python3
"""
Minimal AI Service Backend - MVP Version
Simple chat API that works without large model downloads
"""
import os
import sys
import json
import random
import argparse
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
ERRORLOGGER_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://localhost:5001/log')
MODELS_FILE = os.path.join(os.path.dirname(__file__), 'models_mvp.json')

# Simple error logging
def log_error(error_code, message=None, exception=None):
    """Log error to ErrorLogger service"""
    try:
        payload = {
            'error_code': error_code,
            'message': message,
            'exception': str(exception) if exception else None,
            'extra': {'service': 'ai_backend_mvp'}
        }
        requests.post(ERRORLOGGER_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ErrorLogger Unreachable] {e}")

# Mock AI responses (for MVP without actual models)
MOCK_RESPONSES = [
    "I'm a minimal AI assistant. This is a demo response!",
    "Hello! I'm running in MVP mode without large language models.",
    "This is a simulated AI response for testing purposes.",
    "I understand you're testing the AI service. Everything looks good!",
    "Welcome to the AI Service MVP! The system is working correctly.",
    "I'm a lightweight AI assistant running in demonstration mode.",
    "This response shows that the backend API is functioning properly.",
    "Thank you for testing! The AI service infrastructure is operational."
]

# Simple model registry
def get_models():
    """Get available models"""
    try:
        if os.path.exists(MODELS_FILE):
            with open(MODELS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log_error('MVP001', f'Failed to load models: {e}', e)
    
    # Default models for MVP
    return [{
        'id': 'mvp-demo',
        'name': 'MVP Demo Assistant',
        'icon': '🤖',
        'state': 'online',
        'version': 'mvp-1.0',
        'description': 'Lightweight demo assistant for testing'
    }]

def save_models(models):
    """Save models to file"""
    try:
        with open(MODELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(models, f, indent=2)
        return True
    except Exception as e:
        log_error('MVP002', f'Failed to save models: {e}', e)
        return False

# Initialize models
if not os.path.exists(MODELS_FILE):
    save_models(get_models())

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    log_error('MVP_HEALTH', 'Health check called')
    return jsonify({
        'status': 'ok',
        'service': 'ai_backend_mvp',
        'timestamp': datetime.now().isoformat(),
        'models_available': len(get_models())
    })

@app.route('/api/models', methods=['GET'])
def list_models():
    """List available models"""
    try:
        models = get_models()
        log_error('MVP_MODELS', f'Models listed: {len(models)} available')
        return jsonify(models)
    except Exception as e:
        log_error('MVP003', 'Failed to list models', e)
        return jsonify({'error': 'Failed to list models'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint (MVP with mock responses)"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        model_id = data.get('model_id', 'mvp-demo')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Log the request
        log_error('MVP_CHAT_REQUEST', f'Chat request received: "{message[:50]}..."')
        
        # Generate mock response
        response = random.choice(MOCK_RESPONSES)
        
        # Add context-aware responses for certain keywords
        message_lower = message.lower()
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            response = "Hello! I'm the AI Service MVP. How can I help you test the system today?"
        elif any(word in message_lower for word in ['test', 'testing', 'check']):
            response = "Great! You're testing the AI service. Everything appears to be working correctly. The backend is responding and the ErrorLogger is capturing events."
        elif any(word in message_lower for word in ['error', 'problem', 'issue']):
            response = "I see you're asking about errors. This MVP system includes comprehensive error logging. Check the ErrorLogger service for detailed diagnostics."
        elif any(word in message_lower for word in ['model', 'ai', 'assistant']):
            response = "I'm running in MVP mode without large language models. This demonstrates the API structure that would connect to real AI models in production."
        
        result = {
            'response': response,
            'model_id': model_id,
            'timestamp': datetime.now().isoformat(),
            'mode': 'mvp_demo'
        }
        
        log_error('MVP_CHAT_RESPONSE', f'Response generated: "{response[:50]}..."')
        return jsonify(result)
        
    except Exception as e:
        log_error('MVP004', 'Chat request failed', e)
        return jsonify({'error': 'Chat request failed', 'details': str(e)}), 500

@app.route('/api/inference/run', methods=['POST'])
def run_inference():
    """Inference endpoint (MVP version)"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        model_id = data.get('model_id', 'mvp-demo')
        
        # Simple inference simulation
        response_text = f"[MVP Response to: '{prompt[:30]}...'] " + random.choice(MOCK_RESPONSES)
        
        result = {
            'generated_text': response_text,
            'model_id': model_id,
            'timestamp': datetime.now().isoformat(),
            'mode': 'mvp_simulation'
        }
        
        log_error('MVP_INFERENCE', f'Inference completed for model: {model_id}')
        return jsonify(result)
        
    except Exception as e:
        log_error('MVP005', 'Inference failed', e)
        return jsonify({'error': 'Inference failed', 'details': str(e)}), 500

# Simple web interface for testing
WEB_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Service MVP - Test Interface</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .chat { border: 1px solid #ddd; height: 300px; overflow-y: auto; padding: 10px; margin: 10px 0; background: #fafafa; }
        .message { margin: 5px 0; padding: 8px; border-radius: 4px; }
        .user { background: #e3f2fd; text-align: right; }
        .ai { background: #f3e5f5; }
        input[type="text"] { width: 70%; padding: 8px; }
        button { padding: 8px 16px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .status { padding: 10px; background: #e8f5e8; border-radius: 4px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AI Service MVP - Test Interface</h1>
        <div class="status">
            <strong>Status:</strong> MVP Mode Active | <strong>Time:</strong> {{ timestamp }} | <strong>Models:</strong> {{ model_count }}
        </div>
        
        <div class="chat" id="chat"></div>
        
        <div>
            <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="if(event.key==='Enter') sendMessage()">
            <button onclick="sendMessage()">Send</button>
            <button onclick="clearChat()">Clear</button>
        </div>
        
        <h3>Available Models:</h3>
        <ul id="models"></ul>
    </div>

    <script>
        // Load models
        fetch('/api/models')
            .then(r => r.json())
            .then(models => {
                const list = document.getElementById('models');
                models.forEach(model => {
                    list.innerHTML += `<li><strong>${model.name}</strong> (${model.id}) - ${model.state}</li>`;
                });
            });

        function addMessage(text, isUser) {
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = `message ${isUser ? 'user' : 'ai'}`;
            div.textContent = `${isUser ? 'You' : 'AI'}: ${text}`;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;

            addMessage(message, true);
            input.value = '';

            fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message, model_id: 'mvp-demo'})
            })
            .then(r => r.json())
            .then(data => {
                if (data.response) {
                    addMessage(data.response, false);
                } else {
                    addMessage('Error: ' + (data.error || 'Unknown error'), false);
                }
            })
            .catch(e => addMessage('Error: ' + e.message, false));
        }

        function clearChat() {
            document.getElementById('chat').innerHTML = '';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def web_interface():
    """Simple web interface for testing"""
    models = get_models()
    return render_template_string(WEB_INTERFACE, 
                                  timestamp=datetime.now().isoformat(),
                                  model_count=len(models))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI Service Backend MVP')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting AI Service Backend MVP on {args.host}:{args.port}")
    print(f"📊 Models file: {MODELS_FILE}")
    print(f"🔗 ErrorLogger: {ERRORLOGGER_URL}")
    print(f"🌐 Web interface: http://localhost:{args.port}")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use!")
            print(f"💡 Try: sudo lsof -i :{args.port} to see what's using it")
            sys.exit(1)
        else:
            raise
