import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
try:
    from projects.ErrorLogger.error_codes import ERROR_CODE_DEFINITIONS
except ImportError:
    ERROR_CODE_DEFINITIONS = {
        "IABS1": "Setup model script started.",
        "IABS2": "All required model files present.",
        "EABS1": "Missing required model files.",
        "EABS2": "Failed to download model file.",
        "IABS3": "Model file downloaded successfully.",
        "E00000": "Python exception occurred.",
        "IAXX1": "Health check called.",
        "IABS4": "Using Hugging Face Hub API for download.",
    }

import json
import requests
from huggingface_hub import snapshot_download
from transformers import AutoConfig

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '../backend/registry/models.json')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '../backend/models')
DEFAULT_MODEL = {
    "id": "opt-6.7b",
    "name": "OPT 6.7B",
    "icon": "🤖",
    "state": "online",
    "version": "v1.0"
}
ERRORLOGGER_SERVICE_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://localhost:5001/log')

# Use a publicly accessible model that doesn't require authentication
MODEL_HF_ID = "facebook/opt-6.7b"


def is_wsl():
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False


def log_error_to_service(error_code, message=None, exception=None, extra=None):
    payload = {
        'error_code': error_code,
        'message': message or get_error_explanation(error_code),
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
    """Check for essential model files accounting for sharding"""
    missing = []

    config_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(config_path):
        missing.append("config.json")

    # Check for model files (handle sharded or single file)
    has_model_files = any(
        fname.startswith("pytorch_model") and
        (fname.endswith(".bin") or fname.endswith(".index.json"))
        for fname in os.listdir(model_dir)
    )

    if not has_model_files:
        missing.append("pytorch_model.bin or shards")

    return missing


def download_model_with_hf(model_dir, debug=False):
    try:
        if debug:
            log_error_to_service("IABS4", message="Using Hugging Face Hub API for download")
            print("[DEBUG] Starting Hugging Face Hub download")

        # Download model (no token needed for public models)
        snapshot_download(
            repo_id=MODEL_HF_ID,
            revision="main",
            cache_dir=model_dir,
            local_dir=model_dir,
            local_dir_use_symlinks=False,
            resume_download=True
        )

        if debug:
            print(f"[DEBUG] Model downloaded successfully to {model_dir}")
        log_error_to_service("IABS3", message=get_error_explanation("IABS3"))
        return True
    except Exception as e:
        print(f"Failed to download model: {str(e)}")
        log_error_to_service("EABS2", message=get_error_explanation("EABS2"), exception=str(e))
        return False


def ensure_online_model(debug=False):
    models = [DEFAULT_MODEL]
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)
    print(f"models.json overwritten with only the default model: {models}")

    model_dir = os.path.join(MODELS_DIR, DEFAULT_MODEL["id"])
    os.makedirs(model_dir, exist_ok=True)

    if debug:
        log_error_to_service("IABS1", message=get_error_explanation("IABS1"))
        print(f"[DEBUG] Model directory: {model_dir}")

    missing_files = check_model_files(model_dir)

    if missing_files:
        if debug:
            print(f"[DEBUG] Missing files: {missing_files}")

        log_error_to_service("EABS1", message=get_error_explanation("EABS1"))
        print("Attempting to download model...")

        success = download_model_with_hf(model_dir, debug=debug)

        if success:
            missing_files = check_model_files(model_dir)
            if missing_files:
                print(f"⚠️ Still missing files: {missing_files}")
                log_error_to_service("EABS1", message=get_error_explanation("EABS1"))
            else:
                print(f"✅ All required files present for {DEFAULT_MODEL['id']}")
                log_error_to_service("IABS2", message=get_error_explanation("IABS2"))
        else:
            print("❌ Download failed. Please check network connection")
    else:
        print(f"✅ All required files present for {DEFAULT_MODEL['id']}")
        log_error_to_service("IABS2", message=get_error_explanation("IABS2"))


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    ensure_online_model(debug=debug)