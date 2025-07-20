import os
import json
import webbrowser
import requests
from huggingface_hub import snapshot_download

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

def download_model(model_id, model_dir):
    """
    Download the full HuggingFace model repository to the specified directory if it does not exist.
    """
    if os.path.exists(model_dir) and os.path.isdir(model_dir) and os.listdir(model_dir):
        print(f"Model directory already exists at {model_dir}")
        return
    print(f"Downloading HuggingFace model repository for {model_id} to {model_dir}...")
    try:
        snapshot_download(repo_id=model_id, local_dir=model_dir, local_dir_use_symlinks=False)
        print(f"Model repository downloaded successfully to {model_dir}")
    except Exception as e:
        print(f"Failed to download model repository: {e}")
        log_error_to_service('MODEL_DOWNLOAD_FAILED', str(e))

def ensure_online_model():
    # Always overwrite models.json with only the DEFAULT_MODEL
    models = [DEFAULT_MODEL]
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)
    print(f"models.json overwritten with only the default model: {models}")

    # Download the full model repository if not present
    model_id = "mistralai/Mistral-7B-v0.1"  # HuggingFace repo id
    model_dir = os.path.join(MODELS_DIR, "mistral-7b-v1")
    os.makedirs(MODELS_DIR, exist_ok=True)
    download_model(model_id, model_dir)

if __name__ == "__main__":
    ensure_online_model()
