import os
import json
import requests
from transformers import snapshot_download

MODELS_DIR = os.path.join(os.path.dirname(__file__), '../backend/models')
REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '../backend/registry/models.json')
DEFAULT_MODEL_ID = "mistral-7b-v1"
HUGGINGFACE_REPO_ID = "mistralai/Mistral-7B-v0.1"
DEFAULT_MODEL = {
    "id": DEFAULT_MODEL_ID,
    "name": "Mistral 7B",
    "icon": "🤖",
    "state": "online",
    "version": "v1.2.3"
}
ERRORLOGGER_SERVICE_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://localhost:5001/log')

def is_wsl():
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False

def log_error_to_service(error_code, message=None, exception=None, extra=None):
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

def ensure_model_downloaded(model_id=DEFAULT_MODEL_ID, repo_id=HUGGINGFACE_REPO_ID):
    model_dir = os.path.abspath(os.path.join(MODELS_DIR, model_id))
    if os.path.exists(model_dir) and os.listdir(model_dir):
        print(f"Model directory for {model_id} already exists and is not empty.")
        return
    print(f"Downloading model {repo_id} to {model_dir}...")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HuggingFace access token (HF_TOKEN) not found in environment.")
    snapshot_download(
        repo_id=repo_id,
        cache_dir=model_dir,
        use_auth_token=token,
        local_files_only=False,
        resume_download=True
    )
    print(f"Model {model_id} downloaded and set up at {model_dir}.")

if __name__ == "__main__":
    ensure_online_model()
    ensure_model_downloaded()
