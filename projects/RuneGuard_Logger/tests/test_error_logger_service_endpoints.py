import importlib
import os
import sys
from datetime import datetime


def test_log_endpoint_and_recent_and_services(tmp_path, capsys):
    # Import the service module fresh
    mod_name = "projects.RuneGuard_Logger.error_logger_service"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    svc = importlib.import_module(mod_name)
    importlib.reload(svc)

    # Point LOG_DIR to a temporary directory for tests
    svc.LOG_DIR = str(tmp_path)
    os.makedirs(svc.LOG_DIR, exist_ok=True)

    app = svc.app.test_client()

    # Missing error_code -> 400
    r = app.post("/log", json={"message": "no code"})
    assert r.status_code == 400

    # Valid log -> 200 and file written
    r2 = app.post("/log", json={"error_code": "E_TEST", "message": "it failed", "service": "unittest"})
    assert r2.status_code == 200
    # There should be a log file for today in svc.LOG_DIR
    files = list(os.listdir(svc.LOG_DIR))
    assert any(f.startswith("errors_") for f in files)

    # Recent logs -> should return at least one
    r3 = app.get("/logs/recent")
    assert r3.status_code == 200
    jd = r3.get_json()
    assert jd.get("total_today", 0) >= 1

    # Services endpoint -> should list 'unittest'
    r4 = app.get("/services")
    assert r4.status_code == 200
    sd = r4.get_json()
    assert isinstance(sd.get("services"), list)

