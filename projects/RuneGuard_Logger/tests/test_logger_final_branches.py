import importlib
import os
import sys
import time
import traceback


def test_exception_hook_calls_remote_and_handles(monkeypatch, tmp_path):
    modname = "projects.RuneGuard_Logger.logger"
    if modname in sys.modules:
        del sys.modules[modname]
    logger = importlib.import_module(modname)
    importlib.reload(logger)

    # Replace log_error_remote to capture calls instead of network
    called = {}

    def fake_remote(code, message=None, exception=None, extra=None):
        called['code'] = code

    monkeypatch.setattr(logger, "log_error_remote", fake_remote)

    try:
        raise ValueError("boom")
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        # Call the hook directly
        logger._exception_hook(exc_type, exc_value, exc_tb)

    assert called.get('code') == "E00000"


def test_get_log_rotation_status_will_rotate(monkeypatch, tmp_path):
    modname = "projects.RuneGuard_Logger.logger"
    if modname in sys.modules:
        del sys.modules[modname]
    logger = importlib.import_module(modname)
    importlib.reload(logger)

    # Point LOG_DIRECTORY to tmp
    monkeypatch.setenv("LOG_DIRECTORY", str(tmp_path))
    ld = logger.get_log_directory()
    os.makedirs(ld, exist_ok=True)

    # Create a log file and make it large
    logger.LOG_FILE_PATH = os.path.join(ld, "errorlog_big.csv")
    with open(logger.LOG_FILE_PATH, "w", encoding="utf-8") as f:
        f.write("x" * 1024 * 1024)

    # Force MAX_FILE_SIZE_BYTES small so will_rotate_soon True
    logger.MAX_FILE_SIZE_BYTES = 1
    status = logger.get_log_rotation_status()
    assert status.get("will_rotate_soon") is True
