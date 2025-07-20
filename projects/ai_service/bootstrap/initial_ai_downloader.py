import os
import json
import subprocess
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
HUGGINGFACE_MODEL_URL = "https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main/pytorch_model.bin"
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

def ensure_model_files(model):
    model_dir = os.path.join(MODELS_DIR, model['id'])
    model_file = os.path.join(model_dir, 'pytorch_model.bin')
    token = os.environ.get("HF_TOKEN")
    if not os.path.exists(model_dir) or not os.path.exists(model_file):
        print(f"Model directory or model file for {model['id']} not found. Downloading from HuggingFace...")
        os.makedirs(model_dir, exist_ok=True)
        if not token:
            msg = "HuggingFace access token (HF_TOKEN) not found in environment."
            print(msg)
            log_error_to_service(
                error_code="SETUP01",
                message=msg,
                exception="User did not set HF_TOKEN."
            )
            print("Please open this URL in your browser to create a token:")
            print("  https://huggingface.co/settings/tokens\n")
            print("After creating a token, run: export HF_TOKEN=your_token_here and rerun this script.")
            if not is_wsl():
                try:
                    webbrowser.open("https://huggingface.co/settings/tokens")
                except Exception:
                    pass
            exit(1)
        # Download the model file using wget with the token
        try:
            subprocess.run([
                "wget", "--header", f"Authorization: Bearer {token}", "-O", model_file, HUGGINGFACE_MODEL_URL
            ], check=True)
            print(f"Model {model['id']} downloaded and set up.")
        except Exception as e:
            err_msg = f"Failed to download model: {e}"
            print(err_msg)
            log_error_to_service(
                error_code="SETUP02",
                message=err_msg,
                exception=str(e)
            )
    else:
        print(f"Model directory and model file for {model['id']} already exist.")

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
    # Ensure model files for all online models
    os.makedirs(MODELS_DIR, exist_ok=True)
    for m in models:
        if m.get('state') == 'online':
            ensure_model_files(m)

if __name__ == "__main__":
    ensure_online_model()
