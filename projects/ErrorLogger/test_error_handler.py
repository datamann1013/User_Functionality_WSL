import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import traceback
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from werkzeug.exceptions import BadRequest

# Mock the relative imports to avoid import errors
with patch.dict('sys.modules', {
    'logger_optimized': Mock(log_error_remote=Mock(), ERROR_EXPLANATIONS={'E12345': 'Test error'})
}):
    import error_handler
    from error_handler import (
        get_error_explanation,
        flask_error_handler,
        log_exceptions,
        log_python_exception,
        log_react_exception
    )


class TestErrorHandler(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

    def test_get_error_explanation_with_custom_message(self):
        """Test get_error_explanation with custom message"""
        result = get_error_explanation("E12345", "Custom error message")
        self.assertEqual(result, "Custom error message")

    @patch("error_handler.ERROR_EXPLANATIONS", {"E12345": "Known error message"})
    def test_get_error_explanation_known_code(self):
        """Test get_error_explanation with known error code"""
        result = get_error_explanation("E12345")
        self.assertEqual(result, "Known error message")

    @patch("error_handler.ERROR_EXPLANATIONS", {})
    def test_get_error_explanation_unknown_code(self):
        """Test get_error_explanation with unknown error code"""
        result = get_error_explanation("E99999")
        self.assertEqual(result, "Undefined error code: E99999 (standard)")

    @patch("error_handler.log_error_remote")
    @patch("error_handler.get_error_explanation")
    def test_flask_error_handler_http_exception(self, mock_get_explanation, mock_log):
        """Test flask_error_handler with HTTP exceptions"""
        http_error = BadRequest("Test bad request")
        
        with self.app.test_request_context('/test'):
            result = flask_error_handler(http_error)
            
        # Should return the HTTP exception response directly
        self.assertEqual(result.status_code, 400)
        mock_log.assert_not_called()
        mock_get_explanation.assert_not_called()

    @patch("error_handler.log_error_remote")
    @patch("error_handler.get_error_explanation")
    def test_flask_error_handler_custom_exception(self, mock_get_explanation, mock_log):
        """Test flask_error_handler with custom exceptions"""
        mock_get_explanation.return_value = "Test error explanation"
        
        # Create custom exception with error code
        test_error = Exception("Test error")
        test_error.error_code = "E12345"
        
        with self.app.test_request_context('/test', method='POST'):
            result = flask_error_handler(test_error)
            
        # Should log error and return JSON response
        mock_log.assert_called_once_with(
            "E12345",
            message="Test error explanation",
            exception="POST /test | Test error"
        )
        mock_get_explanation.assert_called_once_with("E12345")
        
        self.assertEqual(result[1], 500)  # Status code
        response_data = json.loads(result[0].get_data(as_text=True))
        self.assertEqual(response_data["error"], "Internal Server Error")
        self.assertEqual(response_data["message"], "Test error explanation")
        self.assertEqual(response_data["code"], "E12345")

    @patch("error_handler.log_error_remote")
    @patch("error_handler.get_error_explanation")
    def test_flask_error_handler_exception_without_code(self, mock_get_explanation, mock_log):
        """Test flask_error_handler with exception without error code"""
        mock_get_explanation.return_value = "Default error explanation"
        
        test_error = Exception("Test error without code")
        
        with self.app.test_request_context('/test'):
            result = flask_error_handler(test_error)
            
        # Should use default error code E00000
        mock_log.assert_called_once_with(
            "E00000",
            message="Default error explanation",
            exception="GET /test | Test error without code"
        )
        mock_get_explanation.assert_called_once_with("E00000")

    @patch("error_handler.log_error_remote")
    @patch("error_handler.get_error_explanation")
    def test_log_exceptions_decorator_success(self, mock_get_explanation, mock_log):
        """Test log_exceptions decorator when function succeeds"""
        @log_exceptions("E54321")
        def test_function():
            return "success"
        
        with self.app.test_request_context('/test'):
            result = test_function()
            
        self.assertEqual(result, "success")
        mock_log.assert_not_called()
        mock_get_explanation.assert_not_called()

    @patch("error_handler.log_error_remote")
    @patch("error_handler.get_error_explanation")
    def test_log_exceptions_decorator_failure(self, mock_get_explanation, mock_log):
        """Test log_exceptions decorator when function raises exception"""
        mock_get_explanation.return_value = "Decorator error explanation"
        
        @log_exceptions("E54321")
        def test_function():
            raise ValueError("Function failed")
        
        with self.app.test_request_context('/test', method='PUT'):
            result = test_function()
            
        # Should log error and return JSON response
        mock_log.assert_called_once_with(
            "E54321",
            message="Decorator error explanation",
            exception="PUT /test | Function failed"
        )
        mock_get_explanation.assert_called_once_with("E54321")
        
        self.assertEqual(result[1], 500)  # Status code
        response_data = json.loads(result[0].get_data(as_text=True))
        self.assertEqual(response_data["error"], "Application Error")
        self.assertEqual(response_data["message"], "Decorator error explanation")
        self.assertEqual(response_data["code"], "E54321")

    @patch("error_handler.log_error_remote")
    def test_log_python_exception_keyboard_interrupt(self, mock_log):
        """Test log_python_exception ignores KeyboardInterrupt"""
        try:
            raise KeyboardInterrupt("User interrupted")
        except KeyboardInterrupt:
            exc_type, exc_value, exc_traceback = (
                KeyboardInterrupt,
                KeyboardInterrupt("User interrupted"),
                None
            )
            
            log_python_exception(exc_type, exc_value, exc_traceback)
            
        # Should not log KeyboardInterrupt
        mock_log.assert_not_called()

    @patch("error_handler.log_error_remote")
    def test_log_python_exception_regular_exception(self, mock_log):
        """Test log_python_exception with regular exceptions"""
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            log_python_exception(exc_type, exc_value, exc_traceback)
            
        # Should log the exception
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        self.assertEqual(args[0], "E00000")
        self.assertEqual(kwargs["message"], "Python exception occurred (standard)")
        self.assertIn("ValueError: Test error", kwargs["exception"])

    @patch("error_handler.log_error_remote")
    def test_log_react_exception(self, mock_log):
        """Test log_react_exception function"""
        error_info = "React error: Component failed to render"
        
        log_react_exception(error_info)
        
        mock_log.assert_called_once_with(
            "E00001",
            message="React exception occurred (standard)",
            exception=error_info
        )

    def test_error_handler_import_structure(self):
        """Test that all necessary imports are accessible"""
        # Verify error_handler module imports work correctly
        from error_handler import (
            get_error_explanation,
            flask_error_handler,
            log_exceptions,
            log_python_exception,
            log_react_exception
        )
        
        self.assertTrue(callable(get_error_explanation))
        self.assertTrue(callable(flask_error_handler))
        self.assertTrue(callable(log_exceptions))
        self.assertTrue(callable(log_python_exception))
        self.assertTrue(callable(log_react_exception))

    @patch("error_handler.log_error_remote")
    @patch("error_handler.get_error_explanation")
    def test_log_exceptions_preserves_metadata(self, mock_get_explanation, mock_log):
        """Test that log_exceptions decorator preserves function metadata"""
        @log_exceptions("E99999")
        def test_function_with_metadata():
            """Test function with docstring"""
            return "metadata_preserved"
        
        # Function metadata should be preserved
        self.assertEqual(test_function_with_metadata.__name__, "test_function_with_metadata")
        self.assertEqual(test_function_with_metadata.__doc__, "Test function with docstring")


if __name__ == "__main__":
    unittest.main()
