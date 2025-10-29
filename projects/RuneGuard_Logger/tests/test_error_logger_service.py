import os
import importlib
import json
import tempfile


def test_log_and_recent_and_services(tmp_path, monkeypatch):
    # Use a temporary log directory
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    # Import the service module and reload to pick up tmp path
    mod = importlib.import_module("projects.RuneGuard_Logger.error_logger_service")
    importlib.reload(mod)

    client = mod.app.test_client()

    # Missing error_code -> 400
    r = client.post("/log", json={"message": "oops"})
    assert r.status_code == 400

    # Proper log -> 200
    payload = {"error_code": "E123", "message": "test", "service": "unit"}
    r2 = client.post("/log", json=payload)
    assert r2.status_code == 200
    d = r2.get_json()
    assert d["status"] == "logged"

    # recent logs should include our entry
    r3 = client.get("/logs/recent")
    assert r3.status_code == 200
    recent = r3.get_json()
    assert recent["count"] >= 1

    # services listing
    r4 = client.get("/services")
    assert r4.status_code == 200
    services = r4.get_json()
    assert "unit" in services.get("services", [])

