import os
import json
import webbrowser
import requests
import sys

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

REQUIRED_FILES = [
    "mistral-7b-v1.bin",  # Example model file
    "config.json"         # Example config file
]

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

def check_model_files(model_dir):
    missing = []
    for fname in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(model_dir, fname)):
            missing.append(fname)
    return missing

def ensure_online_model(debug=False):
    models = [DEFAULT_MODEL]
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)
    print(f"models.json overwritten with only the default model: {models}")
    model_dir = os.path.join(MODELS_DIR, DEFAULT_MODEL["id"])
    if debug:
        log_error_to_service("BOOT001", message="Backend startup: setup_models.py running", extra={"model_dir": model_dir})
    missing_files = check_model_files(model_dir)
    if missing_files:
        log_error_to_service("MODEL_MISSING", message="Missing model files", extra={"missing": missing_files})
        print(f"Missing model files: {missing_files}")
    else:
        print(f"All required model files present for {DEFAULT_MODEL['id']}")
        log_error_to_service("MODEL_OK", message="All required model files present", extra={"model_dir": model_dir})

if __name__ == "__main__":
    debug = "--debug" in sys.argv
    ensure_online_model(debug=debug)
