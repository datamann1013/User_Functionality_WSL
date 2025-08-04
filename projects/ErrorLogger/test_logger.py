import os
import glob
from projects.ErrorLogger import logger
import json


def get_latest_log_file():
    if 'microsoft' in os.uname().release.lower():
        log_dir = os.path.expanduser('~/logs')
    else:
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

    files = glob.glob(os.path.join(log_dir, 'errorlog_*.csv'))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def test_csv_file_creation_and_format():
    # Clean existing logs
    log_dir = os.path.expanduser('~/logs') if 'microsoft' in os.uname().release.lower() else os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../..'))
    pattern = os.path.join(log_dir, 'errorlog_*.csv')
    for f in glob.glob(pattern):
        os.remove(f)

    # Test log
    logger.log_error('TEST01', message="Test error", exception="Test exception", extra={"key": "value"})

    # Verify
    log_file = get_latest_log_file()
    assert log_file is not None

    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Check header
    assert lines[0].strip() == "timestamp;error_code;explanation;exception;extra"

    # Check content format
    assert len(lines) >= 2
    parts = lines[1].split(';', 4)  # Split into 5 parts (maxsplit=4)
    assert len(parts) == 5
    assert parts[1] == "TEST01"
    assert parts[2] == "Test error"
    assert parts[3] == "Test exception"
    assert json.loads(parts[4].strip()) == {"key": "value"}


def test_standard_message_fallback():
    logger.log_error('UNDEFINED_CODE')
    log_file = get_latest_log_file()
    assert log_file is not None

    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Get last non-empty line
    last_line = None
    for line in reversed(lines):
        if line.strip():
            last_line = line
            break

    assert last_line is not None
    parts = last_line.split(';', 4)
    assert len(parts) >= 3
    assert "(standard)" in parts[2]

# Add more tests as needed...