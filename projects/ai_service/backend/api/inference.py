from flask import Blueprint, jsonify, request
from ..core.scheduler import RoundRobinScheduler
from ..api.model_registry import load_models
import threading

inference_bp = Blueprint('inference', __name__)

# Global scheduler instance and lock for thread safety
scheduler = None
scheduler_lock = threading.Lock()

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

@inference_bp.route('/inference/run', methods=['POST'])
def run_inference():
    data = request.get_json()
    # Simulate model selection
    sched = get_scheduler()
    model = sched.next()
    if not model:
        return jsonify({'error': 'No available model'}), 503
    # Simulate inference result
    prompt = data.get('prompt', '')
    result = f"[Simulated response from model {model['id']}: '{prompt[:30]}...']"
    # Release model after use
    sched.release(model['id'])
    return jsonify({'model_id': model['id'], 'result': result})
