from flask import Flask, request, jsonify
from logger import log_error_remote

app = Flask(__name__)

@app.route('/log', methods=['POST'])
def log():
    data = request.get_json(force=True)
    error_code = data.get('error_code', 0)
    exception = data.get('exception', '')
    extra = data.get('extra', None)
    log_error_remote(error_code, exception=exception, extra=extra)
    return jsonify({'status': 'logged'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
