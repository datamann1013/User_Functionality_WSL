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

ERROR_CODE_DEFINITIONS = {
    "IABS1": "Setup model script started.",
    "IABS2": "All required model files present.",
    "EABS1": "Missing required model files.",
    "EABS2": "Failed to download model file.",
    "IABS3": "Model file downloaded successfully.",
    "E00000": "Python exception occurred.",
}

MODEL_FILE_URLS = {
    "mistral-7b-v1.bin": "https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main/pytorch_model.bin",
    "config.json": "https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main/config.json"
}

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

def get_error_explanation(error_code):
    return ERROR_CODE_DEFINITIONS.get(error_code, "No explanation provided")

def check_model_files(model_dir):
    missing = []
    for fname in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(model_dir, fname)):
            missing.append(fname)
    return missing

def download_model_file(model_dir, fname):
    url = MODEL_FILE_URLS.get(fname)
    if not url:
        log_error_to_service("EABS2", message=f"No download URL for {fname}", extra={"file": fname})
        return False
    try:
        log_error_to_service("IABS1", message=f"Downloading {fname} from {url}", extra={"file": fname})
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(os.path.join(model_dir, fname), 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        log_error_to_service("IABS3", message=f"Downloaded {fname}", extra={"file": fname})
        return True
    except Exception as e:
        log_error_to_service("EABS2", message=f"Failed to download {fname}", exception=str(e), extra={"file": fname, "url": url})
        return False

def ensure_online_model(debug=False):
    models = [DEFAULT_MODEL]
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)
    print(f"models.json overwritten with only the default model: {models}")
    model_dir = os.path.join(MODELS_DIR, DEFAULT_MODEL["id"])
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    if debug:
        log_error_to_service("IABS1", message=get_error_explanation("IABS1"), extra={"model_dir": model_dir})
    missing_files = check_model_files(model_dir)
    if missing_files:
        log_error_to_service("EABS1", message=get_error_explanation("EABS1"), extra={"missing": missing_files})
        print(f"Missing model files: {missing_files}")
        for fname in missing_files:
            download_model_file(model_dir, fname)
        # Re-check after download attempt
        missing_files = check_model_files(model_dir)
        if missing_files:
            log_error_to_service("EABS1", message=get_error_explanation("EABS1"), extra={"missing": missing_files})
            print(f"Still missing model files after download: {missing_files}")
        else:
            log_error_to_service("IABS2", message=get_error_explanation("IABS2"), extra={"model_dir": model_dir})
            print(f"All required model files present for {DEFAULT_MODEL['id']}")
    else:
        print(f"All required model files present for {DEFAULT_MODEL['id']}")
        log_error_to_service("IABS2", message=get_error_explanation("IABS2"), extra={"model_dir": model_dir})

if __name__ == "__main__":
    debug = "--debug" in sys.argv
    ensure_online_model(debug=debug)
