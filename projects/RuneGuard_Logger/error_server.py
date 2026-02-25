import os
import threading
import time
import socket
import requests
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
