import os
import tempfile
import json
import pytest
from app import app

MODELS_PATH = os.path.join(os.path.dirname(__file__), '../registry/models.json')

@pytest.fixture(autouse=True)
def temp_models_file(monkeypatch):
    # Use a temp file for models.json during tests
    with tempfile.NamedTemporaryFile('w+', delete=False) as tf:
        tf.write('[]')
        tf.flush()
        monkeypatch.setattr(
            'api.model_registry.MODELS_PATH', tf.name
        )
        yield
    os.remove(tf.name)

def test_list_models():
    with app.test_client() as client:
        resp = client.get('/registry/models')
        assert resp.status_code == 200
        assert resp.get_json() == []

def test_add_and_get_model():
    with app.test_client() as client:
        model = {'id': 'm1', 'name': 'Test Model'}
        resp = client.post('/registry/models', json=model)
        assert resp.status_code == 201
        assert resp.get_json()['id'] == 'm1'
        # Get the model
        resp = client.get('/registry/models/m1')
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'Test Model'

def test_add_duplicate_model():
    with app.test_client() as client:
        model = {'id': 'm2', 'name': 'Dup Model'}
        client.post('/registry/models', json=model)
        resp = client.post('/registry/models', json=model)
        assert resp.status_code == 409

def test_update_model():
    with app.test_client() as client:
        model = {'id': 'm3', 'name': 'Old Name'}
        client.post('/registry/models', json=model)
        update = {'name': 'New Name'}
        resp = client.put('/registry/models/m3', json=update)
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'New Name'

def test_update_nonexistent_model():
    with app.test_client() as client:
        resp = client.put('/registry/models/doesnotexist', json={'name': 'X'})
        assert resp.status_code == 404

def test_delete_model():
    with app.test_client() as client:
        model = {'id': 'm4', 'name': 'ToDelete'}
        client.post('/registry/models', json=model)
        resp = client.delete('/registry/models/m4')
        assert resp.status_code == 200
        assert resp.get_json()['id'] == 'm4'
        # Should be gone now
        resp = client.get('/registry/models/m4')
        assert resp.status_code == 404

def test_delete_nonexistent_model():
    with app.test_client() as client:
        resp = client.delete('/registry/models/doesnotexist')
        assert resp.status_code == 404

