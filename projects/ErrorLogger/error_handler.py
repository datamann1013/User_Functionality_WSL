from functools import wraps
from flask import request, jsonify
from werkzeug.exceptions import HTTPException

# Pre-import optimized logger
from .logger_optimized import log_error_remote, ERROR_EXPLANATIONS


def get_error_explanation(error_code, custom_message=None):
    """Fast explanation lookup"""
    return custom_message or ERROR_EXPLANATIONS.get(error_code, f"Undefined error code: {error_code} (standard)")


def flask_error_handler(e):
    """Optimized Flask error handler"""
    if isinstance(e, HTTPException):
        return e.get_response()

    error_code = getattr(e, 'error_code', 'E00000')
    explanation = get_error_explanation(error_code)

    log_error_remote(
        error_code,
        message=explanation,
        exception=f"{request.method} {request.path} | {str(e)}"
    )

    return jsonify({
        'error': 'Internal Server Error',
        'message': explanation,
        'code': error_code
    }), 500


def log_exceptions(error_code):
    """Optimized decorator for route-specific error handling"""
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

                return jsonify({
                    'error': 'Application Error',
                    'message': explanation,
                    'code': error_code
                }), 500
        return wrapper
    return decorator


def log_python_exception(exc_type, exc_value, exc_traceback):
    """Optimized Python exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        return
    
    import traceback
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_error_remote(
        "E00000",
        message="Python exception occurred (standard)",
        exception=error_message
    )


def log_react_exception(error_info):
    """Optimized React exception handler"""
    log_error_remote(
        "E00001",
        message="React exception occurred (standard)",
        exception=error_info
    )
