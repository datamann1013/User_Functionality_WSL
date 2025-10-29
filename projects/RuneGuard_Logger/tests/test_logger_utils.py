import importlib
import os
import sys
import types


def test_safe_json_and_log_write_and_remote_fallback(tmp_path, monkeypatch):
    mod_name = "projects.RuneGuard_Logger.logger"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    logger = importlib.import_module(mod_name)
    importlib.reload(logger)

    # Redirect log directory to tmp
    monkeypatch.setenv("LOG_DIRECTORY", str(tmp_path))

    # safe_json_dumps handles Decimal and datetime
    import decimal
    from datetime import datetime, timedelta

    s = logger.safe_json_dumps({"d": decimal.Decimal("1.23"), "t": datetime.utcnow(), "dt": timedelta(seconds=5)})
    assert isinstance(s, str)

    # init_log_file creates a file
    logger.LOG_FILE_PATH = None
    logger.init_log_file()
    assert os.path.exists(logger.LOG_FILE_PATH)

    # log_error writes to file
    logger.log_error("TST1", message="ok", exception=None, extra={"a":1})
    assert os.path.getsize(logger.LOG_FILE_PATH) > 0

    # Simulate remote failure by making requests.post raise
    class BadResp:
        def post(self, *a, **k):
            class R:
                status_code = 500

                def json(self):
                    return {}

            return R()

    logger.requests = BadResp()
    # Should fallback to local logging and not raise
    logger.log_error_remote("E100", message="remote fail test")

    # generate_error_code
    code = logger.generate_error_code("L", "O", "C", None, 3)
    assert isinstance(code, str) and code.startswith("LOC")

    # rotation status returns a dict
    status = logger.get_log_rotation_status()
    assert "current_log_file" in status
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
