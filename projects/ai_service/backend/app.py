from flask import Flask, jsonify
from api.model_registry import registry_bp
from ErrorLogger.decorators import flask_error_handler

app = Flask(__name__)
app.register_blueprint(registry_bp)
app.register_error_handler(Exception, flask_error_handler)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
