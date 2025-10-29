import importlib
import os
import sys
import io
import time


def test_log_write_failure_and_json_decode(tmp_path, monkeypatch):
    modname = "projects.RuneGuard_Logger.error_logger_service"
    if modname in sys.modules:
        del sys.modules[modname]
    svc = importlib.import_module(modname)
    importlib.reload(svc)

    # Point LOG_DIR to tmp
    svc.LOG_DIR = str(tmp_path)
    os.makedirs(svc.LOG_DIR, exist_ok=True)

    app = svc.app.test_client()

    # Simulate inability to write by making get_log_filename return a directory
    def fake_get_log_filename():
        return svc.LOG_DIR  # directory instead of file

    monkeypatch.setattr(svc, "get_log_filename", fake_get_log_filename)

    # Sending a log should not raise; it will attempt to write and catch the exception
    r = app.post("/log", json={"error_code": "E_WRITE", "message": "test"})
    # Since writing failed, the endpoint still responds 200 (it prints warning)
    assert r.status_code == 200

    # Now create a recent log file with one valid and one invalid JSON line
    good = {"error_code": "E1", "service": "s1"}
    bad_line = "{not: valid json}\n"
    # Restore get_log_filename to a real file path for the next part of the test
    def real_get_log_filename():
        return os.path.join(svc.LOG_DIR, "errors_test.jsonl")

    monkeypatch.setattr(svc, "get_log_filename", real_get_log_filename)
    fname = svc.get_log_filename()
    with open(fname, "w", encoding="utf-8") as f:
        import json

        f.write(json.dumps(good) + "\n")
        f.write(bad_line)

    # recent logs should parse and skip the bad JSON line
    r2 = app.get("/logs/recent")
    assert r2.status_code == 200
    jd = r2.get_json()
    assert jd.get("total_today", 0) >= 1


def test_rotation_and_cleanup(tmp_path, monkeypatch):
    # Test logger rotation behavior by forcing small max size and creating files older than retention
    modname = "projects.RuneGuard_Logger.logger"
    if modname in sys.modules:
        del sys.modules[modname]
    logger = importlib.import_module(modname)
    importlib.reload(logger)

    # Point LOG_DIRECTORY to tmp
    monkeypatch.setenv("LOG_DIRECTORY", str(tmp_path))

    # Force small max size so rotation triggers
    monkeypatch.setitem(logger.CONFIG["logging"], "max_log_file_size_mb", 0)
    # Recompute constants
    monkeypatch.setenv("LOG_DIRECTORY", str(tmp_path))
    logger.MAX_FILE_SIZE_BYTES = 1  # 1 byte to force rotation
    logger.RETENTION_SECONDS = 0  # immediate cleanup

    # Create an old file that should be removed by cleanup
    old_file = os.path.join(logger.get_log_directory(), "errorlog_20000101_000000.csv")
    with open(old_file, "w", encoding="utf-8") as f:
        f.write("old\n")
    # Set mtime to far past
    old_time = time.time() - 10 * 24 * 3600
    os.utime(old_file, (old_time, old_time))

    # Initialize and log to trigger cleanup
    logger.LOG_FILE_PATH = None
    logger.init_log_file()
    logger.log_error("TROT", message="rotate test")

    # Run cleanup explicitly
    logger.cleanup_old_logs()

    # Old file should be removed
    assert not os.path.exists(old_file)
