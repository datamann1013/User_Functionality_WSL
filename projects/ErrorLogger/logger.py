import os
from datetime import datetime
import json
import threading
import sys
import uuid
import requests
from platform import uname

# Load configuration with fallback
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    """Load config with fallback to error_codes.py"""
    config = {
        'error_explanations': {},
        'logging': {'enable_console_debug': False, 'log_retention_days': 30, 'max_log_file_size_mb': 10},
        'service': {'remote_url': 'http://localhost:5001/log', 'timeout_seconds': 5, 'retry_attempts': 1}
    }
    
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass  # Use defaults
    
    # Fallback to error_codes.py if no explanations in config
    if not config['error_explanations']:
        try:
            from .error_codes import ERROR_CODE_DEFINITIONS
            config['error_explanations'] = ERROR_CODE_DEFINITIONS
        except ImportError:
            pass
    
    return config

CONFIG = load_config()
ERROR_EXPLANATIONS = CONFIG['error_explanations']
ERRORLOGGER_SERVICE_URL = os.environ.get('ERRORLOGGER_SERVICE_URL', CONFIG['service']['remote_url'])

LOG_FILE_PATH = None
LOG_FILE_LOCK = threading.Lock()


def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _init_log_file():
    global LOG_FILE_PATH
    while True:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        # Use WSL-friendly path if detected
        if 'microsoft' in uname().release.lower():
            root_dir = os.path.expanduser('~/logs')
            os.makedirs(root_dir, exist_ok=True)
        else:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

        log_filename = f'errorlog_{timestamp}.csv'
        log_path = os.path.join(root_dir, log_filename)
        if not os.path.exists(log_path):
            LOG_FILE_PATH = log_path
            break
        # If file exists, append a short uuid
        log_filename = f'errorlog_{timestamp}_{uuid.uuid4().hex[:6]}.csv'
        log_path = os.path.join(root_dir, log_filename)
        if not os.path.exists(log_path):
            LOG_FILE_PATH = log_path
            break

    # Write CSV header
    with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("timestamp;error_code;explanation;exception;extra\n")
    return LOG_FILE_PATH


# Initialize log file at module load
if LOG_FILE_PATH is None:
    _init_log_file()


def get_explanation(error_code, message=None):
    """Returns explanation with (standard) tag if using default"""
    if message:
        return message

    explanation = ERROR_EXPLANATIONS.get(error_code)
    if explanation:
        return explanation

    return "Unidentified error (standard)"


def log_error(error_code, message=None, exception=None, extra=None):
    timestamp = get_timestamp()
    explanation = get_explanation(error_code, message)

    # Format exception and extra
    exception_str = str(exception) if exception else ""
    extra_str = json.dumps(extra) if extra else ""

    # CSV format: timestamp;error_code;explanation;exception;extra
    log_line = f"{timestamp};{error_code};{explanation};{exception_str};{extra_str}"

    # Console debug output if enabled
    if CONFIG['logging']['enable_console_debug'] or os.getenv('DEBUG'):
        print(f"[{timestamp}] {error_code}: {explanation}")
        if exception_str:
            print(f"  Exception: {exception_str}")

    with LOG_FILE_LOCK:
        # Ensure file path is initialized
        if LOG_FILE_PATH is None:
            _init_log_file()

        with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')


def log_error_remote(error_code, message=None, exception=None, extra=None):
    """Synchronous logging with response validation"""
    payload = {
        'error_code': error_code,
        'message': message,
        'exception': exception,
        'extra': extra
    }
    try:
        # Use config settings for timeout and retry
        timeout = CONFIG['service']['timeout_seconds']
        response = requests.post(
            ERRORLOGGER_SERVICE_URL,
            json=payload,
            timeout=timeout
        )

        if response.status_code != 200:
            raise Exception(f"Remote logger returned {response.status_code}")

    except Exception as e:
        # Fallback to local log with special error code
        log_error(
            "EREM1",
            message="Remote logger failed (standard)",
            exception=f"{e} | Original error: {error_code}",
            extra=payload
        )


def generate_error_code(level, origin, component, subcomponent, number):
    """Generate structured error code"""
    if not subcomponent:
        subcomponent = '#'
    return f"{level}{origin}{component}{subcomponent}{str(number).zfill(2)}"


def _exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    from traceback import format_exception
    exception_str = ''.join(format_exception(exc_type, exc_value, exc_traceback))
    log_error_remote("E00000", message="Unhandled Python exception (standard)", exception=exception_str)


sys.excepthook = _exception_hook