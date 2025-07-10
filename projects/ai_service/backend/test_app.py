import pytest
from app import app

def test_health_check():
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {'status': 'ok'}
