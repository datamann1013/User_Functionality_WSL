import os
import json
import webbrowser
import requests

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '../backend/registry/models.json')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '../backend/models')
DEFAULT_MODEL = {
    "id": "mistral-7b-v1",
    "name": "Mistral 7B",
    "icon": "🤖",
    "state": "online",
    "version": "v1.2.3"
}
ERRORLOGGER_SERVICE_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://localhost:5001/log')

def is_wsl():
    # Detect if running in WSL
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False

def log_error_to_service(error_code, message=None, exception=None, extra=None):
    """
    Send an error log to the ErrorLogger service via HTTP POST.
    """
    payload = {
        'error_code': error_code,
        'message': message,
        'exception': exception,
        'extra': extra
    }
    try:
        requests.post(ERRORLOGGER_SERVICE_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ErrorLogger Service Unreachable] {e}")

def ensure_online_model():
    if not os.path.exists(REGISTRY_PATH):
        print(f"models.json not found, creating new registry at {REGISTRY_PATH}")
        models = [DEFAULT_MODEL]
    else:
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            try:
                models = json.load(f)
            except Exception:
                models = []
        online = any(m.get('state') == 'online' for m in models)
        if not online:
            print("No online models found. Adding default model.")
            models.append(DEFAULT_MODEL)
        else:
            print("At least one online model already present.")
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)
    print(f"models.json updated. Current models: {models}")
    # Model files are now handled by setup_models.py

if __name__ == "__main__":
    ensure_online_model()
