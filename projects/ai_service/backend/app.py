#!/usr/bin/env python3
"""
AI Service Backend - Optimized and Modularized
Connects to project-wide ErrorLogger service for logging
"""
import os
import sys
import json
import argparse
import base64
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Import modules
from database_postgres import db
from api.ollama import check_ollama_service, route_to_ollama_chat, get_ollama_models, download_model
from utils.files import save_avatar_file, get_avatar_url, UPLOAD_FOLDER

# Import project-wide ErrorLogger
sys.path.append('/app')
from ErrorLogger.logger import log_error_remote

# Wrapper function to add service name
def log_to_errorlogger(error_code, message=None, exception=None, extra=None):
    """Log to ErrorLogger with proper service identification"""
    # Add service name to extra data
    if extra is None:
        extra = {}
    extra['service'] = 'ai_service'
    
    return log_error_remote(error_code, message, exception, extra)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def extract_and_store_memory(agent_id, user_message, ai_response):
    """Extract and store important conversation context"""
    try:
        # Simple keyword-based importance scoring
        keywords = ['important', 'remember', 'key', 'critical', 'note', 'save']
        combined_text = f"{user_message} {ai_response}".lower()
        importance = sum(0.1 for keyword in keywords if keyword in combined_text)
        
        if importance > 0 or len(user_message) > 100:  # Store longer conversations
            db.store_memory(agent_id, f"User: {user_message} | AI: {ai_response}", importance)
    except Exception as e:
        log_to_errorlogger('EABM01', 'Failed to extract memory', exception=e)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with Ollama integration"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        agent_id = data.get('agent_id', 'assistant-1')
        
        if not message:
            return jsonify({
                'error': 'Empty message',
                'message': 'Please type a message to send to your AI agent.'
            }), 400
        
        # Set agent as busy before processing
        db.update_agent_status(agent_id, 'busy')
        
        log_to_errorlogger('IABC01', f'Chat request received: "{message[:50]}..."', 
                          extra={'agent_id': agent_id, 'message_length': len(message)})
        
        try:
            # Check Ollama service availability
            if not check_ollama_service():
                db.update_agent_status(agent_id, 'offline')
                return jsonify({
                    'error': 'AI service unavailable',
                    'message': 'The Ollama AI service is not responding. Please try restarting the service or check your connection.',
                    'code': 'EABC01'
                }), 503
            
            log_to_errorlogger('IABC02', f'Routing to Ollama service for agent {agent_id}')
            start_time = time.time()
            ollama_response = route_to_ollama_chat(message, agent_id)
            response_time = int((time.time() - start_time) * 1000)
            
            if not ollama_response:
                db.update_agent_status(agent_id, 'idle')
                return jsonify({
                    'error': 'AI processing failed',
                    'message': 'The AI couldn\'t process your message right now. This might be due to a model issue or network problem. Please try again in a moment.',
                    'code': 'EABC02',
                    'suggestions': ['Try rephrasing your message', 'Check if the AI model is still downloading', 'Restart the conversation']
                }), 500
            
            log_to_errorlogger('IABC03', 
                             f'Ollama response for agent {agent_id}: "{ollama_response.get("response", "")[:50]}..."')
            
            # Log conversation and extract memory
            try:
                db.log_conversation(
                    agent_id=agent_id,
                    user_message=message,
                    ai_response=ollama_response.get('response', ''),
                    model_used=ollama_response.get('model_name', 'unknown'),
                    parameters_used=ollama_response.get('parameters_used', {}),
                    tokens_used=ollama_response.get('tokens_used', 0),
                    response_time_ms=response_time,
                    session_id=data.get('session_id')
                )
                extract_and_store_memory(agent_id, message, ollama_response.get('response', ''))
                log_to_errorlogger('IABC04', f'Conversation logged for agent {agent_id}')
            except Exception as e:
                log_to_errorlogger('EABC03', 'Failed to log conversation', exception=e)
            
            # Set agent back to idle after successful response
            db.update_agent_status(agent_id, 'idle')
            return jsonify(ollama_response)
        
        except Exception as inner_e:
            log_to_errorlogger('EABC04', 'Error during chat processing', exception=inner_e)
            db.update_agent_status(agent_id, 'idle')
            return jsonify({
                'error': 'Chat processing failed',
                'message': 'An unexpected error occurred. Please try restarting the AI service.',
                'code': 'EABC04'
            }), 500
        
    except Exception as e:
        log_to_errorlogger('EABC05', 'Chat request failed', exception=e)
        try:
            db.update_agent_status(agent_id, 'idle')
        except:
            pass
        return jsonify({
            'error': 'Technical Error - Chat System Failed',
            'message': 'An unexpected server error occurred in the chat system. This is not something you can fix.',
            'error_code': 'EABC05',
            'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues with this error code.'
        }), 500

@app.route('/api/log-frontend-error', methods=['POST'])
def log_frontend_error():
    """Receive error logs from frontend and forward to ErrorLogger"""
    try:
        data = request.get_json()
        
        success = log_to_errorlogger(
            error_code=data.get('error_code', 'EAFX01'),
            message=data.get('message', 'Frontend error occurred'),
            exception=data.get('exception'),
            extra={**data.get('extra', {}), 'source': 'frontend'}
        )
        
        return jsonify({'status': 'logged' if success else 'failed'}), 200 if success else 503
            
    except Exception as e:
        log_to_errorlogger('EAFX02', 'Error processing frontend log', exception=e)
        return jsonify({'error': 'Failed to process error log'}), 500

@app.route('/health', methods=['GET'])
def health_root():
    """Root health check endpoint for monitoring"""
    return health()

@app.route('/api/health', methods=['GET'])
def health():
    """Simple health check endpoint"""
    try:
        log_to_errorlogger('IAXX1', 'Health check called')
        errorlogger_status = 'ok'  # If we reach here, ErrorLogger is working
        ollama_status = 'ok' if check_ollama_service() else 'unavailable'
        
        return jsonify({
            'status': 'ok',
            'service': 'ai_service',
            'timestamp': datetime.now().isoformat(),
            'errorlogger_status': errorlogger_status,
            'ollama_service_status': ollama_status
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/ollama/status', methods=['GET'])
def ollama_status():
    """Get detailed Ollama service status"""
    try:
        if check_ollama_service():
            models = get_ollama_models()
            return jsonify({
                'status': 'available',
                'models_count': len(models),
                'models': [{'name': model.get('name', 'unknown')} for model in models]
            })
        else:
            return jsonify({
                'status': 'unavailable',
                'message': 'Ollama service is not responding. Please restart the service.'
            }), 503
    except Exception as e:
        log_to_errorlogger('EABS06', 'Failed to get Ollama status', exception=e)
        return jsonify({
            'status': 'error', 
            'error': 'Technical Error - Service Status Check Failed',
            'message': 'Unable to check AI service status due to a server error.',
            'error_code': 'EABS06',
            'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues with this error code.'
        }), 500

# Agent management endpoints
@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    try:
        agents = db.get_all_agents()
        return jsonify({'agents': agents})
    except Exception as e:
        log_to_errorlogger('EABD01', 'Failed to get agents', exception=e)
        return jsonify({
            'error': 'Technical Error - Database Connection Failed',
            'message': 'Unable to connect to the database to load your AI agents. This is a server-side issue.',
            'error_code': 'EABD01', 
            'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues with this error code.'
        }), 500

@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create a new agent"""
    try:
        # Check content type
        if not request.is_json and not request.content_type.startswith('multipart/form-data'):
            log_to_errorlogger('EABD05', f'Invalid content type for agent creation: {request.content_type}')
            return jsonify({
                'error': 'Technical Error - Unsupported Content Type',
                'message': 'There is a technical issue with how your request was formatted. This is likely a bug in the application.',
                'error_code': 'EABD05',
                'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues',
                'technical_details': {
                    'received_content_type': request.content_type,
                    'supported_types': ['application/json', 'multipart/form-data']
                }
            }), 415
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            if data is None:
                log_to_errorlogger('EABD06', 'No JSON data received for agent creation')
                return jsonify({
                    'error': 'Technical Error - Empty JSON Request',
                    'message': 'The application sent an empty request. This is likely a bug in the frontend.',
                    'error_code': 'EABD06',
                    'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues'
                }), 400
        else:
            # Handle multipart/form-data (for file uploads)
            data = request.form.to_dict()
            # Convert string values back to appropriate types
            if 'temperature' in data:
                try:
                    data['temperature'] = float(data['temperature'])
                except (ValueError, TypeError):
                    return jsonify({
                        'error': 'Invalid temperature',
                        'message': 'Temperature must be a number between 0 and 1.'
                    }), 400
            if 'top_p' in data:
                try:
                    data['top_p'] = float(data['top_p'])
                except (ValueError, TypeError):
                    return jsonify({
                        'error': 'Invalid top_p',
                        'message': 'Top P must be a number between 0 and 1.'
                    }), 400
            if 'max_tokens' in data:
                try:
                    data['max_tokens'] = int(data['max_tokens'])
                except (ValueError, TypeError):
                    return jsonify({
                        'error': 'Invalid max_tokens',
                        'message': 'Maximum tokens must be a whole number.'
                    }), 400
        
        # Validate required fields
        if not data.get('name') or not data.get('name').strip():
            return jsonify({
                'error': 'Missing agent name',
                'message': 'Please provide a name for your AI agent. This helps you identify it later.'
            }), 400
            
        if not data.get('model_name'):
            return jsonify({
                'error': 'Missing model selection',
                'message': 'Please select an AI model for your agent. Popular options include llama3.2:1b for fast responses or llama3.1:8b for better quality.'
            }), 400
        
        # Validate ranges
        temperature = data.get('temperature', 0.7)
        if not (0 <= temperature <= 1):
            return jsonify({
                'error': 'Temperature out of range',
                'message': 'Temperature must be between 0 (very focused) and 1 (very creative). Try 0.7 for balanced responses.'
            }), 400
            
        top_p = data.get('top_p', 0.9)
        if not (0 <= top_p <= 1):
            return jsonify({
                'error': 'Top P out of range', 
                'message': 'Top P must be between 0 and 1. This controls response variety - try 0.9 for good balance.'
            }), 400
            
        max_tokens = data.get('max_tokens', 2048)
        if not (1 <= max_tokens <= 8192):
            return jsonify({
                'error': 'Max tokens out of range',
                'message': 'Maximum tokens must be between 1 and 8192. This limits response length - try 2048 for most conversations.'
            }), 400
            
        agent_data = {
            'name': data.get('name').strip(),
            'model_name': data.get('model_name'),
            'system_prompt': data.get('system_prompt', '').strip(),
            'temperature': temperature,
            'top_p': top_p,
            'max_tokens': max_tokens,
            'avatar_url': data.get('avatar_url')
        }
        
        agent = db.create_agent(agent_data)
        return jsonify({
            'agent_id': agent.get('id'), 
            'status': 'created',
            'message': f'Agent "{agent_data["name"]}" has been created successfully!'
        })
    except Exception as e:
        log_to_errorlogger('EABD02', 'Failed to create agent', exception=e)
        return jsonify({
            'error': 'Technical Error - Agent Creation Failed',
            'message': 'An unexpected server error occurred while creating your agent. This is not something you can fix.',
            'error_code': 'EABD02',
            'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues with this error code.'
        }), 500

@app.route('/api/agents/<agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Update an agent"""
    try:
        data = request.get_json()
        success = db.update_agent(agent_id, data)
        return jsonify({'status': 'updated' if success else 'failed'})
    except Exception as e:
        log_to_errorlogger('EABD03', f'Failed to update agent {agent_id}', exception=e)
        return jsonify({'error': 'Failed to update agent'}), 500

@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete an agent"""
    try:
        success = db.delete_agent(agent_id)
        return jsonify({'status': 'deleted' if success else 'failed'})
    except Exception as e:
        log_to_errorlogger('EABD04', f'Failed to delete agent {agent_id}', exception=e)
        return jsonify({'error': 'Failed to delete agent'}), 500

# Avatar upload endpoint
@app.route('/api/upload-avatar', methods=['POST'])
def upload_avatar():
    """Upload avatar file"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please select an image file to upload as your agent\'s avatar.'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please choose an image file from your device.'
            }), 400
        
        filename = save_avatar_file(file)
        if filename:
            avatar_url = get_avatar_url(filename)
            return jsonify({
                'avatar_url': avatar_url, 
                'filename': filename,
                'message': 'Avatar uploaded successfully!'
            })
        else:
            return jsonify({
                'error': 'Invalid file type',
                'message': 'Please upload a valid image file (JPG, PNG, GIF, or WebP). The file should be less than 5MB.',
                'supported_formats': ['jpg', 'jpeg', 'png', 'gif', 'webp']
            }), 400
    except Exception as e:
        log_to_errorlogger('EABF01', 'Failed to upload avatar', exception=e)
        return jsonify({
            'error': 'Upload failed',
            'message': 'Something went wrong while uploading your avatar. Please try again with a different image or contact support if the problem continues.'
        }), 500

@app.route('/api/avatars/<filename>')
def serve_avatar(filename):
    """Serve avatar files"""
    return send_from_directory(UPLOAD_FOLDER, filename)

# Model management endpoint
@app.route('/api/models/download', methods=['POST'])
def download_model_endpoint():
    """Download a model through Ollama"""
    try:
        data = request.get_json()
        model_name = data.get('model_name')
        
        if not model_name:
            return jsonify({
                'error': 'Missing model name',
                'message': 'Please specify which AI model you want to download (e.g., "llama3.2:1b").'
            }), 400
        
        success = download_model(model_name)
        if success:
            return jsonify({
                'status': 'downloaded',
                'message': f'Model "{model_name}" has been downloaded successfully and is ready to use!'
            })
        else:
            return jsonify({
                'status': 'failed',
                'error': 'Download failed',
                'message': f'Could not download model "{model_name}". Please check the model name and your internet connection.'
            })
    except Exception as e:
        log_to_errorlogger('EABM02', f'Failed to download model {model_name}', exception=e)
        return jsonify({
            'error': 'Technical Error - Model Download Service Failed',
            'message': f'An unexpected server error occurred while downloading model "{model_name}". This is a technical issue.',
            'error_code': 'EABM02',
            'action_required': 'Please contact the administrator or create a ticket at https://github.com/datamann1013/User_Functionality_WSL/issues with this error code.'
        }), 500

def check_and_download_agent_models():
    """Check and download models for saved agents"""
    try:
        agents = db.get_all_agents()
        available_models = {model.get('name') for model in get_ollama_models()}
        
        all_ready = True
        for agent in agents:
            model_name = agent.get('model_name')
            if model_name and model_name not in available_models:
                log_to_errorlogger('EABM03', f'Model {model_name} not available for agent {agent["id"]}')
                db.update_agent_status(agent['id'], 'offline')
                all_ready = False
            else:
                db.update_agent_status(agent['id'], 'idle')
        
        return all_ready
    except Exception as e:
        log_to_errorlogger('EABM04', 'Failed to check agent models', exception=e)
        return False

def main():
    """Main function to start the service"""
    parser = argparse.ArgumentParser(description='AI Service Backend')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    # Log startup and check ErrorLogger connection
    startup_success = log_to_errorlogger('IABS7', f'AI Service starting up on {args.host}:{args.port}')
    
    # Test ErrorLogger connection and log results
    if startup_success:
        log_to_errorlogger('IABS8', 'ErrorLogger connection established successfully')
    else:
        # Only use print for critical startup message when ErrorLogger is unavailable
        print(f"⚠️  ErrorLogger service unavailable - running without centralized logging")
    
    # Check and download models for saved agents
    log_to_errorlogger('IABM01', 'Starting agent model availability check')
    agent_models_ready = check_and_download_agent_models()
    
    if agent_models_ready:
        log_to_errorlogger('IABM02', 'All agent models are available and ready')
    else:
        log_to_errorlogger('WABM01', 'Some agent models unavailable - agents marked offline')
    
    log_to_errorlogger('IABS9', 'AI Service fully initialized and ready to serve requests')
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            log_to_errorlogger('EABS07', f'Port {args.port} is already in use', exception=e)
            sys.exit(1)
        else:
            log_to_errorlogger('EABS08', 'Unexpected error during service startup', exception=e)
            raise

if __name__ == '__main__':
    main()
