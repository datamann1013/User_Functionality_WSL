import importlib
import os
import types


def test_log_write_failure(monkeypatch, tmp_path):
    # Point LOG_DIR to a read-only location to simulate write failure
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    mod = importlib.import_module("projects.RuneGuard_Logger.error_logger_service")
    importlib.reload(mod)

    # Make the directory read-only
    os.chmod(tmp_path, 0o400)

    client = mod.app.test_client()
    payload = {"error_code": "E1", "message": "x", "service": "s"}
    # Even if write fails, service should return 200 (it catches exceptions)
    r = client.post("/log", json=payload)
    assert r.status_code == 200


def test_log_endpoint_malformed_json(monkeypatch):
    mod = importlib.import_module("projects.RuneGuard_Logger.error_logger_service")
    importlib.reload(mod)
    client = mod.app.test_client()

    # Send malformed JSON
    r = client.post("/log", data="{bad}", content_type="application/json")
    # Endpoint should return 500 with internal server error message
    assert r.status_code == 500
