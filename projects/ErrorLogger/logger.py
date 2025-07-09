import os
from datetime import datetime
from projects.shared_utils.constants import ERROR_EXPLANATIONS

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'error.log')

def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log_error(error_code, message=None, exception=None):
    timestamp = get_timestamp()
    if error_code == 0 and exception is not None:
        log_message = f"[{timestamp}] 0: {repr(exception)}"
    else:
        explanation = ERROR_EXPLANATIONS.get(error_code, message or 'No explanation provided')
        log_message = f"[{timestamp}] {error_code}: {explanation}"
    with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
        f.write(log_message + '\n')

def generate_error_code(level, origin, component, subcomponent, number):
    """
    Generate an error code string.
    level: 'E', 'W', 'I', etc. (Error, Warning, Info)
    origin: single letter (e.g., 'A')
    component: single letter (e.g., 'B')
    subcomponent: single letter or '#' if not needed
    number: int or str, up to two digits
    """
    if not subcomponent:
        subcomponent = '#'
    return f"{level}{origin}{component}{subcomponent}{str(number).zfill(2)}"
