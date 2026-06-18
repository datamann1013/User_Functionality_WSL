#!/usr/bin/env python3
"""
ErrorLogger - Standalone Service for Multiple Programs
Centralized error logging that can be used by any program in the system
"""
import os
import sys
import json
import time
import threading
import argparse
from datetime import datetime
from flask import Flask, request, jsonify
# optional integration with core
try:
    from shared_utils.core_client import CoreClient
except Exception:
    CoreClient = None

app = Flask(__name__)

# Configuration
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def get_log_filename():
    """Generate log filename with date"""
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_DIR, f"errors_{date_str}.jsonl")


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "ok",
                "service": "errorlogger",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/log", methods=["POST"])
def log_error():
    """Log error endpoint - accepts from any service"""
    try:
        data = request.get_json(force=True)

        # Validate required fields
        if "error_code" not in data:
            return jsonify({"error": "error_code is required"}), 400

        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_code": data.get("error_code"),
            "message": data.get("message", ""),
            "exception": data.get("exception", ""),
            "extra": data.get("extra", {}),
            "service": data.get("service", "unknown"),
        }

        # Console output for monitoring
        service_name = log_entry["service"]
        print(
            f"[{log_entry['timestamp']}] {service_name}: {log_entry['error_code']} - {log_entry['message']}"
        )

        # Write to daily log file
        log_file = get_log_filename()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                json.dump(log_entry, f, separators=(",", ":"))
                f.write("\n")
        except Exception as e:
            print(f"Warning: Could not write to log file: {e}")

        return (
            jsonify(
                {
                    "status": "logged",
                    "code": log_entry["error_code"],
                    "timestamp": log_entry["timestamp"],
                }
            ),
            200,
        )

    except Exception as e:
        print(f"Error in log endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@app.route("/logs/recent", methods=["GET"])
def get_recent_logs():
    """Get recent logs with optional filtering"""
    try:
        # Query parameters
        service = request.args.get("service")
        limit = min(int(request.args.get("limit", 100)), 1000)  # Max 1000

        logs = []
        log_file = get_log_filename()

        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            if not service or entry.get("service") == service:
                                logs.append(entry)
                        except json.JSONDecodeError:
                            continue

        # Return most recent entries
        recent_logs = logs[-limit:]

        return (
            jsonify(
                {
                    "logs": recent_logs,
                    "count": len(recent_logs),
                    "total_today": len(logs),
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Could not retrieve logs", "message": str(e)}), 500


@app.route("/services", methods=["GET"])
def get_services():
    """Get list of services that have logged today"""
    try:
        services = set()
        log_file = get_log_filename()

        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            services.add(entry.get("service", "unknown"))
                        except json.JSONDecodeError:
                            continue

        return (
            jsonify({"services": sorted(list(services)), "count": len(services)}),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Could not retrieve services", "message": str(e)}), 500


SERVICE_NAME = "RuneGuard_Logger"
SERVICE_VERSION = "1.0.0"

# Heartbeat thread state
_heartbeat_thread = None
_heartbeat_running = False


def _service_rest_url():
    """Base reachable URL for this service. In Docker the alias is `runeguard`;
    falls back to the explicit ERRORLOGGER_SERVICE_URL or localhost."""
    return os.environ.get("ERRORLOGGER_SERVICE_URL", "http://runeguard:5001")


def _build_registration_info():
    """ServiceInfo advertised to Core. Logger exposes /health and /log on 5001."""
    base = _service_rest_url().rstrip("/")
    return {
        "name": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "rest_url": base,
        "health_url": f"{base}/health",
        "log_url": f"{base}/log",
        "dependencies": [],
    }


def maybe_register_with_core():
    """If RUNECORE_REGISTER_WITH_CORE is set, attempt to register this service with
    Core using the shared CoreClient and start a best-effort heartbeat loop.

    Best-effort / limb-mode: the Logger is the bottom of the dependency stack, so a
    Core that is down or unreachable MUST never block or crash it. Any failure is
    logged as a warning and execution continues."""
    if not os.environ.get("RUNECORE_REGISTER_WITH_CORE"):
        return
    if CoreClient is None:
        print("CoreClient not available; skipping registration")
        return
    try:
        cc = CoreClient(
            core_url=os.environ.get("RUNECORE_CORE_URL"),
            disable_mtls=os.environ.get("RUNECORE_DISABLE_MTLS") in ("1", "true", "True"),
        )
        info = _build_registration_info()
        res = cc.register_service(info)
        print(f"Registered with core: {res}")
        start_heartbeat_thread()
    except Exception as e:
        # limb mode: warn and keep running, never propagate
        print(f"Failed to register with core: {e}")


def send_heartbeat():
    """Send a single best-effort heartbeat to Core. Never raises."""
    if CoreClient is None:
        return
    core_url = os.environ.get("RUNECORE_CORE_URL")
    if not core_url:
        return
    try:
        import requests

        disable_mtls = os.environ.get("RUNECORE_DISABLE_MTLS") in ("1", "true", "True")
        requests.post(
            f"{core_url.rstrip('/')}/api/v1/services/heartbeat",
            json={
                "name": SERVICE_NAME,
                "status": "healthy",
                "metadata": {"service_type": "error_logger"},
            },
            timeout=5,
            verify=False if disable_mtls else True,
        )
    except Exception as e:
        print(f"Heartbeat to core failed: {e}")


def heartbeat_loop(interval: int = 30):
    """Background heartbeat loop (mirrors CoreMemory service_discovery)."""
    while _heartbeat_running:
        send_heartbeat()
        time.sleep(interval)


def start_heartbeat_thread():
    """Start the best-effort heartbeat thread if not already running."""
    global _heartbeat_thread, _heartbeat_running
    if _heartbeat_thread and _heartbeat_thread.is_alive():
        return
    _heartbeat_running = True
    _heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    _heartbeat_thread.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ErrorLogger - Centralized Error Logging Service"
    )
    parser.add_argument(
        "--port", type=int, default=5001, help="Port to run on (default: 5001)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    print(f"🔍 Starting ErrorLogger Service")
    print(f"   Host: {args.host}:{args.port}")
    print(f"   Logs: {LOG_DIR}")
    print(f"   Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"   Ready to receive logs from any service...")

    # Best-effort Core registration + heartbeat (never blocks/crashes the logger)
    maybe_register_with_core()

    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use!")
            print(f"💡 Another ErrorLogger may already be running")
            print(f"💡 Use: lsof -i :{args.port} to check")
            sys.exit(1)
        else:
            raise
