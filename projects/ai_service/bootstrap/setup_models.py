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
        "EABS3": "Missing Hugging Face access token.",
        "IABS5": "Gated model access detected.",
    }

import json
import requests
from huggingface_hub import HfApi, HfFolder, snapshot_download, login
from transformers import AutoConfig

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

MODEL_HF_ID = "mistralai/Mistral-7B-v0.1"


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


def ensure_model_access(token):
    """Verify we have access to the gated model"""
    api = HfApi()
    try:
        model_info = api.model_info(MODEL_HF_ID, token=token)
        if getattr(model_info, 'gated', False):
            print("✅ Access verified to gated model")
            log_error_to_service("IABS5", message="Gated model access verified")
        return True
    except Exception as e:
        print(f"❌ Access verification failed: {str(e)}")
        return False


def download_model_with_hf(model_dir, debug=False):
    try:
        if debug:
            log_error_to_service("IABS4", message="Using Hugging Face Hub API for download")
            print("[DEBUG] Starting Hugging Face Hub download")

        # Get Hugging Face token
        hf_token = os.environ.get("HF_API_TOKEN")
        if not hf_token:
            hf_token = HfFolder.get_token()

        if not hf_token:
            log_error_to_service("EABS3", message="Missing Hugging Face access token")
            print("\nERROR: Hugging Face access token required")
            print("1. Visit https://huggingface.co/settings/tokens")
            print("2. Create access token (with read permissions)")
            print("3. Accept model terms at: https://huggingface.co/mistralai/Mistral-7B-v0.1")
            print("   (You MUST click 'Agree and access repository')")
            print("4. Set token as environment variable:")
            print("   export HF_API_TOKEN='your_token_here'")
            print("\nAlternatively, run: huggingface-cli login")
            return False

        # Verify model access
        print("🔒 Verifying access to gated model...")
        if not ensure_model_access(hf_token):
            print("\nACCESS DENIED: You haven't accepted the model terms")
            print("Visit https://huggingface.co/mistralai/Mistral-7B-v0.1")
            print("and click 'Agree and access repository'")
            return False

        # Download model
        snapshot_download(
            repo_id=MODEL_HF_ID,
            revision="main",
            cache_dir=model_dir,
            token=hf_token,
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
        if "Access to model" in str(e) and "is restricted" in str(e):
            print("\nACCESS ISSUE: Please verify:")
            print("1. You've accepted terms at: https://huggingface.co/mistralai/Mistral-7B-v0.1")
            print("2. Your access token is valid")
            print("3. You're using the same account that accepted the terms")
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
            print("❌ Download failed. Please fix the access issues above")
    else:
        print(f"✅ All required files present for {DEFAULT_MODEL['id']}")
        log_error_to_service("IABS2", message=get_error_explanation("IABS2"))


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    ensure_online_model(debug=debug)