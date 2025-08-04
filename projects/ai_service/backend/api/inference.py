from flask import Blueprint, jsonify, request
from ..core.scheduler import RoundRobinScheduler
from ..api.model_registry import load_models
from flask import current_app
import threading
import os
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import requests

inference_bp = Blueprint('inference', __name__)

# Global scheduler instance and lock for thread safety
scheduler = None
scheduler_lock = threading.Lock()

ERRORLOGGER_SERVICE_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://localhost:5001/log')

@inference_bp.route('/generate', methods=['POST'])
def generate():
    model_id = request.json.get('model_id')
    model_path = os.path.join(current_app.config['MODELS_DIR'], model_id)

try:
    from projects.ErrorLogger.error_codes import ERROR_CODE_DEFINITIONS
except ImportError:
    ERROR_CODE_DEFINITIONS = {}

def get_error_explanation(error_code):
    return ERROR_CODE_DEFINITIONS.get(error_code, "No explanation provided")

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

def get_scheduler():
    global scheduler
    with scheduler_lock:
        if scheduler is None:
            models = load_models()
            # Initialize with id, load, last_used for each model
            items = [{
                'id': m['id'],
                'load': 0,
                'last_used': 0
            } for m in models if m.get('state') == 'online']
            scheduler = RoundRobinScheduler(items)
        return scheduler

@inference_bp.route('/inference/next_model', methods=['GET'])
def next_model():
    sched = get_scheduler()
    model = sched.next()
    if model:
        return jsonify({'model_id': model['id'], 'load': model['load'], 'last_used': model['last_used']})
    return jsonify({'error': 'No available model'}), 503

@inference_bp.route('/inference/release_model', methods=['POST'])
def release_model():
    data = request.get_json()
    model_id = data.get('model_id')
    sched = get_scheduler()
    sched.release(model_id)
    return jsonify({'released': model_id})

# Cache for loaded models
MODEL_CACHE = {}

def get_model_and_tokenizer(model_id):
    if model_id in MODEL_CACHE:
        return MODEL_CACHE[model_id]
    model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../models', model_id))
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForCausalLM.from_pretrained(model_dir)
    MODEL_CACHE[model_id] = (model, tokenizer)
    return model, tokenizer

@inference_bp.route('/inference/run', methods=['POST'])
def run_inference():
    try:
        data = request.get_json()
        sched = get_scheduler()
        model_info = sched.next()
        if not model_info:
            log_error_to_service("EABB2", message=get_error_explanation("EABB2"), extra=data)
            return jsonify({'error': get_error_explanation("EABB2"), 'code': "EABB2"}), 503
        model_id = model_info['id']
        prompt = data.get('prompt', '')
        if os.environ.get('DEBUG_MODE', '0') == '1':
            log_error_to_service("IABB1", message=get_error_explanation("IABB1"), extra={"model_id": model_id, "prompt": prompt})
        try:
            model, tokenizer = get_model_and_tokenizer(model_id)
            input_ids = tokenizer(prompt, return_tensors="pt").input_ids
            with torch.no_grad():
                output = model.generate(input_ids, max_new_tokens=64, do_sample=True)
            result = tokenizer.decode(output[0], skip_special_tokens=True)
            if os.environ.get('DEBUG_MODE', '0') == '1':
                log_error_to_service("IABB2", message=get_error_explanation("IABB2"), extra={"model_id": model_id, "result": result})
        except Exception as e:
            sched.release(model_id)
            log_error_to_service("EABB1", message=get_error_explanation("EABB1"), exception=str(e), extra={"model_id": model_id, "prompt": prompt})
            return jsonify({'error': get_error_explanation("EABB1"), 'code': "EABB1"}), 500
        sched.release(model_id)
        return jsonify({'model_id': model_id, 'result': result})
    except Exception as e:
        # Catch any unexpected errors in the endpoint itself
        log_error_to_service("E00000", message=get_error_explanation("E00000"), exception=str(e))
        return jsonify({'error': get_error_explanation("E00000"), 'code': "E00000"}), 500
