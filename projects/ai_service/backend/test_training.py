import pytest
from flask import Flask
from api.training import training_bp, TRAINING_JOBS

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(training_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_start_training_job(client):
    TRAINING_JOBS.clear()
    resp = client.post('/training/jobs', json={"model_id": "mistral-7b-v1", "params": {"epochs": 2}})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["job_id"].startswith("job-")
    assert data["status"] == "started"
    # The job should be in the list and status should be 'running' or 'completed' after a short wait
    import time
    time.sleep(2.5)
    jobs = client.get('/training/jobs').get_json()
    assert any(j["model_id"] == "mistral-7b-v1" for j in jobs)
    assert any(j["status"] in ("running", "completed") for j in jobs)

def test_list_training_jobs(client):
    TRAINING_JOBS.clear()
    # Add a job
    client.post('/training/jobs', json={"model_id": "phi-2", "params": {}})
    jobs = client.get('/training/jobs').get_json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    assert jobs[0]["model_id"] == "phi-2"

