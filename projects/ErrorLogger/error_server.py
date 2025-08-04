import os
from flask import Flask, request, jsonify
import sys
import argparse

# Add parent directory to path for proper imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from logger import log_error

app = Flask(__name__)

# Disable CSRF protection since this is an API-only service
app.config['WTF_CSRF_ENABLED'] = False


@app.route('/log', methods=['POST'])
def log_endpoint():
    data = request.get_json(force=True)

    # Validate required fields
    if 'error_code' not in data:
        return jsonify({'error': 'Missing error_code'}), 400

    # Log with local CSV writer
    log_error(
        data.get('error_code'),
        message=data.get('message'),
        exception=data.get('exception'),
        extra=data.get('extra')
    )

    return jsonify({'status': 'logged', 'code': data['error_code']}), 200


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'error_logger'}), 200


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    app.run(host='0.0.0.0', port=5001, debug=args.debug)