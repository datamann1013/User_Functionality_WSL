#!/usr/bin/env python3
"""
Basic functionality tests for ErrorLogger components
to improve test coverage
"""
import os
import sys
import json
import tempfile
import unittest.mock as mock

# Add the ErrorLogger directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from logger import (
    log_error,
    get_explanation,
    get_log_rotation_status,
    safe_json_dumps,
    get_log_directory,
)
from error_codes import ERROR_CODE_DEFINITIONS


def test_error_code_definitions():
    """Test that error code definitions are properly loaded"""
    assert isinstance(ERROR_CODE_DEFINITIONS, dict)
    assert len(ERROR_CODE_DEFINITIONS) > 0
    assert "EABS1" in ERROR_CODE_DEFINITIONS
    assert ERROR_CODE_DEFINITIONS["EABS1"] == "Missing required model files"


def test_get_explanation():
    """Test error explanation retrieval"""
    # Test known error code
    explanation = get_explanation("EABS1")
    assert explanation == "Missing required model files"

    # Test unknown error code
    explanation = get_explanation("UNKNOWN_CODE")
    assert "(standard)" in explanation
    assert "Unidentified error" in explanation

    # Test custom message
    custom_explanation = get_explanation("EABS1", "Custom message")
    assert custom_explanation == "Custom message"


def test_safe_json_dumps():
    """Test safe JSON serialization"""
    from decimal import Decimal
    from datetime import datetime, timedelta

    # Test None
    result = safe_json_dumps(None)
    assert result == ""

    # Test simple object
    simple_obj = {"key": "value", "number": 42}
    result = safe_json_dumps(simple_obj)
    assert json.loads(result) == simple_obj

    # Test complex object with special types
    complex_obj = {
        "decimal": Decimal("123.45"),
        "datetime": datetime(2023, 1, 1, 12, 0, 0),
        "timedelta": timedelta(hours=1),
        "string": "test",
        "number": 42,
    }
    result = safe_json_dumps(complex_obj)
    parsed = json.loads(result)

    assert parsed["decimal"] == 123.45
    assert parsed["string"] == "test"
    assert parsed["number"] == 42
    assert "2023-01-01T12:00:00" in parsed["datetime"]
    # timedelta should be converted to string representation
    assert "1:00:00" in parsed["timedelta"]


def test_get_log_directory():
    """Test log directory creation and retrieval"""
    # Test default directory
    log_dir = get_log_directory()
    assert os.path.exists(log_dir)
    assert os.path.isdir(log_dir)

    # Test with environment variable
    with mock.patch.dict(os.environ, {"LOG_DIRECTORY": "/tmp/test_logs"}):
        log_dir = get_log_directory()
        assert log_dir == "/tmp/test_logs"
        assert os.path.exists(log_dir)


def test_log_rotation_status():
    """Test log rotation status functionality"""
    status = get_log_rotation_status()

    # Check required keys
    required_keys = [
        "current_log_file",
        "log_directory",
        "max_file_size_mb",
        "retention_days",
        "current_file_size_mb",
        "will_rotate_soon",
        "total_log_files",
    ]

    for key in required_keys:
        assert key in status, f"Missing key: {key}"

    # Check value types and ranges
    assert isinstance(status["max_file_size_mb"], (int, float))
    assert status["max_file_size_mb"] > 0

    assert isinstance(status["retention_days"], int)
    assert status["retention_days"] > 0

    assert isinstance(status["current_file_size_mb"], (int, float))
    assert status["current_file_size_mb"] >= 0

    assert isinstance(status["will_rotate_soon"], bool)
    assert isinstance(status["total_log_files"], int)
    assert status["total_log_files"] >= 0


def test_log_error_basic():
    """Test basic error logging functionality"""
    # Test minimal logging
    log_error("TEST_BASIC", "Test message")

    # Test with exception
    log_error("TEST_EXCEPTION", "Test with exception", "Exception details")

    # Test with extra data
    extra_data = {"user_id": 123, "action": "test"}
    log_error("TEST_EXTRA", "Test with extra", "Exception", extra=extra_data)

    # Test with None values
    log_error("TEST_NONE", None, None, extra=None)

    # Verify log file was created
    status = get_log_rotation_status()
    assert status["current_log_file"] is not None
    assert os.path.exists(status["current_log_file"])


def test_config_loading():
    """Test configuration loading"""
    from logger import CONFIG

    # Verify config structure
    assert isinstance(CONFIG, dict)
    assert "error_explanations" in CONFIG
    assert "logging" in CONFIG
    assert "service" in CONFIG

    # Verify logging config
    logging_config = CONFIG["logging"]
    assert "enable_console_debug" in logging_config
    assert "log_retention_days" in logging_config
    assert "max_log_file_size_mb" in logging_config

    # Verify service config
    service_config = CONFIG["service"]
    assert "remote_url" in service_config
    assert "timeout_seconds" in service_config
    assert "retry_attempts" in service_config


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
