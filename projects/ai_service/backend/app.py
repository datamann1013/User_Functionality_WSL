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
        'message': message or get_error_explanation(error_code),
        'exception': exception,
        'extra': extra
    }
    try:
        requests.post(ERRORLOGGER_SERVICE_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ErrorLogger Service Unreachable] {e}")

# Import error code definitions
try:
    from projects.ErrorLogger.error_codes import ERROR_CODE_DEFINITIONS
except ImportError:
    ERROR_CODE_DEFINITIONS = {}

def get_error_explanation(error_code):
    return ERROR_CODE_DEFINITIONS.get(error_code, "No explanation provided")

# Parse debug flag from command line
parser = argparse.ArgumentParser()
parser.add_argument('--debug', '-DEBUG', action='store_true', help='Enable debug output')
args, unknown = parser.parse_known_args()
DEBUG_MODE = args.debug
if DEBUG_MODE:
    log_error_to_service("IAXX1", message=get_error_explanation("IAXX1"))
    print("[DEBUG] Debug mode enabled.")

# Ensure at least one model is downloaded and set up before starting the app
try:
    if DEBUG_MODE:
        log_error_to_service("IABS1", message=get_error_explanation("IABS1"))
        print("[DEBUG] Running setup_models.py to ensure model setup...")
    subprocess.run([
        sys.executable,
        os.path.join(os.path.dirname(__file__), '../bootstrap/setup_models.py'),
        "--debug"
    ], check=True)
    if DEBUG_MODE:
        print("[DEBUG] Model setup script completed.")
except subprocess.CalledProcessError as e:
    log_error_to_service("EABS1", message=get_error_explanation("EABS1"), exception=str(e))
    print("\n[Startup Error] Model setup failed. Please resolve the above issue and restart the backend.")
    sys.exit(1)

app = Flask(__name__)
app.register_blueprint(registry_bp)
app.register_blueprint(inference_bp, url_prefix="/api")

@app.errorhandler(Exception)
def handle_exception(e):
    # Catch all unhandled exceptions in Flask app
    error_code = getattr(e, 'error_code', 'E00000')
    explanation = get_error_explanation(error_code)
    log_error_to_service(error_code, message=explanation, exception=str(e), extra={"path": request.path, "method": request.method})
    if DEBUG_MODE:
        print(f"[DEBUG] Unhandled exception: {repr(e)} at {request.method} {request.path}")
    # Try to gently deal with the error: return a generic error response
    response = {
        'error': 'Internal Server Error',
        'message': explanation,
        'code': error_code
    }
    return jsonify(response), 500

@app.route('/health', methods=['GET'])
def health():
    try:
        if DEBUG_MODE:
            log_error_to_service("IAXX1", message=get_error_explanation("IAXX1"))
            print("[DEBUG] /health endpoint called.")
        return jsonify({'status': 'ok'})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'E00000')
        explanation = get_error_explanation(error_code)
        log_error_to_service(error_code, message=explanation, exception=str(e))
        return jsonify({'error': explanation, 'code': error_code}), 500
