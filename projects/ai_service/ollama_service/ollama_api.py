#!/usr/bin/env python3
"""
Ollama API Service - Secondary Backend for Real AI
Handles multiple agents with different Ollama models
Supports both local and remote Ollama instances
"""
import os
import sys
import json
import time
import requests
import subprocess
import argparse
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
ERRORLOGGER_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://127.0.0.1:5001/log')
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
SERVICE_NAME = 'ollama_service'

# Agent to model mapping
AGENT_MODELS = {}
DEFAULT_MODEL = "llama3.2:1b"  # Lightweight model for general use
MODELS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'agent_models.json')

# Ollama status tracking
ollama_status = {
    'running': False,
    'models_available': [],
    'last_check': None
}

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
        return False

def check_ollama_installation():
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(['ollama', '--version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def install_ollama():
    """Install Ollama using the official installer"""
    log_to_errorlogger('OLLAMA_INSTALL_START', 'Installing Ollama')
    print("🔧 Installing Ollama...")
    
    try:
        # Download and run the Ollama installer
        install_cmd = 'curl -fsSL https://ollama.ai/install.sh | sh'
        result = subprocess.run(install_cmd, shell=True, 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            log_to_errorlogger('OLLAMA_INSTALL_SUCCESS', 'Ollama installed successfully')
            print("✅ Ollama installed successfully!")
            return True
        else:
            log_to_errorlogger('OLLAMA_INSTALL_ERROR', 'Ollama installation failed', 
                             extra={'output': result.stderr})
            print(f"❌ Ollama installation failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_to_errorlogger('OLLAMA_INSTALL_TIMEOUT', 'Ollama installation timed out')
        print("❌ Ollama installation timed out")
        return False
    except Exception as e:
        log_to_errorlogger('OLLAMA_INSTALL_EXCEPTION', 'Ollama installation exception', e)
        print(f"❌ Ollama installation error: {e}")
        return False

def start_ollama_service():
    """Start the Ollama service"""
    log_to_errorlogger('OLLAMA_START_ATTEMPT', 'Starting Ollama service')
    print("🚀 Starting Ollama service...")
    
    try:
        # Start Ollama in background
        subprocess.Popen(['ollama', 'serve'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        
        # Wait for service to be ready
        for attempt in range(30):  # 30 seconds timeout
            try:
                response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
                if response.status_code == 200:
                    log_to_errorlogger('OLLAMA_START_SUCCESS', 'Ollama service started')
                    print("✅ Ollama service is running!")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
            print(f"⏳ Waiting for Ollama... ({attempt + 1}/30)")
        
        log_to_errorlogger('OLLAMA_START_TIMEOUT', 'Ollama service start timeout')
        print("❌ Ollama service failed to start (timeout)")
        return False
        
    except Exception as e:
        log_to_errorlogger('OLLAMA_START_ERROR', 'Ollama service start error', e)
        print(f"❌ Error starting Ollama: {e}")
        return False

def check_ollama_status():
    """Check if Ollama service is running and get available models"""
    global ollama_status
    
    try:
        # Check if service is running
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            models = [model['name'] for model in models_data.get('models', [])]
            
            ollama_status = {
                'running': True,
                'models_available': models,
                'last_check': datetime.now().isoformat()
            }
            return True
        else:
            ollama_status['running'] = False
            return False
            
    except requests.exceptions.RequestException:
        ollama_status['running'] = False
        return False

def pull_model(model_name):
    """Pull/download a model in Ollama"""
    log_to_errorlogger('OLLAMA_PULL_START', f'Pulling model: {model_name}')
    print(f"📥 Downloading model: {model_name}")
    
    try:
        # Use Ollama CLI to pull the model
        result = subprocess.run(['ollama', 'pull', model_name], 
                              capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            log_to_errorlogger('OLLAMA_PULL_SUCCESS', f'Model pulled: {model_name}')
            print(f"✅ Model {model_name} downloaded successfully!")
            return True
        else:
            log_to_errorlogger('OLLAMA_PULL_ERROR', f'Model pull failed: {model_name}', 
                             extra={'output': result.stderr})
            print(f"❌ Failed to download {model_name}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_to_errorlogger('OLLAMA_PULL_TIMEOUT', f'Model pull timeout: {model_name}')
        print(f"❌ Model download timed out: {model_name}")
        return False
    except Exception as e:
        log_to_errorlogger('OLLAMA_PULL_EXCEPTION', f'Model pull exception: {model_name}', e)
        print(f"❌ Error downloading {model_name}: {e}")
        return False

def load_agent_models_config():
    """Load agent to model mapping configuration"""
    try:
        if os.path.exists(MODELS_CONFIG_FILE):
            with open(MODELS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default configuration
            default_config = {
                "agent_models": {
                    "assistant-1": DEFAULT_MODEL,
                    "default": DEFAULT_MODEL
                },
                "model_configs": {
                    DEFAULT_MODEL: {
                        "temperature": 0.7,
                        "max_tokens": 2048,
                        "description": "General purpose lightweight model"
                    }
                }
            }
            save_agent_models_config(default_config)
            return default_config
    except Exception as e:
        log_to_errorlogger('AGENT_CONFIG_LOAD_ERROR', 'Failed to load agent config', e)
        return {"agent_models": {"default": DEFAULT_MODEL}, "model_configs": {}}

def save_agent_models_config(config):
    """Save agent to model mapping configuration"""
    try:
        with open(MODELS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        log_to_errorlogger('AGENT_CONFIG_SAVE_ERROR', 'Failed to save agent config', e)
        return False

def ensure_ollama_ready():
    """Ensure Ollama is installed, running, and has required models"""
    global ollama_status
    
    print("🔍 Checking Ollama setup...")
    
    # Check installation
    if not check_ollama_installation():
        print("❌ Ollama not found. Installing...")
        if not install_ollama():
            return False
    
    # Check if service is running
    if not check_ollama_status():
        print("🚀 Starting Ollama service...")
        if not start_ollama_service():
            return False
    
    # Refresh status after starting
    check_ollama_status()
    
    # Check if default model is available
    if DEFAULT_MODEL not in ollama_status['models_available']:
        print(f"📥 Default model {DEFAULT_MODEL} not found. Downloading...")
        if not pull_model(DEFAULT_MODEL):
            print("⚠️  Failed to download default model. Service will use available models.")
    
    # Final status check
    check_ollama_status()
    print(f"✅ Ollama ready! Available models: {ollama_status['models_available']}")
    return True

# ==================== API ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    check_ollama_status()
    
    return jsonify({
        'status': 'ok',
        'service': SERVICE_NAME,
        'timestamp': datetime.now().isoformat(),
        'ollama_status': ollama_status
    })

@app.route('/api/models', methods=['GET'])
def get_models():
    """Get list of available models"""
    check_ollama_status()
    
    return jsonify({
        'models': ollama_status['models_available'],
        'running': ollama_status['running'],
        'last_check': ollama_status['last_check']
    })

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get agent to model mappings"""
    config = load_agent_models_config()
    
    return jsonify({
        'agent_models': config.get('agent_models', {}),
        'model_configs': config.get('model_configs', {})
    })

@app.route('/api/agents/<agent_id>/model', methods=['POST'])
def set_agent_model(agent_id):
    """Set model for specific agent"""
    data = request.get_json()
    model_name = data.get('model')
    
    if not model_name:
        return jsonify({'error': 'Model name required'}), 400
    
    check_ollama_status()
    
    if model_name not in ollama_status['models_available']:
        return jsonify({'error': f'Model {model_name} not available'}), 404
    
    # Update configuration
    config = load_agent_models_config()
    config['agent_models'][agent_id] = model_name
    
    if save_agent_models_config(config):
        log_to_errorlogger('AGENT_MODEL_UPDATE', f'Agent {agent_id} assigned to {model_name}')
        return jsonify({'success': True, 'agent_id': agent_id, 'model': model_name})
    else:
        return jsonify({'error': 'Failed to save configuration'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint using Ollama models"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        agent_id = data.get('agent_id', 'default')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        log_to_errorlogger('OLLAMA_CHAT_REQUEST', f'Chat request from agent {agent_id}: "{message[:50]}..."')
        
        # Check Ollama status
        if not check_ollama_status():
            return jsonify({'error': 'Ollama service not available'}), 503
        
        # Get model for this agent
        config = load_agent_models_config()
        agent_models = config.get('agent_models', {})
        model_name = agent_models.get(agent_id, agent_models.get('default', DEFAULT_MODEL))
        
        # Verify model is available
        if model_name not in ollama_status['models_available']:
            # Try to use default model
            model_name = DEFAULT_MODEL if DEFAULT_MODEL in ollama_status['models_available'] else None
            if not model_name and ollama_status['models_available']:
                model_name = ollama_status['models_available'][0]  # Use first available
            
            if not model_name:
                return jsonify({'error': 'No models available'}), 503
        
        # Prepare Ollama request
        ollama_payload = {
            'model': model_name,
            'prompt': message,
            'stream': False,
            'options': {
                'temperature': config.get('model_configs', {}).get(model_name, {}).get('temperature', 0.7),
                'num_predict': config.get('model_configs', {}).get(model_name, {}).get('max_tokens', 2048)
            }
        }
        
        # Send request to Ollama
        try:
            response = requests.post(f"{OLLAMA_HOST}/api/generate", 
                                   json=ollama_payload, timeout=60)
            
            if response.status_code == 200:
                ollama_response = response.json()
                ai_response = ollama_response.get('response', 'No response from model')
                
                result = {
                    'response': ai_response,
                    'agent_id': agent_id,
                    'model_id': model_name,
                    'model_name': model_name,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'ollama_powered',
                    'tokens_used': len(ai_response.split())  # Rough estimate
                }
                
                log_to_errorlogger('OLLAMA_CHAT_SUCCESS', 
                                 f'Response from {model_name} for agent {agent_id}: "{ai_response[:50]}..."')
                
                return jsonify(result)
            else:
                log_to_errorlogger('OLLAMA_API_ERROR', f'Ollama API error: {response.status_code}',
                                 extra={'response': response.text})
                return jsonify({'error': f'Ollama API error: {response.status_code}'}), 502
                
        except requests.exceptions.Timeout:
            log_to_errorlogger('OLLAMA_TIMEOUT', 'Ollama request timeout')
            return jsonify({'error': 'Model response timeout'}), 504
        except requests.exceptions.RequestException as e:
            log_to_errorlogger('OLLAMA_REQUEST_ERROR', 'Ollama request failed', e)
            return jsonify({'error': 'Failed to communicate with Ollama'}), 502
        
    except Exception as e:
        log_to_errorlogger('OLLAMA_CHAT_ERROR', 'Chat request failed', e)
        return jsonify({'error': 'Chat request failed', 'details': str(e)}), 500

@app.route('/api/models/pull', methods=['POST'])
def pull_model_endpoint():
    """Pull/download a new model"""
    data = request.get_json()
    model_name = data.get('model')
    
    if not model_name:
        return jsonify({'error': 'Model name required'}), 400
    
    if pull_model(model_name):
        check_ollama_status()  # Refresh model list
        return jsonify({'success': True, 'model': model_name})
    else:
        return jsonify({'error': f'Failed to pull model {model_name}'}), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Ollama API Service')
    parser.add_argument('--port', type=int, default=5002, help='Port to run on (default: 5002)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--skip-setup', action='store_true', help='Skip Ollama setup check')
    
    args = parser.parse_args()
    
    print(f"🤖 Starting Ollama API Service")
    print(f"   Host: {args.host}:{args.port}")
    print(f"   ErrorLogger: {ERRORLOGGER_URL}")
    print(f"   Ollama Host: {OLLAMA_HOST}")
    
    # Test ErrorLogger connection
    if log_to_errorlogger('OLLAMA_SERVICE_STARTUP', 'Ollama Service starting up'):
        print(f"   ✅ ErrorLogger connection: OK")
    else:
        print(f"   ⚠️  ErrorLogger connection: Failed (will run without logging)")
    
    # Setup Ollama if requested
    if not args.skip_setup:
        print("🔧 Setting up Ollama...")
        if ensure_ollama_ready():
            print("✅ Ollama setup complete")
        else:
            print("❌ Ollama setup failed - service will run with limited functionality")
    else:
        print("⏭️  Skipping Ollama setup check")
        check_ollama_status()
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use!")
            sys.exit(1)
        else:
            raise
