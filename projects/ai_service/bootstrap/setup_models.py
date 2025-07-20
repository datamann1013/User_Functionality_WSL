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

def download_model(model_url, model_path):
    """
    Download the model file from the given URL to the specified path if it does not exist.
    """
    if os.path.exists(model_path):
        print(f"Model file already exists at {model_path}")
        return
    print(f"Downloading model from {model_url} to {model_path}...")
    try:
        response = requests.get(model_url, stream=True)
        response.raise_for_status()
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Model downloaded successfully to {model_path}")
    except Exception as e:
        print(f"Failed to download model: {e}")
        log_error_to_service('MODEL_DOWNLOAD_FAILED', str(e))

def ensure_online_model():
    # Always overwrite models.json with only the DEFAULT_MODEL
    models = [DEFAULT_MODEL]
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)
    print(f"models.json overwritten with only the default model: {models}")

    # Download the model file if not present
    model_url = "https://huggingface.co/mistralai/Mistral-7B-v0.1"  # TODO: Replace with actual model URL
    model_path = os.path.join(MODELS_DIR, "mistral-7b-v1.bin")
    os.makedirs(MODELS_DIR, exist_ok=True)
    download_model(model_url, model_path)

if __name__ == "__main__":
    ensure_online_model()
