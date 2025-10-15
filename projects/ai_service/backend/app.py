#!/usr/bin/env python3
"""
AI Service Backend - Simplified
Connects to ErrorLogger service for logging
"""
import os
import sys
import json
import random
import argparse
import requests
import base64
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Import our database module
from database import db

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Configuration for file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'avatars')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Configuration
ERRORLOGGER_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://127.0.0.1:5001/log')
OLLAMA_SERVICE_URL = os.environ.get('OLLAMA_SERVICE_URL', 'http://127.0.0.1:5002')
SERVICE_NAME = 'ai_service'
MODELS_FILE = os.path.join(os.path.dirname(__file__), 'models.json')

# Global variables for model state
loaded_models = {}
active_model = None

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

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_avatar_file(file):
    """Save uploaded avatar file and return filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        timestamp = str(int(datetime.now().timestamp()))
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{timestamp}{ext}"
        
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        return filename
    return None

def get_avatar_url(filename):
    """Get URL for avatar file"""
    if filename:
        return f"/api/avatars/{filename}"
    return None

def check_ollama_service():
    """Check if Ollama service is available"""
    try:
        response = requests.get(f"{OLLAMA_SERVICE_URL}/health", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return data.get('ollama_status', {}).get('running', False)
        return False
    except requests.exceptions.RequestException:
        return False

def route_to_ollama_chat(message, agent_id):
    """Route chat request to Ollama service"""
    try:
        payload = {
            'message': message,
            'agent_id': agent_id
        }
        
        response = requests.post(f"{OLLAMA_SERVICE_URL}/api/chat", 
                               json=payload, timeout=60)
        
        if response.status_code == 200:
            return response.json()
        else:
            log_to_errorlogger('OLLAMA_ROUTE_ERROR', 
                             f'Ollama service error: {response.status_code}',
                             extra={'response': response.text})
            return None
            
    except requests.exceptions.Timeout:
        log_to_errorlogger('OLLAMA_ROUTE_TIMEOUT', 'Ollama service timeout')
        return None
    except requests.exceptions.RequestException as e:
        log_to_errorlogger('OLLAMA_ROUTE_REQUEST_ERROR', 'Ollama service request failed', e)
        return None
    except Exception as e:
        log_to_errorlogger('OLLAMA_ROUTE_GENERAL_ERROR', 'Ollama routing error', e)
        return None

# Default free model configuration
DEFAULT_MODEL = {
    "id": "free-assistant",
    "name": "Free Assistant",
    "provider": "demo",
    "model_type": "chat",
    "status": "idle",
    "last_active": None,
    "config": {
        "max_tokens": 512,
        "temperature": 0.7,
        "description": "Simple demonstration model - no API costs"
    }
}

def load_models_config():
    """Load models configuration from JSON file"""
    try:
        if os.path.exists(MODELS_FILE):
            with open(MODELS_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default model config if none exists
            default_config = {"models": [DEFAULT_MODEL]}
            save_models_config(default_config)
            return default_config
    except Exception as e:
        log_to_errorlogger('MODEL_CONFIG_LOAD_ERROR', 'Failed to load models config', e)
        return {"models": [DEFAULT_MODEL]}

def save_models_config(config):
    """Save models configuration to JSON file"""
    try:
        os.makedirs(os.path.dirname(MODELS_FILE), exist_ok=True)
        with open(MODELS_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        log_to_errorlogger('MODEL_CONFIG_SAVE_ERROR', 'Failed to save models config', e)
        return False

def initialize_model(model_config):
    """Initialize a model (demo implementation)"""
    global loaded_models, active_model
    
    model_id = model_config['id']
    log_to_errorlogger('MODEL_INIT_START', f'Initializing model: {model_id}')
    
    try:
        # For demo - just mark as loaded
        loaded_models[model_id] = {
            'config': model_config,
            'status': 'ready',
            'loaded_at': datetime.now().isoformat()
        }
        
        # Set as active if no active model
        if active_model is None:
            active_model = model_id
            
        log_to_errorlogger('MODEL_INIT_SUCCESS', f'Model initialized: {model_id}')
        return True
        
    except Exception as e:
        log_to_errorlogger('MODEL_INIT_ERROR', f'Failed to initialize model: {model_id}', e)
        return False

def startup_model_check():
    """Check and initialize models on startup"""
    global active_model
    
    config = load_models_config()
    models = config.get('models', [])
    
    if not models:
        log_to_errorlogger('STARTUP_NO_MODELS', 'No models configured, adding default')
        models = [DEFAULT_MODEL]
        save_models_config({"models": models})
    
    # Initialize first available model
    for model in models:
        if initialize_model(model):
            log_to_errorlogger('STARTUP_MODEL_READY', f'Startup model active: {model["id"]}')
            return True
    
    log_to_errorlogger('STARTUP_MODEL_FAIL', 'Failed to initialize any models')
    return False

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
    
    # Check Ollama service connectivity
    ollama_status = 'disconnected'
    try:
        response = requests.get(f"{OLLAMA_SERVICE_URL}/health", timeout=2)
        if response.status_code == 200:
            ollama_data = response.json()
            if ollama_data.get('ollama_status', {}).get('running', False):
                ollama_status = 'connected_with_ollama'
            else:
                ollama_status = 'connected_no_ollama'
    except Exception:
        pass
    
    return jsonify({
        'status': 'ok',
        'service': SERVICE_NAME,
        'timestamp': datetime.now().isoformat(),
        'errorlogger_status': errorlogger_status,
        'ollama_service_status': ollama_status,
        'demo_model_active': active_model
    })

@app.route('/api/ollama/status', methods=['GET'])
def ollama_status():
    """Get detailed Ollama service status"""
    try:
        response = requests.get(f"{OLLAMA_SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Ollama service not responding', 'status_code': response.status_code}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Cannot connect to Ollama service', 'details': str(e)}), 503

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with Ollama integration and demo fallback"""
    global active_model
    
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        agent_id = data.get('agent_id', 'assistant-1')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        log_to_errorlogger('AI_CHAT_REQUEST', f'Chat request: "{message[:50]}..."', 
                          extra={'agent_id': agent_id, 'message_length': len(message)})
        
        # Try Ollama service first
        if check_ollama_service():
            log_to_errorlogger('AI_CHAT_OLLAMA_ROUTE', f'Routing to Ollama service for agent {agent_id}')
            ollama_response = route_to_ollama_chat(message, agent_id)
            
            if ollama_response:
                log_to_errorlogger('AI_CHAT_OLLAMA_SUCCESS', 
                                 f'Ollama response for agent {agent_id}: "{ollama_response.get("response", "")[:50]}..."')
                return jsonify(ollama_response)
            else:
                log_to_errorlogger('AI_CHAT_OLLAMA_FALLBACK', 
                                 'Ollama service failed, falling back to demo model')
        else:
            log_to_errorlogger('AI_CHAT_OLLAMA_UNAVAILABLE', 
                             'Ollama service unavailable, using demo model')
        
        # Fallback to demo model functionality
        # Check if we have an active demo model
        if not active_model or active_model not in loaded_models:
            # Try to initialize a model if none active
            if not startup_model_check():
                return jsonify({'error': 'No AI models available'}), 503
        
        # Get active demo model info
        model_info = loaded_models.get(active_model, {})
        model_name = model_info.get('config', {}).get('name', 'AI Assistant')
        
        # Generate contextual response using demo model
        message_lower = message.lower()
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            response = f"Hello! I'm {model_name}, your AI assistant. How can I help you today?"
        elif any(word in message_lower for word in ['model', 'who are you']):
            response = f"I'm {model_name}, a free demonstration model. I'm running locally without any API costs."
        elif any(word in message_lower for word in ['test', 'testing']):
            response = f"Great! {model_name} is working correctly. All systems are operational."
        elif any(word in message_lower for word in ['error', 'log']):
            response = f"I'm {model_name}, integrated with the ErrorLogger service for comprehensive monitoring."
        elif any(word in message_lower for word in ['ollama', 'real ai', 'actual ai']):
            response = f"I'm currently using {model_name} demo mode. The Ollama AI service is available but not responding. Real AI capabilities can be enabled when Ollama is properly configured."
        else:
            responses = [
                f"I'm {model_name}, ready to assist you with any questions or tasks.",
                f"How can {model_name} help you today?",
                f"I'm here as {model_name} to demonstrate the AI service functionality.",
                f"Thanks for using {model_name}! The system is working perfectly.",
                f"This is {model_name} responding from the AI service backend."
            ]
            response = random.choice(responses)
        
        result = {
            'response': response,
            'agent_id': agent_id,
            'model_id': active_model,
            'model_name': model_name,
            'timestamp': datetime.now().isoformat(),
            'mode': 'demo_fallback',
            'ollama_available': False
        }
        
        log_to_errorlogger('AI_CHAT_DEMO_RESPONSE', f'Demo response from {active_model}: "{response[:50]}..."',
                          extra={'agent_id': agent_id, 'model_id': active_model, 'response_length': len(response)})
        
        return jsonify(result)
        
    except Exception as e:
        log_to_errorlogger('AI_CHAT_ERROR', 'Chat request failed', e)
        return jsonify({'error': 'Chat request failed', 'details': str(e)}), 500

# ================================
# AGENT MANAGEMENT API ENDPOINTS
# ================================

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    try:
        agents = db.get_all_agents()
        
        # Update agent status based on model availability
        for agent in agents:
            model_available = check_model_availability(agent['model_name'])
            current_status = 'idle' if model_available else 'offline'
            
            # Update status in database if it changed
            if agent['status'] != current_status:
                db.update_agent_status(agent['id'], current_status)
                agent['status'] = current_status
        
        log_to_errorlogger('AGENTS_LIST_SUCCESS', f'Retrieved {len(agents)} agents')
        return jsonify({'agents': agents, 'count': len(agents)})
        
    except Exception as e:
        log_to_errorlogger('AGENTS_LIST_ERROR', 'Failed to retrieve agents', e)
        return jsonify({'error': 'Failed to retrieve agents', 'details': str(e)}), 500

@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create a new agent"""
    try:
        # Handle both JSON and form data
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Form data with file upload
            data = {
                'name': request.form.get('name'),
                'model_name': request.form.get('model_name'),
                'temperature': float(request.form.get('temperature', 0.7)),
                'top_p': float(request.form.get('top_p', 0.9)),
                'system_prompt': request.form.get('system_prompt', 'You are a helpful AI assistant.'),
                'max_tokens': int(request.form.get('max_tokens', 2048))
            }
            
            # Handle avatar upload
            avatar_filename = None
            if 'avatar_image' in request.files:
                file = request.files['avatar_image']
                if file.filename != '':
                    avatar_filename = save_avatar_file(file)
                    if avatar_filename:
                        data['avatar_image'] = get_avatar_url(avatar_filename)
            
        else:
            # JSON data
            data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create the agent
        agent = db.create_agent(data)
        
        # Check if the model is available and update status
        model_available = check_model_availability(agent['model_name'])
        initial_status = 'idle' if model_available else 'offline'
        
        if agent['status'] != initial_status:
            db.update_agent_status(agent['id'], initial_status)
            agent['status'] = initial_status
        
        log_to_errorlogger('AGENT_CREATE_SUCCESS', f'Created agent: {agent["name"]} with model {agent["model_name"]}',
                          extra={'agent_id': agent['id'], 'model': agent['model_name']})
        
        return jsonify(agent), 201
        
    except ValueError as e:
        log_to_errorlogger('AGENT_CREATE_VALIDATION_ERROR', 'Agent creation validation failed', e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        log_to_errorlogger('AGENT_CREATE_ERROR', 'Failed to create agent', e)
        return jsonify({'error': 'Failed to create agent', 'details': str(e)}), 500

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get a specific agent"""
    try:
        agent = db.get_agent(agent_id)
        
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Update status based on model availability
        model_available = check_model_availability(agent['model_name'])
        current_status = 'idle' if model_available else 'offline'
        
        if agent['status'] != current_status:
            db.update_agent_status(agent['id'], current_status)
            agent['status'] = current_status
        
        return jsonify(agent)
        
    except Exception as e:
        log_to_errorlogger('AGENT_GET_ERROR', f'Failed to get agent {agent_id}', e)
        return jsonify({'error': 'Failed to retrieve agent', 'details': str(e)}), 500

@app.route('/api/agents/<agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Update an existing agent"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        success = db.update_agent(agent_id, data)
        
        if not success:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Get updated agent
        agent = db.get_agent(agent_id)
        
        # Update status if model was changed
        if 'model_name' in data:
            model_available = check_model_availability(agent['model_name'])
            new_status = 'idle' if model_available else 'offline'
            db.update_agent_status(agent_id, new_status)
            agent['status'] = new_status
        
        log_to_errorlogger('AGENT_UPDATE_SUCCESS', f'Updated agent: {agent_id}')
        return jsonify(agent)
        
    except Exception as e:
        log_to_errorlogger('AGENT_UPDATE_ERROR', f'Failed to update agent {agent_id}', e)
        return jsonify({'error': 'Failed to update agent', 'details': str(e)}), 500

@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete an agent"""
    try:
        success = db.delete_agent(agent_id)
        
        if not success:
            return jsonify({'error': 'Agent not found'}), 404
        
        log_to_errorlogger('AGENT_DELETE_SUCCESS', f'Deleted agent: {agent_id}')
        return jsonify({'message': 'Agent deleted successfully'})
        
    except Exception as e:
        log_to_errorlogger('AGENT_DELETE_ERROR', f'Failed to delete agent {agent_id}', e)
        return jsonify({'error': 'Failed to delete agent', 'details': str(e)}), 500

@app.route('/api/models', methods=['GET'])
def get_available_models():
    """Get list of available models from Ollama"""
    try:
        models = []
        
        # Try to get models from Ollama service
        if check_ollama_service():
            try:
                response = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get('models', [])
            except requests.exceptions.RequestException:
                pass
        
        # Add default/common models if Ollama isn't available
        if not models:
            models = [
                'llama3.2:1b',
                'llama3.2:3b', 
                'llama3.1:8b',
                'codellama:7b',
                'mistral:7b',
                'gemma:2b',
                'phi3:mini'
            ]
        
        return jsonify({'models': models, 'ollama_available': check_ollama_service()})
        
    except Exception as e:
        log_to_errorlogger('MODELS_LIST_ERROR', 'Failed to retrieve models', e)
        return jsonify({'error': 'Failed to retrieve models', 'details': str(e)}), 500

@app.route('/api/models/check/<model_name>', methods=['GET'])
def check_specific_model(model_name):
    """Check if a specific model is available"""
    try:
        available = check_model_availability(model_name)
        return jsonify({'model': model_name, 'available': available})
    except Exception as e:
        log_to_errorlogger('MODEL_CHECK_ERROR', f'Failed to check model {model_name}', e)
        return jsonify({'error': 'Failed to check model availability', 'details': str(e)}), 500

@app.route('/api/models/download/<model_name>', methods=['POST'])
def download_model(model_name):
    """Download a model via Ollama"""
    try:
        if not check_ollama_service():
            return jsonify({'error': 'Ollama service not available'}), 503
        
        # Check if model is already available
        if check_model_availability(model_name):
            return jsonify({'success': True, 'message': 'Model already available'})
        
        # Request model download from Ollama service
        response = requests.post(f"{OLLAMA_SERVICE_URL}/api/models/pull", 
                               json={'model': model_name}, 
                               timeout=300)  # 5 minute timeout for downloads
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                # Update all agents using this model to 'idle' status
                agents_with_model = db.get_agents_by_model(model_name)
                for agent in agents_with_model:
                    db.update_agent_status(agent['id'], 'idle')
                
                log_to_errorlogger('MODEL_DOWNLOAD_SUCCESS', f'Downloaded model: {model_name}')
                return jsonify({'success': True, 'message': f'Model {model_name} downloaded successfully'})
            else:
                return jsonify({'success': False, 'error': data.get('error', 'Download failed')})
        else:
            return jsonify({'success': False, 'error': f'Ollama responded with status {response.status_code}'}), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Download timeout - model download may still be in progress'}), 408
    except Exception as e:
        log_to_errorlogger('MODEL_DOWNLOAD_ERROR', f'Failed to download model {model_name}', e)
        return jsonify({'success': False, 'error': 'Failed to download model', 'details': str(e)}), 500

@app.route('/api/avatars/<filename>')
def serve_avatar(filename):
    """Serve avatar images"""
    try:
        from flask import send_from_directory
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception as e:
        log_to_errorlogger('AVATAR_SERVE_ERROR', f'Failed to serve avatar {filename}', e)
        return jsonify({'error': 'Avatar not found'}), 404

def check_model_availability(model_name):
    """Check if a specific model is available in Ollama"""
    try:
        if not check_ollama_service():
            return False
        
        response = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            available_models = data.get('models', [])
            return model_name in available_models
        
        return False
        
    except requests.exceptions.RequestException:
        return False

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
    
    # Initialize models
    print(f"   🔧 Initializing AI models...")
    if startup_model_check():
        print(f"   ✅ AI model ready: {active_model}")
    else:
        print(f"   ⚠️  No AI models available (will run in fallback mode)")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use!")
            sys.exit(1)
        else:
            raise
