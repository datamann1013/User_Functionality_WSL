import os
import torch
from flask import Blueprint, request, jsonify, current_app
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from projects.ErrorLogger.logger import log_error_remote

inference_bp = Blueprint('inference', __name__)

# Global model cache
MODEL_CACHE = {}


def get_model_path(model_id):
    """Get absolute path to model directory"""
    return os.path.join(current_app.config['MODELS_DIR'], model_id)


def load_model(model_id):
    """Load model with error handling and caching"""
    # Check cache first
    if model_id in MODEL_CACHE:
        return MODEL_CACHE[model_id]

    model_path = get_model_path(model_id)

    # Validate model path
    if not os.path.exists(model_path):
        error_msg = f"Model directory not found: {model_path}"
        log_error_remote(
            "EABB2",
            message=error_msg,
            extra={"model_id": model_id, "model_path": model_path}
        )
        raise FileNotFoundError(error_msg)

    try:
        if current_app.debug:
            current_app.logger.debug(f"Loading model: {model_id} from {model_path}")

        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        )

        # Create pipeline
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device=0 if torch.cuda.is_available() else -1
        )

        # Cache and return
        MODEL_CACHE[model_id] = pipe
        return pipe

    except Exception as e:
        error_code = "EABB3"
        log_error_remote(
            error_code,
            message="Model loading failed",
            exception=str(e),
            extra={"model_id": model_id, "model_path": model_path}
        )
        raise RuntimeError(f"Failed to load model {model_id}: {str(e)}")


@inference_bp.route('/inference/run', methods=['POST'])
def run_inference():
    """Run inference on the specified model"""
    try:
        # Parse request
        data = request.get_json()
        model_id = data.get('model_id', 'opt-6.7b')
        prompt = data.get('prompt', '')
        max_length = data.get('max_length', 100)

        # Log request
        if current_app.debug:
            current_app.logger.debug(f"Inference request: {model_id} | {prompt[:50]}...")
        log_error_remote("IABB1", message="Inference request received")

        # Load model
        generator = load_model(model_id)

        # Generate response
        output = generator(
            prompt,
            max_length=max_length,
            num_return_sequences=1,
            pad_token_id=generator.tokenizer.eos_token_id
        )

        # Extract and return response
        response = output[0]['generated_text']
        log_error_remote("IABB2", message="Inference response sent")
        return jsonify({"response": response})

    except Exception as e:
        error_code = "EABB1"
        log_error_remote(
            error_code,
            message="Inference failed",
            exception=str(e),
            extra={
                "model_id": data.get('model_id'),
                "prompt": data.get('prompt')
            }
        )
        return jsonify({
            'error': 'Inference failed',
            'message': str(e),
            'code': error_code
        }), 500


@inference_bp.route('/inference/models', methods=['GET'])
def list_loaded_models():
    """List currently loaded models in memory"""
    return jsonify({
        "loaded_models": list(MODEL_CACHE.keys())
    })