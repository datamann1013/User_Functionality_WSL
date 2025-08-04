from .error_codes import ERROR_CODE_DEFINITIONS
from .logger import log_error_remote
import sys
import traceback


def get_error_explanation(error_code, custom_message=None):
    """Return explanation with fallback to standard"""
    if custom_message:
        return custom_message

    explanation = ERROR_CODE_DEFINITIONS.get(error_code)
    if explanation:
        return explanation

    return f"Undefined error code: {error_code} (standard)"


def log_python_exception(exc_type, exc_value, exc_traceback):
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_error_remote(
        "E00000",
        message="Python exception occurred (standard)",
        exception=error_message
    )


# Set global exception handler
sys.excepthook = log_python_exception


def log_react_exception(error_info):
    log_error_remote(
        "E00001",
        message="React exception occurred (standard)",
        exception=error_info
    )