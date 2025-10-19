"""
Ollama service integration module
"""
import os
import sys
import requests
from datetime import datetime

# Import project-wide ErrorLogger with error handling
try:
    sys.path.append('/app')
    from ErrorLogger.logger import log_error_remote
    ERROR_LOGGER_AVAILABLE = True
except ImportError:
    ERROR_LOGGER_AVAILABLE = False
    def log_error_remote(error_code, message=None, exception=None, extra=None):
        """Fallback error logging when ErrorLogger is not available"""
        print(f"ERROR {error_code}: {message} - {exception}")

# Wrapper function to add service name
def log_to_errorlogger(error_code, message=None, exception=None, extra=None):
    """Log to ErrorLogger with proper service identification"""
    if extra is None:
        extra = {}
    extra['service'] = 'ai_service'
    return log_error_remote(error_code, message, exception, extra)

OLLAMA_SERVICE_URL = os.environ.get('OLLAMA_SERVICE_URL', 'http://127.0.0.1:5002')

def check_ollama_service():
    """Check if Ollama service is available"""
    try:
        # Check our Ollama service wrapper first
        response = requests.get(f"{OLLAMA_SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            return True
        
        # Fallback to direct Ollama API
        response = requests.get("http://127.0.0.1:11434/api/version", timeout=5)
        return response.status_code == 200
    except:
        return False

def route_to_ollama_chat(message, agent_id):
    """Route chat request to Ollama service with agent-specific parameters and memory context"""
    try:
        # Import here to avoid circular imports
        from database_postgres import db
        
        # Look up agent from database to get their parameters
        agent = db.get_agent(agent_id)
        if not agent:
            log_to_errorlogger('EABA01', f'Agent {agent_id} not found in database')
            # Use default agent parameters
            agent = {
                'model_name': 'llama3.2:1b',
                'temperature': 0.7,
                'top_p': 0.9,
                'system_prompt': '',
                'max_tokens': 2048
            }
        
        # Get agent's important memories to provide context
        try:
            memories = db.get_agent_memories(agent_id, min_importance=0.6, limit=10)
            memory_context = ""
            
            if memories:
                memory_items = []
                for memory in memories:
                    memory_items.append(memory['content'])
                    # Update access time for memories we're using
                    db.update_memory_access(memory['id'])
                
                if memory_items:
                    memory_context = f"\n\nImportant context from previous conversations:\n{'; '.join(memory_items)}"
        except Exception as e:
            log_to_errorlogger('EABA02', f'Failed to retrieve memories for agent {agent_id}', exception=e)
            memory_context = ""
        
        # Prepare the full message with context
        system_prompt = agent.get('system_prompt', '') + memory_context
        
        # Convert Decimal objects to float for JSON serialization
        temperature = agent.get('temperature', 0.7)
        top_p = agent.get('top_p', 0.9)
        
        # Handle Decimal types from database
        if hasattr(temperature, '__float__'):
            temperature = float(temperature)
        if hasattr(top_p, '__float__'):
            top_p = float(top_p)
        
        payload = {
            'message': message,
            'agent_id': agent_id,
            'model_name': agent.get('model_name', 'llama3.2:1b'),
            'temperature': temperature,
            'top_p': top_p,
            'max_tokens': agent.get('max_tokens', 2048),
            'system_prompt': system_prompt,
            'timestamp': datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{OLLAMA_SERVICE_URL}/api/chat",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        return None
        
    except requests.exceptions.RequestException as e:
        log_to_errorlogger('EABA03', 'Ollama service request failed', exception=e)
        return None
    except Exception as e:
        log_to_errorlogger('EABA04', 'Ollama routing error', exception=e)
        return None

def get_ollama_models():
    """Get available models from Ollama service"""
    try:
        # First try our Ollama service wrapper
        response = requests.get(f"{OLLAMA_SERVICE_URL}/api/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            # Convert model list to the expected format
            return [{'name': model} for model in models]
        
        # Fallback to direct Ollama API
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('models', [])
        return []
    except Exception as e:
        log_to_errorlogger('EABA05', 'Failed to get available models', exception=e)
        return []

def download_model(model_name):
    """Download a model through Ollama service"""
    try:
        payload = {'name': model_name}
        response = requests.post(
            f"{OLLAMA_SERVICE_URL}/api/pull",
            json=payload,
            timeout=300  # 5 minutes for model download
        )
        return response.status_code == 200
    except:
        return False
