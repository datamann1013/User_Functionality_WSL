import sys
import os
# Insert the absolute path to the 'projects' directory if not already present
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from app import app
try:
    from ErrorLogger.decorators import log_exceptions
except ImportError:
    # Mock log_exceptions if ErrorLogger is not importable
    def log_exceptions(code):
        def decorator(f):
            return f
        return decorator
from flask import Blueprint

# Add a test route to trigger unhandled exception
test_bp = Blueprint('test_bp', __name__)

@test_bp.route('/raise-unhandled')
def raise_unhandled():
    raise RuntimeError('Unhandled!')

# Add a test route to trigger handled exception with decorator
@test_bp.route('/raise-handled')
@log_exceptions('EAF#01')
def raise_handled():
    raise ValueError('Handled!')

app.register_blueprint(test_bp)

def test_unhandled_exception(client):
    resp = client.get('/raise-unhandled')
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['code'] == '00000'
    assert 'Unhandled!' in data['message']
    assert data['error'] == 'Internal Server Error'

def test_handled_exception(client):
    resp = client.get('/raise-handled')
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['code'] == 'EAF#01'
    assert 'Handled!' in data['message']
    assert data['error'] == 'Application Error'

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client
