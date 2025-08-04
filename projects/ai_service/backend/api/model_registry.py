from flask import Blueprint, jsonify, request, current_app
import os
import json
import logging
from projects.ErrorLogger.logger import log_error_remote

# Create Blueprint
registry_bp = Blueprint('registry', __name__)

# Constants
MODEL_NOT_FOUND = "Model not found"
MODEL_ID_REQUIRED = "Model id required"
MODEL_EXISTS = "Model with this id already exists"
INVALID_REQUEST = "Invalid request data"


def get_models_path():
    """Get absolute path to models.json with fallback"""
    try:
        # Try to get from app config first
        if 'REGISTRY_PATH' in current_app.config:
            return current_app.config['REGISTRY_PATH']

        # Fallback to default location
        return os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            '../registry/models.json'
        ))
    except Exception as e:
        # Emergency fallback
        return '/tmp/models.json'


def load_models():
    """Load models from JSON file with error handling"""
    try:
        path = get_models_path()
        if not os.path.exists(path):
            return []

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    except Exception as e:
        error_code = "EMR01"
        log_error_remote(
            error_code,
            message=f"Failed to load models: {str(e)}",
            exception=str(e),
            extra={"path": path}
        )
        if current_app.debug:
            current_app.logger.error(f"[{error_code}] Model load error: {e}")
        return []


def save_models(models):
    """Save models to JSON file with error handling"""
    try:
        path = get_models_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(models, f, indent=2)
        return True

    except Exception as e:
        error_code = "EMR02"
        log_error_remote(
            error_code,
            message=f"Failed to save models: {str(e)}",
            exception=str(e),
            extra={"path": path}
        )
        if current_app.debug:
            current_app.logger.error(f"[{error_code}] Model save error: {e}")
        return False


def find_model(models, model_id):
    """Find model by ID with type safety"""
    return next((m for m in models if str(m.get('id')) == str(model_id)), None)


def validate_model_data(data):
    """Validate model data structure"""
    if not data or 'id' not in data:
        return False, MODEL_ID_REQUIRED
    if not isinstance(data.get('name'), str):
        return False, "Model name must be a string"
    return True, ""


# API Endpoints
@registry_bp.route('/registry/models', methods=['GET'])
def list_models():
    """List all registered models"""
    try:
        models = load_models()
        if current_app.debug:
            current_app.logger.debug(f"Listed {len(models)} models")
        return jsonify(models)

    except Exception as e:
        error_code = "EMR03"
        log_error_remote(error_code, message="Failed to list models", exception=str(e))
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Failed to retrieve models',
            'code': error_code
        }), 500


@registry_bp.route('/registry/models/<model_id>', methods=['GET'])
def get_model(model_id):
    """Get details for a specific model"""
    try:
        models = load_models()
        model = find_model(models, model_id)

        if not model:
            return jsonify({'error': MODEL_NOT_FOUND, 'code': 'EMR04'}), 404

        if current_app.debug:
            current_app.logger.debug(f"Retrieved model: {model_id}")
        return jsonify(model)

    except Exception as e:
        error_code = "EMR05"
        log_error_remote(
            error_code,
            message=f"Failed to get model: {model_id}",
            exception=str(e),
            extra={"model_id": model_id}
        )
        return jsonify({
            'error': 'Internal Server Error',
            'message': f'Failed to retrieve model {model_id}',
            'code': error_code
        }), 500


@registry_bp.route('/registry/models', methods=['POST'])
def add_model():
    """Add a new model to the registry"""
    try:
        data = request.get_json()
        valid, message = validate_model_data(data)
        if not valid:
            return jsonify({'error': message, 'code': 'EMR06'}), 400

        models = load_models()
        if find_model(models, data['id']):
            return jsonify({'error': MODEL_EXISTS, 'code': 'EMR07'}), 409

        models.append(data)
        if save_models(models):
            if current_app.debug:
                current_app.logger.debug(f"Added new model: {data['id']}")
            return jsonify(data), 201
        else:
            return jsonify({'error': 'Failed to save model', 'code': 'EMR08'}), 500

    except Exception as e:
        error_code = "EMR09"
        log_error_remote(
            error_code,
            message="Failed to add model",
            exception=str(e),
            extra={"model_data": data}
        )
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Failed to add model',
            'code': error_code
        }), 500


@registry_bp.route('/registry/models/<model_id>', methods=['PUT'])
def update_model(model_id):
    """Update an existing model"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': INVALID_REQUEST, 'code': 'EMR10'}), 400

        models = load_models()
        model_index, model = next(
            ((i, m) for i, m in enumerate(models) if str(m.get('id')) == str(model_id)),
            (None, None)
        )

        if model is None:
            return jsonify({'error': MODEL_NOT_FOUND, 'code': 'EMR11'}), 404

        # Preserve ID and merge data
        updated_model = {**model, **data, 'id': model_id}
        models[model_index] = updated_model

        if save_models(models):
            if current_app.debug:
                current_app.logger.debug(f"Updated model: {model_id}")
            return jsonify(updated_model)
        else:
            return jsonify({'error': 'Failed to save model', 'code': 'EMR12'}), 500

    except Exception as e:
        error_code = "EMR13"
        log_error_remote(
            error_code,
            message=f"Failed to update model: {model_id}",
            exception=str(e),
            extra={"model_id": model_id, "update_data": data}
        )
        return jsonify({
            'error': 'Internal Server Error',
            'message': f'Failed to update model {model_id}',
            'code': error_code
        }), 500


@registry_bp.route('/registry/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    """Delete a model from the registry"""
    try:
        models = load_models()
        model_index, model = next(
            ((i, m) for i, m in enumerate(models) if str(m.get('id')) == str(model_id)),
            (None, None)
        )

        if model is None:
            return jsonify({'error': MODEL_NOT_FOUND, 'code': 'EMR14'}), 404

        deleted = models.pop(model_index)
        if save_models(models):
            if current_app.debug:
                current_app.logger.debug(f"Deleted model: {model_id}")
            return jsonify(deleted)
        else:
            return jsonify({'error': 'Failed to save registry', 'code': 'EMR15'}), 500

    except Exception as e:
        error_code = "EMR16"
        log_error_remote(
            error_code,
            message=f"Failed to delete model: {model_id}",
            exception=str(e),
            extra={"model_id": model_id}
        )
        return jsonify({
            'error': 'Internal Server Error',
            'message': f'Failed to delete model {model_id}',
            'code': error_code
        }), 500

# Savepoint management endpoints would follow the same pattern...
# Implemented with similar error handling and validation