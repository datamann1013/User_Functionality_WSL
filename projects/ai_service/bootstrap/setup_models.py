import os
from transformers import snapshot_download

MODELS_DIR = os.path.join(os.path.dirname(__file__), '../backend/models')
DEFAULT_MODEL_ID = "mistral-7b-v1"
HUGGINGFACE_REPO_ID = "mistralai/Mistral-7B-v0.1"

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
    ensure_model_downloaded()

