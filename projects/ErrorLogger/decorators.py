from functools import wraps
from flask import request, jsonify
from werkzeug.exceptions import HTTPException
from .logger import log_error_remote
from .error_handler import get_error_explanation


def flask_error_handler(e):
    """Global Flask error handler"""
    if isinstance(e, HTTPException):
        return e.get_response()

    error_code = getattr(e, 'error_code', 'E00000')
    explanation = get_error_explanation(error_code)

    log_error_remote(
        error_code,
        message=explanation,
        exception=f"{request.method} {request.path} | {str(e)}"
    )

    response = {
        'error': 'Internal Server Error',
        'message': explanation,
        'code': error_code
    }
    return jsonify(response), 500


def log_exceptions(error_code):
    """Decorator for route-specific error handling"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                explanation = get_error_explanation(error_code)

                log_error_remote(
                    error_code,
                    message=explanation,
                    exception=f"{request.method} {request.path} | {str(e)}"
                )

                response = {
                    'error': 'Application Error',
                    'message': explanation,
                    'code': error_code
                }
                return jsonify(response), 500

        return wrapper

    return decorator