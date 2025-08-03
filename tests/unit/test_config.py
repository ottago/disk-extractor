"""
Unit tests for configuration management
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import Config, SECURITY_HEADERS, API_CACHE_HEADERS


class TestConfig(unittest.TestCase):
    """Test configuration management"""
    
    def test_default_values(self):
        """Test default configuration values"""
        # Test numeric defaults
        self.assertIsInstance(Config.HANDBRAKE_TIMEOUT, int)
        self.assertGreater(Config.HANDBRAKE_TIMEOUT, 0)
        
        self.assertIsInstance(Config.MAX_CACHE_SIZE, int)
        self.assertGreater(Config.MAX_CACHE_SIZE, 0)
        
        self.assertIsInstance(Config.CACHE_TTL, int)
        self.assertGreater(Config.CACHE_TTL, 0)
        
        # Test string defaults
        self.assertIsInstance(Config.HOST, str)
        self.assertIsInstance(Config.LOG_LEVEL, str)
        
        # Test boolean defaults
        self.assertIsInstance(Config.DEBUG, bool)
        
        # Test list defaults
        self.assertIsInstance(Config.ALLOWED_EXTENSIONS, list)
        self.assertIn('.img', Config.ALLOWED_EXTENSIONS)
    
    @patch.dict(os.environ, {'HANDBRAKE_TIMEOUT': '300'})
    def test_environment_variable_override(self):
        """Test environment variables override defaults"""
        # Need to reload the module to pick up env changes
        import importlib
        import config
        importlib.reload(config)
        
        self.assertEqual(config.Config.HANDBRAKE_TIMEOUT, 300)
    
    @patch.dict(os.environ, {'FLASK_DEBUG': 'true'})
    def test_boolean_environment_variables(self):
        """Test boolean environment variable parsing"""
        import importlib
        import config
        importlib.reload(config)
        
        self.assertTrue(config.Config.DEBUG)
    
    def test_handbrake_path_detection(self):
        """Test HandBrake CLI path detection"""
        # The path should be set to one of the expected locations
        expected_paths = ['/usr/local/bin/HandBrakeCLI', '/usr/bin/HandBrakeCLI']
        self.assertIn(Config.HANDBRAKE_CLI_PATH, expected_paths)
    
    def test_security_constants(self):
        """Test security-related constants"""
        # Test filename length limits
        self.assertIsInstance(Config.MAX_FILENAME_LENGTH, int)
        self.assertGreater(Config.MAX_FILENAME_LENGTH, 0)
        
        # Test synopsis length limits
        self.assertIsInstance(Config.MAX_SYNOPSIS_LENGTH, int)
        self.assertGreater(Config.MAX_SYNOPSIS_LENGTH, 0)
        
        # Test allowed characters
        self.assertIsInstance(Config.ALLOWED_FILENAME_CHARS, str)
        self.assertIn('a', Config.ALLOWED_FILENAME_CHARS)
        self.assertIn('A', Config.ALLOWED_FILENAME_CHARS)
        self.assertIn('0', Config.ALLOWED_FILENAME_CHARS)
    
    def test_title_suggestion_settings(self):
        """Test title suggestion configuration"""
        self.assertIsInstance(Config.MIN_TITLE_DURATION_MINUTES, int)
        self.assertGreaterEqual(Config.MIN_TITLE_DURATION_MINUTES, 0)
        
        self.assertIsInstance(Config.MIN_COLLAPSED_DURATION_SECONDS, int)
        self.assertGreaterEqual(Config.MIN_COLLAPSED_DURATION_SECONDS, 0)
    
    @patch('config.Path.exists')
    def test_validate_success(self, mock_exists):
        """Test successful configuration validation"""
        mock_exists.return_value = True
        
        # Should not raise an exception
        result = Config.validate()
        self.assertTrue(result)
    
    @patch('config.Path.exists')
    def test_validate_missing_handbrake(self, mock_exists):
        """Test validation fails when HandBrake is missing"""
        mock_exists.return_value = False
        
        with self.assertRaises(ValueError) as cm:
            Config.validate()
        self.assertIn('HandBrake CLI not found', str(cm.exception))
    
    def test_validate_invalid_timeout(self):
        """Test validation fails with invalid timeout"""
        original_timeout = Config.HANDBRAKE_TIMEOUT
        try:
            Config.HANDBRAKE_TIMEOUT = -1
            with self.assertRaises(ValueError) as cm:
                Config.validate()
            self.assertIn('HANDBRAKE_TIMEOUT must be positive', str(cm.exception))
        finally:
            Config.HANDBRAKE_TIMEOUT = original_timeout
    
    def test_validate_invalid_cache_size(self):
        """Test validation fails with invalid cache size"""
        original_cache_size = Config.MAX_CACHE_SIZE
        try:
            Config.MAX_CACHE_SIZE = 0
            with self.assertRaises(ValueError) as cm:
                Config.validate()
            self.assertIn('MAX_CACHE_SIZE must be positive', str(cm.exception))
        finally:
            Config.MAX_CACHE_SIZE = original_cache_size


class TestSecurityHeaders(unittest.TestCase):
    """Test security header configurations"""
    
    def test_security_headers_structure(self):
        """Test security headers have correct structure"""
        self.assertIsInstance(SECURITY_HEADERS, dict)
        
        # Check required headers are present
        required_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options', 
            'X-XSS-Protection',
            'Content-Security-Policy'
        ]
        
        for header in required_headers:
            with self.subTest(header=header):
                self.assertIn(header, SECURITY_HEADERS)
                self.assertIsInstance(SECURITY_HEADERS[header], str)
                self.assertTrue(len(SECURITY_HEADERS[header]) > 0)
    
    def test_security_header_values(self):
        """Test security header values are correct"""
        self.assertEqual(SECURITY_HEADERS['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(SECURITY_HEADERS['X-Frame-Options'], 'DENY')
        self.assertEqual(SECURITY_HEADERS['X-XSS-Protection'], '1; mode=block')
        
        # CSP should contain expected directives
        csp = SECURITY_HEADERS['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
    
    def test_api_cache_headers_structure(self):
        """Test API cache headers have correct structure"""
        self.assertIsInstance(API_CACHE_HEADERS, dict)
        
        # Check required headers are present
        required_headers = ['Cache-Control', 'Pragma', 'Expires']
        
        for header in required_headers:
            with self.subTest(header=header):
                self.assertIn(header, API_CACHE_HEADERS)
                self.assertIsInstance(API_CACHE_HEADERS[header], str)
                self.assertTrue(len(API_CACHE_HEADERS[header]) > 0)
    
    def test_api_cache_header_values(self):
        """Test API cache header values prevent caching"""
        self.assertEqual(API_CACHE_HEADERS['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(API_CACHE_HEADERS['Pragma'], 'no-cache')
        self.assertEqual(API_CACHE_HEADERS['Expires'], '0')


if __name__ == '__main__':
    unittest.main()
