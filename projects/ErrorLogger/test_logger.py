import os
import glob
from projects.ErrorLogger import logger
import json


def get_latest_log_file():
    # Get project root and logs directory (same logic as logger.py)
    current_file = os.path.abspath(__file__)
    errorlogger_dir = os.path.dirname(current_file)  # projects/ErrorLogger/
    projects_dir = os.path.dirname(errorlogger_dir)  # projects/
    project_root = os.path.dirname(projects_dir)     # User_Functionality_WSL/
    log_dir = os.path.join(project_root, 'logs')
    
    files = glob.glob(os.path.join(log_dir, 'errorlog_*.csv'))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def test_csv_file_creation_and_format():
    # Clean existing logs and reset logger state - use same logic as get_latest_log_file
    current_file = os.path.abspath(__file__)
    errorlogger_dir = os.path.dirname(current_file)
    projects_dir = os.path.dirname(errorlogger_dir)
    project_root = os.path.dirname(projects_dir)
    log_dir = os.path.join(project_root, 'logs')
    
    pattern = os.path.join(log_dir, 'errorlog_*.csv')
    for f in glob.glob(pattern):
        os.remove(f)

    # Reset the logger's log file path to force reinitialization
    logger.LOG_FILE_PATH = None

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


def test_config_integration():
    """Test that configuration is loaded properly"""
    # Test that CONFIG is loaded
    assert hasattr(logger, 'CONFIG')
    assert 'error_explanations' in logger.CONFIG
    assert 'logging' in logger.CONFIG
    assert 'service' in logger.CONFIG
    
    # Test that error explanations work
    assert len(logger.CONFIG['error_explanations']) > 0
    
    # Test a known error code
    explanation = logger.get_explanation('EABS1')
    assert explanation == "Missing required model files"
    
    # Test fallback for unknown code
    explanation = logger.get_explanation('UNKNOWN123')
    assert "(standard)" in explanation


def test_log_rotation_status():
    """Test log rotation status reporting"""
    # Reset logger state
    logger.LOG_FILE_PATH = None
    
    # Create a log entry to initialize
    logger.log_error('TEST_ROTATION', message="Testing rotation status")
    
    # Get rotation status
    status = logger.get_log_rotation_status()
    
    # Verify status structure
    assert 'current_log_file' in status
    assert 'log_directory' in status
    assert 'max_file_size_mb' in status
    assert 'retention_days' in status
    assert 'current_file_size_mb' in status
    assert 'will_rotate_soon' in status
    assert 'total_log_files' in status
    
    # Verify reasonable values
    assert status['max_file_size_mb'] > 0
    assert status['retention_days'] > 0
    assert status['current_file_size_mb'] >= 0
    assert status['total_log_files'] >= 1  # At least the file we just created

# Add more tests as needed...