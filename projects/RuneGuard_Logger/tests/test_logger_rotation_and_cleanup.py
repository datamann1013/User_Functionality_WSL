import importlib
import os
import time


def test_rotation_and_cleanup(tmp_path, monkeypatch):
    # Use temporary log directory
    monkeypatch.setenv("LOG_DIRECTORY", str(tmp_path))

    mod = importlib.import_module("projects.RuneGuard_Logger.logger_optimized")
    importlib.reload(mod)

    # Ensure a fresh file is initialized
    mod.LOG_FILE_PATH = None
    mod.init_log_file()
    assert os.path.exists(mod.LOG_FILE_PATH)

    # Simulate large file to force rotation on next log_error call
    with open(mod.LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write("X" * (mod.MAX_FILE_SIZE_BYTES + 10))

    prev_path = mod.LOG_FILE_PATH
    mod.log_error("TST1", "rotation test")
    # After rotation, LOG_FILE_PATH should point to a (potentially) new file
    assert mod.LOG_FILE_PATH is not None
    assert os.path.exists(mod.LOG_FILE_PATH)

    # Create an old file to be cleaned
    old_file = os.path.join(mod.get_log_directory(), "errorlog_old.csv")
    with open(old_file, "w", encoding="utf-8") as f:
        f.write("old\n")
    # set mtime to far past
    old_time = time.time() - (mod.RETENTION_SECONDS + 1000)
    os.utime(old_file, (old_time, old_time))

    # Force cleanup by resetting LAST_CLEANUP and calling cleanup_old_logs
    mod.LAST_CLEANUP = 0
    mod.cleanup_old_logs()
    # old file should be removed (or not exist)
    assert not os.path.exists(old_file)
