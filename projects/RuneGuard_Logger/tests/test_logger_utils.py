import importlib
import sys
import os
import types
import tempfile


def test_safe_json_dumps_and_explanation(tmp_path, monkeypatch):
    mod = importlib.import_module("projects.RuneGuard_Logger.logger_optimized")
    importlib.reload(mod)

    # Decimal and datetime handling
    from decimal import Decimal
    from datetime import datetime, timedelta

    s = mod.safe_json_dumps({"a": Decimal("1.23"), "t": datetime.now(), "d": timedelta(days=1)})
    assert isinstance(s, str)

    # get_explanation fallback
    assert "Unidentified error" in mod.get_explanation("NOPE")


def test_log_error_remote_fallback(monkeypatch, tmp_path):
    # Use temporary LOG_DIRECTORY to avoid touching repo logs
    monkeypatch.setenv("LOG_DIRECTORY", str(tmp_path))

    mod = importlib.import_module("projects.RuneGuard_Logger.logger_optimized")
    importlib.reload(mod)

    # Create a fake requests module that raises
    fake_requests = types.ModuleType("requests")

    def _post(*a, **k):
        raise Exception("network")

    fake_requests.post = _post
    mod.requests = fake_requests

    # Call remote logging which should fall back to local log file write
    mod.log_error_remote("E999", message="remote fail test", exception=None, extra={"x": 1})

    # Check that a log file was created under tmp_path/logs (logger_optimized uses project-root/logs unless LOG_DIRECTORY)
    log_dir = mod.get_log_directory()
    assert os.path.exists(log_dir)
    files = [f for f in os.listdir(log_dir) if f.startswith("errorlog_")]
    assert len(files) >= 1
