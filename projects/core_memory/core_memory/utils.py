import os
import requests
import traceback

ERRORLOGGER_URL = os.environ.get("ERRORLOGGER_SERVICE_URL", "http://127.0.0.1:5001/log")
SERVICE_NAME = os.environ.get("CORE_MEMORY_SERVICE_NAME", "core_memory")


def log_error_remote(code: str, message: str, extra: dict = None, severity: str = "error") -> bool:
    payload = {
        "error_code": code,
        "message": message,
        "service": SERVICE_NAME,
        "severity": severity,
        "extra": extra or {},
    }
    try:
        resp = requests.post(ERRORLOGGER_URL, json=payload, timeout=1)
        return resp.status_code == 200
    except Exception:
        # Avoid raising in production paths; best-effort logging
        return False


def log_exception(code: str, exc: Exception, extra: dict = None) -> bool:
    tb = traceback.format_exc()
    return log_error_remote(code, f"{str(exc)}\n{tb}", extra=extra, severity="critical")
