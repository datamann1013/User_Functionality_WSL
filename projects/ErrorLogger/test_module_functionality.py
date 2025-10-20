import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the modules that work
import error_codes
import logger


class TestModuleImports(unittest.TestCase):
    """Test basic module imports and functionality"""
    
    def test_error_codes_import(self):
        """Test error_codes module imports correctly"""
        self.assertTrue(hasattr(error_codes, '__file__'))
    
    def test_logger_import(self):
        """Test logger module imports correctly"""
        self.assertTrue(hasattr(logger, 'log_error'))
        self.assertTrue(hasattr(logger, 'log_error_remote'))
    
    def test_logger_functions_exist(self):
        """Test that logger functions are callable"""
        self.assertTrue(callable(logger.log_error))
        self.assertTrue(callable(logger.log_error_remote))
        if hasattr(logger, 'safe_json_dumps'):
            self.assertTrue(callable(logger.safe_json_dumps))


class TestLoggerWithMocks(unittest.TestCase):
    """Test logger functionality with mocked dependencies"""
    
    @patch('logger.requests.post')
    @patch('logger.os.path.exists')
    @patch('logger.open', create=True)
    def test_log_error_remote_success(self, mock_open, mock_exists, mock_post):
        """Test successful remote error logging"""
        # Setup mocks
        mock_exists.return_value = True
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Call function
        result = logger.log_error_remote("E12345", "Test message")
        
        # Verify result
        self.assertTrue(result)
    
    @patch('logger.requests.post')
    def test_log_error_remote_failure(self, mock_post):
        """Test remote error logging failure handling"""
        # Setup mock to raise exception
        mock_post.side_effect = Exception("Connection failed")
        
        # Call function
        result = logger.log_error_remote("E12345", "Test message")
        
        # Should handle exception gracefully
        self.assertFalse(result)
    
    @patch('logger.open', create=True)
    @patch('logger.os.makedirs')
    @patch('logger.os.path.exists')
    def test_log_error_local_file_creation(self, mock_exists, mock_makedirs, mock_open):
        """Test local error logging with file creation"""
        # Setup mocks
        mock_exists.return_value = False
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Call function
        logger.log_error("E54321", "Test local message")
        
        # Verify directory creation and file writing
        mock_makedirs.assert_called()
        mock_open.assert_called()
        mock_file.write.assert_called()


class TestLoggerSafeJsonDumps(unittest.TestCase):
    """Test JSON serialization functionality"""
    
    def test_safe_json_dumps_basic_dict(self):
        """Test JSON dumping with basic dictionary"""
        if hasattr(logger, 'safe_json_dumps'):
            test_data = {"key": "value", "number": 123}
            result = logger.safe_json_dumps(test_data)
            self.assertIsInstance(result, str)
            self.assertIn("key", result)
    
    def test_safe_json_dumps_with_datetime(self):
        """Test JSON dumping with datetime objects"""
        if hasattr(logger, 'safe_json_dumps'):
            from datetime import datetime, timedelta
            test_data = {
                "timestamp": datetime.now(),
                "duration": timedelta(seconds=30)
            }
            result = logger.safe_json_dumps(test_data)
            self.assertIsInstance(result, str)
    
    def test_safe_json_dumps_with_non_serializable(self):
        """Test JSON dumping with non-serializable objects"""
        if hasattr(logger, 'safe_json_dumps'):
            test_data = {"function": lambda x: x}
            result = logger.safe_json_dumps(test_data)
            self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
