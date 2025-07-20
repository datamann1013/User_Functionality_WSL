import os
import json
import subprocess
import webbrowser

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

def ensure_model_files(model):
    model_dir = os.path.join(MODELS_DIR, model['id'])
    model_file = os.path.join(model_dir, 'pytorch_model.bin')
    token = os.environ.get("HF_TOKEN")
    if not os.path.exists(model_dir) or not os.path.exists(model_file):
        print(f"Model directory or model file for {model['id']} not found. Downloading from HuggingFace...")
        os.makedirs(model_dir, exist_ok=True)
        if not token:
            print("HuggingFace access token (HF_TOKEN) not found in environment.")
            print("Opening browser to HuggingFace token page. Please create a token and set it as HF_TOKEN, then rerun this script.")
            webbrowser.open("https://huggingface.co/settings/tokens")
            exit(1)
        # Download the model file using wget with the token
        try:
            subprocess.run([
                "wget", "--header", f"Authorization: Bearer {token}", "-O", model_file, HUGGINGFACE_MODEL_URL
            ], check=True)
            print(f"Model {model['id']} downloaded and set up.")
        except Exception as e:
            print(f"Failed to download model: {e}")
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
