import sys
import os
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from flask import Flask, jsonify, request
from projects.ai_service.backend.api.model_registry import registry_bp

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

app = Flask(__name__)
app.register_blueprint(registry_bp)

@app.errorhandler(Exception)
def handle_exception(e):
    # Log error to ErrorLogger service
    log_error_to_service(0, exception=f"{request.method} {request.path} | {repr(e)}")
    response = {
        'error': 'Internal Server Error',
        'message': str(e),
        'code': '00000'
    }
    return jsonify(response), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
