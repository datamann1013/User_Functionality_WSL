import pytest
from unittest.mock import patch
from app import app

def test_health_check():
    # Patch the error handler registration to a dummy during this test
    with patch('app.flask_error_handler', lambda e: ("mocked error", 500)):
        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            assert response.is_json
            assert response.get_json() == {'status': 'ok'}
