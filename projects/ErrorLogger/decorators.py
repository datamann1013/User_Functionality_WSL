from functools import wraps
from flask import request, jsonify, current_app
from .logger import log_error

# Flask error handler for unhandled exceptions

def flask_error_handler(e):
    # Log with request context
    log_error(0, exception=f"{request.method} {request.path} | {repr(e)}")
    response = {
        'error': 'Internal Server Error',
        'message': str(e),
        'code': '00000'
    }
    return jsonify(response), 500

# Decorator for Flask routes to log handled exceptions with custom error codes

def log_exceptions(error_code):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error(error_code, exception=f"{request.method} {request.path} | {repr(e)}")
                response = {
                    'error': 'Application Error',
                    'message': str(e),
                    'code': error_code
                }
                return jsonify(response), 500
        return wrapper
    return decorator

