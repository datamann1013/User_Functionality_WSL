import os
from datetime import datetime
import json
import threading
import sys
import uuid

LOG_FILE_PATH = None
LOG_FILE_LOCK = threading.Lock()

# Load explanations from config file (JSON)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_explanations():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

ERROR_EXPLANATIONS = load_explanations()

def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _init_log_file():
    global LOG_FILE_PATH
    while True:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Add milliseconds
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
        log_filename = f'errorlog_{timestamp}.log'
        log_path = os.path.join(root_dir, log_filename)
        if not os.path.exists(log_path):
            LOG_FILE_PATH = log_path
            break
        # If file exists, append a short uuid
        log_filename = f'errorlog_{timestamp}_{uuid.uuid4().hex[:6]}.log'
        log_path = os.path.join(root_dir, log_filename)
        if not os.path.exists(log_path):
            LOG_FILE_PATH = log_path
            break
    with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(f"Log file created at {get_timestamp()}\n")
    return LOG_FILE_PATH

_init_log_file()

def get_explanation(error_code, message=None):
    return ERROR_EXPLANATIONS.get(error_code, message or 'No explanation provided')

def log_error(error_code, message=None, exception=None):
    timestamp = get_timestamp()
    if error_code == 0 and exception is not None:
        # Use '00000' as the error code for Python exceptions
        log_message = f"[{timestamp}] 00000: {repr(exception)}"
    else:
        explanation = get_explanation(error_code, message)
        log_message = f"[{timestamp}] {error_code}: {explanation}"
    with LOG_FILE_LOCK:
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

def _exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    from traceback import format_exception
    exception_str = ''.join(format_exception(exc_type, exc_value, exc_traceback))
    log_error(0, exception=exception_str)

sys.excepthook = _exception_hook
