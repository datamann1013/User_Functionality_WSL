import os
import csv
import glob as _glob
import threading
import time
import socket
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import optimized logger
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from logger import log_error

app = Flask(__name__)


def _register_with_core():
    core_url = os.environ.get("RUNECORE_CORE_URL")
    if not core_url:
        return
    payload = {
        "name": "RuneGuardLogger",
        "version": "1.0.0",
        "rest_url": "http://runeguard:5001",
        "dependencies": [],
        "container_name": socket.gethostname(),
    }
    for attempt in range(5):
        try:
            r = requests.post(f"{core_url}/api/v1/services/register", json=payload, timeout=5)
            if r.ok:
                print("[RuneGuard] Registered with Core")
                return
        except Exception as e:
            print(f"[RuneGuard] Registration attempt {attempt + 1} failed: {e}")
        time.sleep(3 * (attempt + 1))
    print("[RuneGuard] Could not register with Core after 5 attempts")


threading.Thread(target=_register_with_core, daemon=True).start()


# ---------------------------------------------------------------------------
# Error stats — background push to CoreMemory + local /stats endpoint
# ---------------------------------------------------------------------------
_LOG_DIRECTORY = os.environ.get("LOG_DIRECTORY", "/app/logs")
_CORE_PROXY_URL = os.environ.get(
    "CORE_PROXY_URL", "http://runecore_core:11441/api/proxy/CoreMemoryAPI"
)
_STATS_PUSH_INTERVAL = int(os.environ.get("STATS_PUSH_INTERVAL", "300"))  # 5 minutes


def _compute_error_stats():
    """Read all CSV log files and return aggregate counts."""
    total = 0
    errors_last_hour = 0
    by_type = {"E": 0, "W": 0, "I": 0}
    cutoff = datetime.utcnow() - timedelta(hours=1)

    if not os.path.isdir(_LOG_DIRECTORY):
        return total, errors_last_hour, by_type

    for path in _glob.glob(os.path.join(_LOG_DIRECTORY, "errorlog_*.csv")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) < 2:
                        continue
                    total += 1
                    code = row[1] if len(row) > 1 else ""
                    prefix = code[0].upper() if code else ""
                    if prefix in by_type:
                        by_type[prefix] += 1
                    try:
                        ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                        if ts >= cutoff:
                            errors_last_hour += 1
                    except ValueError:
                        pass
        except Exception:
            pass

    return total, errors_last_hour, by_type


def _push_stats_loop():
    """Push error stats to CoreMemory every STATS_PUSH_INTERVAL seconds."""
    time.sleep(10)  # initial delay — let Core registration settle
    while True:
        try:
            total, last_hour, by_type = _compute_error_stats()
            payload = {
                "measurement": "error_stats",
                "tags": {"service": "RuneGuardLogger"},
                "fields": {
                    "total_errors": float(total),
                    "errors_last_hour": float(last_hour),
                    "error_count": float(by_type.get("E", 0)),
                    "warning_count": float(by_type.get("W", 0)),
                    "info_count": float(by_type.get("I", 0)),
                },
            }
            requests.post(
                f"{_CORE_PROXY_URL}/telemetry",
                json=payload,
                timeout=5,
            )
        except Exception as e:
            print(f"[RuneGuard] Stats push failed: {e}")
        time.sleep(_STATS_PUSH_INTERVAL)


threading.Thread(target=_push_stats_loop, daemon=True).start()

app.config["WTF_CSRF_ENABLED"] = False

# Pre-compile response templates for faster responses
SUCCESS_RESPONSE = {"status": "logged"}
HEALTH_RESPONSE = {"status": "ok", "service": "error_logger"}
ERROR_RESPONSE = {"error": "Missing error_code"}


@app.route("/log", methods=["POST"])
def log_endpoint():
    """Optimized log endpoint with fast validation"""
    data = request.get_json(force=True)

    # Fast validation
    error_code = data.get("error_code")
    if not error_code:
        return jsonify(ERROR_RESPONSE), 400

    # Log with optimized logger
    log_error(
        error_code,
        message=data.get("message"),
        exception=data.get("exception"),
        extra=data.get("extra"),
    )

    # Fast response
    response = SUCCESS_RESPONSE.copy()
    response["code"] = error_code
    return jsonify(response), 200


@app.route("/health", methods=["GET"])
def health_check():
    """Fast health check"""
    return jsonify(HEALTH_RESPONSE), 200


@app.route("/stats", methods=["GET"])
def stats():
    """Return aggregate error counts from local log files."""
    total, last_hour, by_type = _compute_error_stats()
    return jsonify({
        "total_errors": total,
        "errors_last_hour": last_hour,
        "error_count": by_type.get("E", 0),
        "warning_count": by_type.get("W", 0),
        "info_count": by_type.get("I", 0),
    }), 200


if __name__ == "__main__":
    # Optimized startup with minimal argument parsing
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Get configuration from environment with defaults
    host = os.environ.get("ERRORLOGGER_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("ERRORLOGGER_PORT", os.environ.get("PORT", "5001")))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true" or args.debug

    app.run(host=host, port=port, debug=debug, threaded=True)
