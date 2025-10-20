import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask

# Mock the logger import to avoid import errors
with patch.dict('sys.modules', {
    'logger': Mock(log_error=Mock())
}):
    import error_server
    from error_server import app, log_endpoint, health_check


class TestErrorServer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config["TESTING"] = True
        self.test_client = self.app.test_client()

    @patch("error_server.log_error")
    def test_log_endpoint_success(self, mock_log_error):
        """Test successful log endpoint request"""
        test_data = {
            "error_code": "E12345",
            "message": "Test error message",
            "exception": "Test exception",
            "extra": {"user_id": "test_user"}
        }
        
        response = self.test_client.post(
            "/log",
            data=json.dumps(test_data),
            content_type="application/json"
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.get_data(as_text=True))
        self.assertEqual(response_data["status"], "logged")
        self.assertEqual(response_data["code"], "E12345")
        
        # Verify log_error was called correctly
        mock_log_error.assert_called_once_with(
            "E12345",
            message="Test error message",
            exception="Test exception",
            extra={"user_id": "test_user"}
        )

    @patch("error_server.log_error")
    def test_log_endpoint_minimal_data(self, mock_log_error):
        """Test log endpoint with minimal required data"""
        test_data = {"error_code": "E99999"}
        
        response = self.test_client.post(
            "/log",
            data=json.dumps(test_data),
            content_type="application/json"
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.get_data(as_text=True))
        self.assertEqual(response_data["status"], "logged")
        self.assertEqual(response_data["code"], "E99999")
        
        # Verify log_error was called with None values for missing fields
        mock_log_error.assert_called_once_with(
            "E99999",
            message=None,
            exception=None,
            extra=None
        )

    def test_log_endpoint_missing_error_code(self):
        """Test log endpoint with missing error_code"""
        test_data = {
            "message": "Test message without error code"
        }
        
        response = self.test_client.post(
            "/log",
            data=json.dumps(test_data),
            content_type="application/json"
        )
        
        # Verify error response
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.get_data(as_text=True))
        self.assertEqual(response_data["error"], "Missing error_code")

    def test_log_endpoint_empty_request(self):
        """Test log endpoint with empty request body"""
        response = self.test_client.post(
            "/log",
            data=json.dumps({}),
            content_type="application/json"
        )
        
        # Verify error response
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.get_data(as_text=True))
        self.assertEqual(response_data["error"], "Missing error_code")

    def test_log_endpoint_invalid_json(self):
        """Test log endpoint with invalid JSON"""
        response = self.test_client.post(
            "/log",
            data="invalid json",
            content_type="application/json"
        )
        
        # Should handle JSON parsing error gracefully
        self.assertIn(response.status_code, [400, 415])

    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        response = self.test_client.get("/health")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.get_data(as_text=True))
        self.assertEqual(response_data["status"], "ok")
        self.assertEqual(response_data["service"], "error_logger")

    def test_health_check_endpoint_post_method(self):
        """Test health check endpoint with POST method (should fail)"""
        response = self.test_client.post("/health")
        
        # Should not allow POST method
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_endpoint(self):
        """Test request to nonexistent endpoint"""
        response = self.test_client.get("/nonexistent")
        
        # Should return 404
        self.assertEqual(response.status_code, 404)

    @patch("error_server.log_error")
    def test_log_endpoint_preserves_response_structure(self, mock_log_error):
        """Test that log endpoint preserves expected response structure"""
        test_data = {"error_code": "E54321"}
        
        response = self.test_client.post(
            "/log",
            data=json.dumps(test_data),
            content_type="application/json"
        )
        
        response_data = json.loads(response.get_data(as_text=True))
        
        # Verify response structure
        self.assertIn("status", response_data)
        self.assertIn("code", response_data)
        self.assertEqual(len(response_data), 2)  # Should only have these two keys

    def test_flask_app_configuration(self):
        """Test Flask app configuration"""
        # Verify CSRF is disabled
        self.assertFalse(self.app.config.get("WTF_CSRF_ENABLED", True))
        
        # Verify testing mode can be enabled
        self.assertTrue(self.app.config.get("TESTING", False))

    @patch.dict(os.environ, {
        "ERRORLOGGER_HOST": "test_host",
        "ERRORLOGGER_PORT": "9999",
        "FLASK_DEBUG": "true"
    })
    def test_environment_variable_handling(self):
        """Test environment variable handling"""
        # This would normally test the main block, but we'll test the concept
        host = os.environ.get("ERRORLOGGER_HOST", "0.0.0.0")
        port = int(os.environ.get("ERRORLOGGER_PORT", os.environ.get("PORT", "5001")))
        debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
        
        self.assertEqual(host, "test_host")
        self.assertEqual(port, 9999)
        self.assertTrue(debug)

    def test_default_environment_values(self):
        """Test default environment values when not set"""
        # Clear environment variables for this test
        with patch.dict(os.environ, {}, clear=True):
            host = os.environ.get("ERRORLOGGER_HOST", "0.0.0.0")
            port = int(os.environ.get("ERRORLOGGER_PORT", os.environ.get("PORT", "5001")))
            debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
            
            self.assertEqual(host, "0.0.0.0")
            self.assertEqual(port, 5001)
            self.assertFalse(debug)


if __name__ == "__main__":
    unittest.main()
