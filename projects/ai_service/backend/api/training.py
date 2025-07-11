from flask import Blueprint, request, jsonify
import threading
import time

training_bp = Blueprint('training', __name__)

# In-memory job store for demonstration
TRAINING_JOBS = []

# Mock training function (replace with real logic later)
def run_training_job(job_id, model_id, params):
    time.sleep(2)  # Simulate training
    for job in TRAINING_JOBS:
        if job['id'] == job_id:
            job['status'] = 'completed'
            job['result'] = f"Model {model_id} trained with params {params}"
            break

@training_bp.route('/training/jobs', methods=['POST'])
def start_training():
    data = request.get_json()
    model_id = data.get('model_id')
    params = data.get('params', {})
    job_id = f"job-{len(TRAINING_JOBS)+1}"
    job = {
        'id': job_id,
        'model_id': model_id,
        'params': params,
        'status': 'running',
        'result': None
    }
    TRAINING_JOBS.append(job)
    threading.Thread(target=run_training_job, args=(job_id, model_id, params), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'started'}), 202

@training_bp.route('/training/jobs', methods=['GET'])
def list_training_jobs():
    return jsonify(TRAINING_JOBS)

