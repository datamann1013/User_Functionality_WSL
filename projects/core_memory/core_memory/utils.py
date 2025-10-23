import os
import requests

ERRORLOGGER_URL = os.environ.get("ERRORLOGGER_SERVICE_URL", "http://127.0.0.1:5001/log")


def log_error_remote(code: str, message: str, extra: dict = None):
    payload = {"error_code": code, "message": message, "extra": extra or {}}
    try:
        requests.post(ERRORLOGGER_URL, json=payload, timeout=1)
    except Exception:
        # Avoid raising in production paths; best-effort logging
        pass
