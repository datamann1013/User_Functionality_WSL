from .error_codes import ERROR_CODE_DEFINITIONS

def get_error_explanation(error_code, custom_message=None):
    """
    Returns the standard explanation for an error code, unless a custom message is provided.
    If the error code is not registered, logs an error about the unknown code.
    """
    if custom_message:
        return custom_message
    explanation = ERROR_CODE_DEFINITIONS.get(error_code)
    if explanation is None:
        # Log an error about the unknown error code
        from .logger import log_error
        log_error("E00000", message=f"Unknown error code received: {error_code}")
        return f"Unknown error code: {error_code}"
    return explanation

# Utility to ensure all Python/React errors are sent to logger
import sys
import traceback

def log_python_exception(exc_type, exc_value, exc_traceback):
    from .logger import log_error
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_error("E00000", message="Python exception occurred.", exception=error_message)
    # Optionally, also log the original error code if available

sys.excepthook = log_python_exception

# For React errors, ensure frontend sends E00001 with details to logger
# (Frontend code should already do this via errorLogger.js)
