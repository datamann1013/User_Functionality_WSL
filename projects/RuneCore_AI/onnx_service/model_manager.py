"""
ONNX model registry — loading, downloading, and listing models.

Models are stored as local directories under ONNX_MODEL_DIR.
Each subdirectory containing a model.onnx (or variant) is a registered model.
"""
import os
import logging
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger("onnx_service.models")

# Global model registry: name → metadata dict
_registry: dict = {}
_registry_lock = threading.Lock()

# Loaded sessions: name → (ORTModelForCausalLM, tokenizer)
_sessions: dict = {}
_sessions_lock = threading.Lock()


def get_model_dir() -> str:
    return os.environ.get("ONNX_MODEL_DIR", "/models")


def _find_model_file(local_path: str) -> Optional[str]:
    """Find the best ONNX model file in a directory.

    Prefers GPU-optimized variants, then falls back to any *.onnx file.
    Returns the path to the model file, or None if not found.
    """
    candidates = [
        os.path.join(local_path, "gpu", "model.onnx"),
        os.path.join(local_path, "gpu-int4-rtn-block-32", "model.onnx"),
        os.path.join(local_path, "cpu_and_mobile", "model.onnx"),
        os.path.join(local_path, "model.onnx"),
        os.path.join(local_path, "model_quantized.onnx"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    # Walk for any onnx file as last resort
    for root, _, files in os.walk(local_path):
        for f in files:
            if f.endswith(".onnx"):
                return os.path.join(root, f)
    return None


def _dir_size_bytes(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def scan_local_models():
    """Scan ONNX_MODEL_DIR for model directories and populate the registry."""
    model_dir = get_model_dir()
    if not os.path.isdir(model_dir):
        logger.info("Model dir %s does not exist yet — nothing to scan", model_dir)
        return

    with _registry_lock:
        for name in os.listdir(model_dir):
            subdir = os.path.join(model_dir, name)
            if not os.path.isdir(subdir):
                continue
            if name in _registry:
                continue  # already registered
            model_file = _find_model_file(subdir)
            if model_file:
                size = _dir_size_bytes(subdir)
                _registry[name] = {
                    "name": name,
                    "local_path": subdir,
                    "backend": "onnx",
                    "status": "unloaded",
                    "size": size,
                    "modified_at": datetime.fromtimestamp(
                        os.path.getmtime(subdir)
                    ).isoformat(),
                }
                logger.info("Discovered model: %s (%s MB)", name, size // (1024 * 1024))


def load_model(model_name: str):
    """Load an ONNX model into memory using optimum ORTModelForCausalLM.

    Returns (model, tokenizer) on success. Updates registry status.
    Raises RuntimeError on failure.
    """
    with _registry_lock:
        entry = _registry.get(model_name)
        if not entry:
            raise KeyError(f"Model '{model_name}' not in registry")
        local_path = entry["local_path"]
        entry["status"] = "loading"

    device = os.environ.get("ONNX_DEVICE", "cpu")
    provider = "DmlExecutionProvider" if device == "dml" else "CPUExecutionProvider"

    logger.info("Loading model %s with provider %s from %s", model_name, provider, local_path)
    try:
        from optimum.onnxruntime import ORTModelForCausalLM
        from transformers import AutoTokenizer

        model = ORTModelForCausalLM.from_pretrained(
            local_path,
            provider=provider,
            use_io_binding=(device == "dml"),
        )
        tokenizer = AutoTokenizer.from_pretrained(local_path)

        with _sessions_lock:
            _sessions[model_name] = (model, tokenizer)

        with _registry_lock:
            _registry[model_name]["status"] = "loaded"

        logger.info("Model %s loaded successfully", model_name)
        return model, tokenizer

    except Exception as e:
        with _registry_lock:
            if model_name in _registry:
                _registry[model_name]["status"] = "error"
                _registry[model_name]["error"] = str(e)
        logger.exception("Failed to load model %s: %s", model_name, e)
        raise RuntimeError(f"Failed to load model '{model_name}': {e}") from e


def get_session(model_name: str):
    """Return (model, tokenizer) for the given model, loading it if needed."""
    with _sessions_lock:
        if model_name in _sessions:
            return _sessions[model_name]

    with _registry_lock:
        if model_name not in _registry:
            raise KeyError(f"Model '{model_name}' not registered")

    return load_model(model_name)


def download_model(model_id: str, local_name: str):
    """Download a model from HuggingFace Hub in the background.

    model_id: HuggingFace repo ID (e.g. "microsoft/Phi-3-mini-4k-instruct-onnx")
    local_name: local directory name under ONNX_MODEL_DIR (e.g. "phi3-mini-onnx")
    """
    model_dir = get_model_dir()
    local_path = os.path.join(model_dir, local_name)
    os.makedirs(local_path, exist_ok=True)

    with _registry_lock:
        _registry[local_name] = {
            "name": local_name,
            "model_id": model_id,
            "local_path": local_path,
            "backend": "onnx",
            "status": "downloading",
            "size": 0,
            "modified_at": datetime.now().isoformat(),
        }

    def _do_download():
        try:
            logger.info("Downloading %s → %s", model_id, local_path)
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=model_id,
                local_dir=local_path,
                ignore_patterns=["*.md", "*.txt", "*.py", "*.ipynb"],
            )
            logger.info("Download complete: %s", local_name)

            # Auto-load after download
            load_model(local_name)

        except Exception as e:
            logger.exception("Download failed for %s: %s", local_name, e)
            with _registry_lock:
                if local_name in _registry:
                    _registry[local_name]["status"] = "error"
                    _registry[local_name]["error"] = str(e)

    th = threading.Thread(target=_do_download, daemon=True)
    th.start()


def list_models() -> list:
    """Return a copy of all registry entries as a list."""
    with _registry_lock:
        return [dict(v) for v in _registry.values()]
