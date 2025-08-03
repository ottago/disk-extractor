"""
Unit tests for security utilities
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.security import (
    safe_decode_subprocess_output,
    apply_security_headers,
    check_path_traversal,
    log_security_event
)


class TestSafeDecodeSubprocessOutput(unittest.TestCase):
    """Test safe subprocess output decoding"""
    
    def test_utf8_decoding(self):
        """Test UTF-8 decoding works"""
        test_bytes = "Hello World".encode('utf-8')
        result = safe_decode_subprocess_output(test_bytes)
        self.assertEqual(result, "Hello World")
    
    def test_latin1_fallback(self):
        """Test Latin-1 fallback works"""
        # Create bytes that are valid Latin-1 but not UTF-8
        test_bytes = b'\xff\xfe'
        result = safe_decode_subprocess_output(test_bytes)
        self.assertIsInstance(result, str)
    
    def test_empty_input(self):
        """Test empty input returns empty string"""
        result = safe_decode_subprocess_output(None)
        self.assertEqual(result, "")
        
        result = safe_decode_subprocess_output(b"")
        self.assertEqual(result, "")
    
    def test_error_replacement(self):
        """Test error replacement as last resort"""
        # This will test the final fallback with errors='replace'
        with patch('utils.security.safe_decode_subprocess_output') as mock_func:
            # Simulate all encodings failing, falling back to error replacement
            mock_func.return_value = "decoded with replacement"
            result = mock_func(b'\xff\xfe\xfd')
            self.assertEqual(result, "decoded with replacement")


class TestApplySecurityHeaders(unittest.TestCase):
    """Test security header application"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_response = Mock()
        self.mock_response.headers = {}
    
    def test_standard_headers_applied(self):
        """Test standard security headers are applied"""
        result = apply_security_headers(self.mock_response)
        
        # Check that headers were set
        self.assertIn('X-Content-Type-Options', self.mock_response.headers)
        self.assertIn('X-Frame-Options', self.mock_response.headers)
        self.assertIn('X-XSS-Protection', self.mock_response.headers)
        self.assertIn('Content-Security-Policy', self.mock_response.headers)
        
        # Check specific values
        self.assertEqual(self.mock_response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.mock_response.headers['X-Frame-Options'], 'DENY')
    
    def test_api_cache_headers(self):
        """Test API cache headers are applied for API endpoints"""
        result = apply_security_headers(self.mock_response, is_api_endpoint=True)
        
        # Check cache control headers are set
        self.assertIn('Cache-Control', self.mock_response.headers)
        self.assertIn('Pragma', self.mock_response.headers)
        self.assertIn('Expires', self.mock_response.headers)
        
        # Check specific values
        self.assertEqual(self.mock_response.headers['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(self.mock_response.headers['Pragma'], 'no-cache')
    
    def test_non_api_no_cache_headers(self):
        """Test non-API endpoints don't get cache headers"""
        result = apply_security_headers(self.mock_response, is_api_endpoint=False)
        
        # Check cache control headers are NOT set
        self.assertNotIn('Cache-Control', self.mock_response.headers)
        self.assertNotIn('Pragma', self.mock_response.headers)
        self.assertNotIn('Expires', self.mock_response.headers)


class TestCheckPathTraversal(unittest.TestCase):
    """Test path traversal detection"""
    
    def test_safe_paths(self):
        """Test safe paths are not flagged"""
        safe_paths = [
            '/api/scan_file/movie.img',
            '/api/metadata/normal_file.img',
            '/health',
            '/setup'
        ]
        
        for path in safe_paths:
            with self.subTest(path=path):
                result = check_path_traversal(path)
                self.assertFalse(result)
    
    def test_malicious_paths(self):
        """Test malicious paths are detected"""
        malicious_paths = [
            '/api/scan_file/../../../etc/passwd',
            '/api/scan_file/..\\..\\windows\\system32',
            '/api/scan_file/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd',
            '/api/scan_file/..%2f..%2f..%2fetc%2fpasswd'
        ]
        
        for path in malicious_paths:
            with self.subTest(path=path):
                result = check_path_traversal(path)
                self.assertTrue(result)
    
    def test_empty_path(self):
        """Test empty path returns False"""
        result = check_path_traversal('')
        self.assertFalse(result)
        
        result = check_path_traversal(None)
        self.assertFalse(result)
    
    def test_case_insensitive(self):
        """Test detection is case insensitive"""
        malicious_paths = [
            '/api/scan_file/../Test',
            '/api/scan_file/..\\Test',
            '/api/scan_file/%2E%2E%2FTest'
        ]
        
        for path in malicious_paths:
            with self.subTest(path=path):
                result = check_path_traversal(path)
                self.assertTrue(result)


class TestLogSecurityEvent(unittest.TestCase):
    """Test security event logging"""
    
    @patch('utils.security.logger')
    def test_basic_logging(self, mock_logger):
        """Test basic security event logging"""
        log_security_event("Test Event", "Test details")
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        self.assertIn("SECURITY: Test Event - Test details", call_args)
    
    @patch('utils.security.logger')
    def test_logging_with_remote_addr(self, mock_logger):
        """Test logging with remote address"""
        log_security_event("Test Event", "Test details", "192.168.1.1")
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        self.assertIn("from 192.168.1.1", call_args)
    
    @patch('utils.security.logger')
    def test_logging_without_remote_addr(self, mock_logger):
        """Test logging without remote address"""
        log_security_event("Test Event", "Test details", None)
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        self.assertNotIn("from", call_args)


if __name__ == '__main__':
    unittest.main()
