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
            stdout=mock_output,
            stderr=""
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
    
    def test_parse_duration(self):
        """Test duration parsing"""
        # Test various duration formats
        test_cases = [
            ("02:30:45", 9045),  # 2h 30m 45s
            ("01:15:30", 4530),  # 1h 15m 30s
            ("00:45:00", 2700),  # 45m
            ("00:05:30", 330),   # 5m 30s
        ]
        
        for duration_str, expected_seconds in test_cases:
            with self.subTest(duration=duration_str):
                seconds = self.scanner._parse_duration(duration_str)
                self.assertEqual(seconds, expected_seconds)
    
    def test_parse_duration_invalid(self):
        """Test parsing invalid duration"""
        invalid_durations = [
            "invalid",
            "25:70:80",  # Invalid minutes/seconds
            "",
            "1:2"  # Too few components
        ]
        
        for duration_str in invalid_durations:
            with self.subTest(duration=duration_str):
                seconds = self.scanner._parse_duration(duration_str)
                self.assertEqual(seconds, 0)
    
    def test_parse_audio_track(self):
        """Test audio track parsing"""
        audio_line = "+ 1, English (AC3) (5.1 ch) (iso639-2: eng)"
        
        track = self.scanner._parse_audio_track(audio_line)
        
        self.assertEqual(track["track_number"], 1)
        self.assertEqual(track["language"], "English")
        self.assertEqual(track["codec"], "AC3")
        self.assertEqual(track["channels"], "5.1 ch")
    
    def test_parse_subtitle_track(self):
        """Test subtitle track parsing"""
        subtitle_line = "+ 1, English (PGS) (iso639-2: eng)"
        
        track = self.scanner._parse_subtitle_track(subtitle_line)
        
        self.assertEqual(track["track_number"], 1)
        self.assertEqual(track["language"], "English")
        self.assertEqual(track["format"], "PGS")
    
    def test_parse_video_info(self):
        """Test video information parsing"""
        video_line = "+ size: 1920x1080, pixel aspect: 1/1, display aspect: 1.78, 23.976 fps"
        
        info = self.scanner._parse_video_info(video_line)
        
        self.assertEqual(info["width"], 1920)
        self.assertEqual(info["height"], 1080)
        self.assertEqual(info["fps"], 23.976)
        self.assertEqual(info["aspect_ratio"], "1.78")
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_test_handbrake_available(self, mock_run):
        """Test HandBrake availability check"""
        mock_run.return_value = Mock(returncode=0)
        
        available = self.scanner.test_handbrake()
        self.assertTrue(available)
    
    @patch('models.handbrake_scanner.subprocess.run')
    def test_test_handbrake_unavailable(self, mock_run):
        """Test HandBrake unavailable"""
        mock_run.side_effect = FileNotFoundError()
        
        available = self.scanner.test_handbrake()
        self.assertFalse(available)
    
    def test_get_handbrake_version(self):
        """Test getting HandBrake version"""
        with patch('models.handbrake_scanner.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="HandBrake 1.6.1"
            )
            
            version = self.scanner.get_handbrake_version()
            self.assertEqual(version, "HandBrake 1.6.1")
    
    def test_validate_file_path(self):
        """Test file path validation"""
        # Valid file
        test_file = self.create_test_file("test.img")
        self.assertTrue(self.scanner._validate_file_path(str(test_file)))
        
        # Non-existent file
        self.assertFalse(self.scanner._validate_file_path("/nonexistent/file.img"))
        
        # Directory instead of file
        self.assertFalse(self.scanner._validate_file_path(str(self.temp_path)))


if __name__ == '__main__':
    unittest.main()
