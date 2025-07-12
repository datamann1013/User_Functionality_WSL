from flask import Blueprint, jsonify, request, abort
import os
import json

mnf = "Model not found"
registry_bp = Blueprint('registry', __name__)

MODELS_PATH = os.path.join(os.path.dirname(__file__), '../registry/models.json')

def load_models():
    if not os.path.exists(MODELS_PATH):
        return []
    with open(MODELS_PATH, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return []

def save_models(models):
    with open(MODELS_PATH, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2)

@registry_bp.route('/registry/models', methods=['GET'])
def list_models():
    return jsonify(load_models())

@registry_bp.route('/registry/models/<model_id>', methods=['GET'])
def get_model(model_id):
    models = load_models()
    for m in models:
        if str(m.get('id')) == str(model_id):
            return jsonify(m)
    abort(404, description=mnf)

@registry_bp.route('/registry/models', methods=['POST'])
def add_model():
    models = load_models()
    data = request.get_json()
    if not data or 'id' not in data:
        abort(400, description='Model id required')
    if any(str(m.get('id')) == str(data['id']) for m in models):
        abort(409, description='Model with this id already exists')
    models.append(data)
    save_models(models)
    return jsonify(data), 201

@registry_bp.route('/registry/models/<model_id>', methods=['PUT'])
def update_model(model_id):
    models = load_models()
    data = request.get_json()
    for i, m in enumerate(models):
        if str(m.get('id')) == str(model_id):
            models[i] = {**m, **data, 'id': model_id}
            save_models(models)
            return jsonify(models[i])
    abort(404, description=mnf)

@registry_bp.route('/registry/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    models = load_models()
    for i, m in enumerate(models):
        if str(m.get('id')) == str(model_id):
            deleted = models.pop(i)
            save_models(models)
            return jsonify(deleted)
    abort(404, description=mnf)

@registry_bp.route('/registry/models/<model_id>/savepoint', methods=['POST'])
def create_savepoint(model_id):
    models = load_models()
    data = request.get_json()
    for m in models:
        if str(m.get('id')) == str(model_id):
            version = data.get('version')
            notes = data.get('notes', '')
            training_diff = data.get('training_diff', {})
            metadata = data.get('metadata', {})
            savepoint = {
                'version': version,
                'created': data.get('created'),
                'savepoint': True,
                'notes': notes,
                'training_diff': training_diff,
                'metadata': metadata,
                'archived': False
            }
            m.setdefault('versions', []).append(savepoint)
            m['current_version'] = version
            save_models(models)
            return jsonify(savepoint)
    abort(404, description=mnf)

@registry_bp.route('/registry/models/<model_id>/savepoints', methods=['GET'])
def list_savepoints(model_id):
    models = load_models()
    for m in models:
        if str(m.get('id')) == str(model_id):
            return jsonify([v for v in m.get('versions', []) if v.get('savepoint') and not v.get('archived')])
    abort(404, description=mnf)

@registry_bp.route('/registry/models/<model_id>/savepoint/<version>', methods=['PUT'])
def edit_savepoint(model_id, version):
    models = load_models()
    data = request.get_json()
    for m in models:
        if str(m.get('id')) == str(model_id):
            for v in m.get('versions', []):
                if v.get('version') == version:
                    v.update(data)
                    save_models(models)
                    return jsonify(v)
    abort(404, description=mnf)

@registry_bp.route('/registry/models/<model_id>/savepoint/<version>/archive', methods=['POST'])
def archive_savepoint(model_id, version):
    models = load_models()
    for m in models:
        if str(m.get('id')) == str(model_id):
            for v in m.get('versions', []):
                if v.get('version') == version:
                    v['archived'] = True
                    save_models(models)
                    return jsonify({'archived': True})
    abort(404, description=mnf)

@registry_bp.route('/registry/models/<model_id>/rollback', methods=['POST'])
def rollback_model(model_id):
    models = load_models()
    data = request.get_json()
    version = data.get('version')
    for m in models:
        if str(m.get('id')) == str(model_id):
            if any(v.get('version') == version for v in m.get('versions', [])):
                m['current_version'] = version
                save_models(models)
                return jsonify({'rolled_back_to': version})
    abort(404, description=mnf)
