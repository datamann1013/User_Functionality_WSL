#!/usr/bin/env python3
"""
Minimal ErrorLogger Server - MVP Version
Simple, reliable error logging service
"""
import os
import sys
import json
import argparse
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Simple configuration
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def get_log_filename():
    """Generate log filename with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(LOG_DIR, f"errors_{timestamp}.json")


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "ok",
                "service": "errorlogger_mvp",
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/log", methods=["POST"])
def log_error():
    """Log error endpoint"""
    try:
        data = request.get_json(force=True)

        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_code": data.get("error_code", "UNKNOWN"),
            "message": data.get("message", "No message provided"),
            "exception": data.get("exception", ""),
            "extra": data.get("extra", {}),
        }

        # Write to console
        print(
            f"[{log_entry['timestamp']}] {log_entry['error_code']}: {log_entry['message']}"
        )

        # Write to file
        log_file = get_log_filename()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                json.dump(log_entry, f)
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


@app.route("/logs", methods=["GET"])
def get_logs():
    """Get recent logs"""
    try:
        logs = []
        for filename in sorted(os.listdir(LOG_DIR))[-5:]:  # Last 5 files
            if filename.endswith(".json"):
                filepath = os.path.join(LOG_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                logs.append(json.loads(line.strip()))
                except Exception as e:
                    print(f"Error reading {filename}: {e}")

        return (
            jsonify({"logs": logs[-100:], "count": len(logs)}),  # Last 100 entries
            200,
        )

    except Exception as e:
        return jsonify({"error": "Could not retrieve logs", "message": str(e)}), 500


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal ErrorLogger Service")
    parser.add_argument("--port", type=int, default=5001, help="Port to run on")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to"
    )  # nosec B104
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    print(f"Starting ErrorLogger MVP on {args.host}:{args.port}")
    print(f"Logs will be stored in: {LOG_DIR}")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {args.port} is already in use!")
            print(f"💡 Try: sudo lsof -i :{args.port} to see what's using it")
            sys.exit(1)
        else:
            raise
