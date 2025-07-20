import sys
import os
import requests
import subprocess
import argparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from flask import Flask, jsonify, request
from projects.ai_service.backend.api.model_registry import registry_bp
from projects.ai_service.backend.api.inference import inference_bp

ERRORLOGGER_SERVICE_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', 'http://localhost:5001/log')

def log_error_to_service(error_code, message=None, exception=None, extra=None):
    payload = {
        'error_code': error_code,
        'message': message,
        'exception': exception,
        'extra': extra
    }
    try:
        requests.post(ERRORLOGGER_SERVICE_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ErrorLogger Service Unreachable] {e}")

# Parse debug flag from command line
parser = argparse.ArgumentParser()
parser.add_argument('--debug', '-DEBUG', action='store_true', help='Enable debug output')
args, unknown = parser.parse_known_args()
DEBUG_MODE = args.debug
if DEBUG_MODE:
    print("[DEBUG] Debug mode enabled.")

# Ensure at least one model is downloaded and set up before starting the app
try:
    if DEBUG_MODE:
        print("[DEBUG] Running initial_ai_downloader.py to ensure model setup...")
    subprocess.run([
        sys.executable,
        os.path.join(os.path.dirname(__file__), '../bootstrap/initial_ai_downloader.py')
    ], check=True)
    if DEBUG_MODE:
        print("[DEBUG] Model setup script completed.")
except subprocess.CalledProcessError as e:
    print("\n[Startup Error] Model setup failed. Please resolve the above issue and restart the backend.")
    sys.exit(1)

app = Flask(__name__)
app.register_blueprint(registry_bp)
app.register_blueprint(inference_bp, url_prefix="/api")

@app.errorhandler(Exception)
def handle_exception(e):
    if DEBUG_MODE:
        print(f"[DEBUG] Unhandled exception: {repr(e)} at {request.method} {request.path}")
    log_error_to_service(0, exception=f"{request.method} {request.path} | {repr(e)}")
    response = {
        'error': 'Internal Server Error',
        'message': str(e),
        'code': '00000'
    }
    return jsonify(response), 500

@app.route('/health', methods=['GET'])
def health_check():
    if DEBUG_MODE:
        print("[DEBUG] /health endpoint called.")
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    if DEBUG_MODE:
        print("[DEBUG] Starting Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=DEBUG_MODE)
