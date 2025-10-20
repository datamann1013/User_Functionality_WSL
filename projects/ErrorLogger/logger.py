import os
import json
import threading
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, Union

# Pre-load configuration for faster access
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_CONFIG: Dict[str, Any] = {
    "error_explanations": {},
    "logging": {
        "enable_console_debug": False,
        "log_retention_days": 30,
        "max_log_file_size_mb": 10,
    },
    "service": {
        "remote_url": "http://localhost:5001/log",
        "timeout_seconds": 5,
        "retry_attempts": 1,
    },
}

# Load config once at module import
CONFIG: Dict[str, Any] = DEFAULT_CONFIG.copy()
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            CONFIG.update(json.load(f))
    except (json.JSONDecodeError, IOError, UnicodeDecodeError):
        pass

# Fallback to error_codes if needed
if not CONFIG["error_explanations"]:
    try:
        from .error_codes import ERROR_CODE_DEFINITIONS

        CONFIG["error_explanations"] = ERROR_CODE_DEFINITIONS
    except ImportError:
        pass

# Pre-compute frequently used values
ERROR_EXPLANATIONS = CONFIG["error_explanations"]
ERRORLOGGER_SERVICE_URL = os.environ.get(
    "ERRORLOGGER_SERVICE_URL", CONFIG["service"]["remote_url"]
)
ENABLE_DEBUG = CONFIG["logging"]["enable_console_debug"] or os.getenv("DEBUG")
MAX_FILE_SIZE_BYTES = CONFIG["logging"]["max_log_file_size_mb"] * 1024 * 1024
RETENTION_SECONDS = CONFIG["logging"]["log_retention_days"] * 24 * 3600

# Thread-safe globals
LOG_FILE_PATH = None
LOG_FILE_LOCK = threading.Lock()
LAST_CLEANUP = 0


def get_log_directory():
    """Get log directory with caching"""
    if "LOG_DIRECTORY" in os.environ:
        log_dir = os.environ["LOG_DIRECTORY"]
    else:
        # Cache the directory path computation
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        log_dir = os.path.join(project_root, "logs")

    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def safe_json_dumps(obj):
    """Fast JSON serialization with type handling"""
    if obj is None:
        return ""

    def serializer(o):
        if isinstance(o, Decimal):
            return float(o)
        elif isinstance(o, datetime):
            return o.isoformat()
        elif isinstance(o, timedelta):
            return str(o)
        return str(o)

    try:
        return json.dumps(obj, default=serializer, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(obj)


def init_log_file():
    """Initialize log file with unique name"""
    global LOG_FILE_PATH

    log_dir = get_log_directory()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE_PATH = os.path.join(log_dir, f"errorlog_{timestamp}.csv")

    # Write header only if file doesn't exist
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("timestamp;error_code;explanation;exception;extra\n")


def cleanup_old_logs():
    """Efficient log cleanup with time-based caching"""
    global LAST_CLEANUP

    now = datetime.now().timestamp()
    # Only cleanup once per hour to reduce overhead
    if now - LAST_CLEANUP < 3600:
        return

    LAST_CLEANUP = now
    cutoff_time = now - RETENTION_SECONDS

    log_dir = get_log_directory()
    try:
        for filename in os.listdir(log_dir):
            if filename.startswith("errorlog_") and filename.endswith(".csv"):
                filepath = os.path.join(log_dir, filename)
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
    except OSError:
        pass


def get_explanation(error_code, message=None):
    """Fast explanation lookup"""
    return message or ERROR_EXPLANATIONS.get(
        error_code, "Unidentified error (standard)"
    )


def log_error(error_code, message=None, exception=None, extra=None):
    """Optimized local logging"""
    global LOG_FILE_PATH

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    explanation = get_explanation(error_code, message)
    exception_str = str(exception) if exception else ""
    extra_str = safe_json_dumps(extra) if extra else ""

    # Debug output (minimal overhead when disabled)
    if ENABLE_DEBUG:
        print(f"[{timestamp}] {error_code}: {explanation}")

    with LOG_FILE_LOCK:
        # Initialize file if needed
        if LOG_FILE_PATH is None:
            init_log_file()

        # Check file size for rotation (efficient check)
        try:
            if os.path.getsize(LOG_FILE_PATH) >= MAX_FILE_SIZE_BYTES:
                init_log_file()
        except OSError:
            init_log_file()

        # Periodic cleanup (low overhead)
        cleanup_old_logs()

        # Write log entry
        log_line = (
            f"{timestamp};{error_code};{explanation};{exception_str};{extra_str}\n"
        )
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)


def log_error_remote(error_code, message=None, exception=None, extra=None):
    """Optimized remote logging with fast fallback"""
    payload = {
        "error_code": error_code,
        "message": message,
        "exception": str(exception) if exception else None,
        "extra": extra,
    }

    try:
        response = requests.post(  # nosec B113
            ERRORLOGGER_SERVICE_URL,
            json=payload,
            timeout=CONFIG["service"]["timeout_seconds"],
        )
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
    except Exception as e:
        # Fast fallback to local logging
        log_error(
            "EREM1",
            message="Remote logger failed (standard)",
            exception=f"{e} | Original: {error_code}",
            extra={"original_payload": str(payload)},
        )


# Initialize on import
init_log_file()


def generate_error_code(level, origin, component, subcomponent, number):
    """Generate structured error code (compatibility function)"""
    if not subcomponent:
        subcomponent = "#"
    return f"{level}{origin}{component}{subcomponent}{str(number).zfill(2)}"


def get_log_rotation_status():
    """Get current log rotation status (compatibility function)"""
    status = {
        "current_log_file": LOG_FILE_PATH,
        "log_directory": get_log_directory(),
        "rotation_enabled": True,
        "max_file_size_mb": CONFIG["logging"]["max_log_file_size_mb"],
        "retention_days": CONFIG["logging"]["log_retention_days"],
        "last_cleanup_check": (
            datetime.fromtimestamp(LAST_CLEANUP) if LAST_CLEANUP else None
        ),
    }

    if LOG_FILE_PATH and os.path.exists(LOG_FILE_PATH):
        status["current_file_size_mb"] = round(
            os.path.getsize(LOG_FILE_PATH) / (1024 * 1024), 2
        )
        status["will_rotate_soon"] = (
            os.path.getsize(LOG_FILE_PATH) >= MAX_FILE_SIZE_BYTES
        )
    else:
        status["current_file_size_mb"] = 0
        status["will_rotate_soon"] = False

    # Count log files
    log_dir = get_log_directory()
    try:
        status["total_log_files"] = len(
            [
                f
                for f in os.listdir(log_dir)
                if f.startswith("errorlog_") and f.endswith(".csv")
            ]
        )
    except OSError:
        status["total_log_files"] = 0

    return status


# Optimized exception hook
def _exception_hook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        return

    import traceback

    exception_str = "".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback)
    )
    log_error_remote(
        "E00000",
        message="Unhandled Python exception (standard)",
        exception=exception_str,
    )


import sys

sys.excepthook = _exception_hook
