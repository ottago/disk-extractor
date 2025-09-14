"""
Unit tests for HandBrakeScanner
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.handbrake_scanner import HandBrakeScanner, HandBrakeError


class TestHandBrakeScanner(unittest.TestCase):
    """Test HandBrakeScanner functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.scanner = HandBrakeScanner()
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_file(self, filename: str) -> Path:
        """Create a test file"""
        file_path = self.temp_path / filename
        file_path.write_bytes(b"fake content")
        return file_path
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_scan_file_success(self, mock_run):
        """Test successful file scanning"""
        # Mock HandBrake output
        mock_output = """
        + title 1:
          + duration: 02:00:00
          + size: 1920x1080, pixel aspect: 1/1, display aspect: 1.78, 23.976 fps
          + audio tracks:
            + 1, English (AC3) (5.1 ch) (iso639-2: eng)
          + subtitle tracks:
            + 1, English (PGS) (iso639-2: eng)
        """
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_output.encode('utf-8'),  # Convert to bytes
            stderr=b""
        )
        
        test_file = self.create_test_file("test.img")
        result = self.scanner.scan_file(str(test_file))
        
        self.assertIn("titles", result)
        self.assertGreater(len(result["titles"]), 0)
        mock_run.assert_called_once()
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_scan_file_handbrake_error(self, mock_run):
        """Test HandBrake scan error"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="No valid source found"
        )
        
        test_file = self.create_test_file("test.img")
        
        with self.assertRaises(HandBrakeError):
            self.scanner.scan_file(str(test_file))
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_scan_file_timeout(self, mock_run):
        """Test HandBrake scan timeout"""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("HandBrakeCLI", 120)
        
        test_file = self.create_test_file("test.img")
        
        with self.assertRaises(HandBrakeError) as cm:
            self.scanner.scan_file(str(test_file))
        
        self.assertIn("timeout", str(cm.exception).lower())
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_scan_file_not_found(self, mock_run):
        """Test scanning non-existent file"""
        with self.assertRaises(HandBrakeError) as cm:
            self.scanner.scan_file("/nonexistent/file.img")
        
        self.assertIn("not found", str(cm.exception).lower())
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_scan_file_success(self, mock_run):
        """Test successful file scanning"""
        # Mock HandBrake output
        mock_output = """
        + title 1:
          + duration: 02:00:00
          + size: 1920x1080, pixel aspect: 1/1, display aspect: 1.78, 23.976 fps
          + audio tracks:
            + 1, English (AC3) (5.1 ch) (iso639-2: eng)
          + subtitle tracks:
            + 1, English (PGS) (iso639-2: eng)
        """
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_output.encode('utf-8'),  # Convert to bytes
            stderr=b""
        )
        
        test_file = self.create_test_file("test.img")
        result = self.scanner.scan_file(str(test_file))
        
        self.assertIn("titles", result)
        self.assertGreater(len(result["titles"]), 0)
        mock_run.assert_called_once()
    
    def test_scan_file_not_found(self):
        """Test scanning non-existent file"""
        with self.assertRaises(HandBrakeError) as cm:
            self.scanner.scan_file("/nonexistent/file.img")
        
        self.assertIn("not found", str(cm.exception).lower())
    
    def test_scan_file_with_valid_file(self):
        """Test scanning with a valid file path"""
        test_file = self.create_test_file("test.img")
        
        # This will fail due to HandBrake not being available, but tests file validation
        with self.assertRaises(HandBrakeError):
            self.scanner.scan_file(str(test_file))


if __name__ == '__main__':
    unittest.main()
