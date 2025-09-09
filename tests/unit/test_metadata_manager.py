"""
Unit tests for MovieMetadataManager
"""

import unittest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.metadata_manager import MovieMetadataManager, MetadataError
from models.encoding_models import EncodingStatus


class TestMovieMetadataManager(unittest.TestCase):
    """Test MovieMetadataManager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.manager = MovieMetadataManager()
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_img_file(self, filename: str) -> Path:
        """Create a test .img file"""
        file_path = self.temp_path / filename
        file_path.write_bytes(b"fake img content")
        return file_path
    
    def create_test_metadata_file(self, filename: str, metadata: dict) -> Path:
        """Create a test .mmm metadata file"""
        metadata_path = self.temp_path / f"{Path(filename).stem}.mmm"
        metadata_path.write_text(json.dumps(metadata, indent=2))
        return metadata_path
    
    def test_set_directory_valid(self):
        """Test setting a valid directory"""
        self.manager.set_directory(self.temp_dir)
        self.assertEqual(self.manager.directory, self.temp_path)
    
    def test_set_directory_invalid(self):
        """Test setting an invalid directory"""
        with self.assertRaises(MetadataError):
            self.manager.set_directory("/nonexistent/directory")
    
    def test_scan_directory_empty(self):
        """Test scanning an empty directory"""
        self.manager.set_directory(self.temp_dir)
        self.manager.scan_directory()
        self.assertEqual(len(self.manager.movies), 0)
    
    def test_scan_directory_with_img_files(self):
        """Test scanning directory with .img files"""
        # Create test files
        self.create_test_img_file("movie1.img")
        self.create_test_img_file("movie2.img")
        
        self.manager.set_directory(self.temp_dir)
        self.manager.scan_directory()
        
        self.assertEqual(len(self.manager.movies), 2)
        filenames = [movie['file_name'] for movie in self.manager.movies]
        self.assertIn("movie1.img", filenames)
        self.assertIn("movie2.img", filenames)
    
    def test_load_metadata_existing(self):
        """Test loading existing metadata"""
        metadata = {
            "file_name": "test.img",
            "titles": [{"title_number": 1, "movie_name": "Test Movie"}]
        }
        
        self.create_test_img_file("test.img")
        self.create_test_metadata_file("test.img", metadata)
        self.manager.set_directory(self.temp_dir)
        
        loaded = self.manager.load_metadata("test.img")
        self.assertEqual(loaded["file_name"], "test.img")
        self.assertEqual(len(loaded["titles"]), 1)
    
    def test_load_metadata_nonexistent(self):
        """Test loading non-existent metadata"""
        self.manager.set_directory(self.temp_dir)
        
        # Should raise FileNotFoundError for non-existent file
        with self.assertRaises(FileNotFoundError):
            self.manager.load_metadata("nonexistent.img")
    
    def test_save_metadata(self):
        """Test saving metadata"""
        metadata = {
            "file_name": "test.img",
            "titles": [{"title_number": 1, "movie_name": "Test Movie"}]
        }
        
        self.create_test_img_file("test.img")
        self.manager.set_directory(self.temp_dir)
        
        success = self.manager.save_metadata("test.img", metadata)
        self.assertTrue(success)
        
        # Verify file was created
        metadata_file = self.temp_path / "test.mmm"
        self.assertTrue(metadata_file.exists())
        
        # Verify content
        loaded = json.loads(metadata_file.read_text())
        self.assertEqual(loaded["file_name"], "test.img")
    
    @patch('models.metadata_manager.HandBrakeScanner')
    def test_get_enhanced_metadata(self, mock_scanner_class):
        """Test getting enhanced metadata with HandBrake scan"""
        # Mock HandBrake scanner
        mock_scanner = Mock()
        mock_scanner.scan_file.return_value = {
            "titles": [{"title_number": 1, "duration_seconds": 7200}]
        }
        mock_scanner_class.return_value = mock_scanner
        
        self.create_test_img_file("test.img")
        self.manager.set_directory(self.temp_dir)
        
        enhanced = self.manager.get_enhanced_metadata("test.img")
        
        self.assertIn("titles", enhanced)
        self.assertEqual(len(enhanced["titles"]), 1)
        mock_scanner.scan_file.assert_called_once()
    
    def test_has_metadata_true(self):
        """Test has_metadata returns True for files with metadata"""
        metadata = {"file_name": "test.img", "titles": []}
        
        self.create_test_img_file("test.img")
        self.create_test_metadata_file("test.img", metadata)
        self.manager.set_directory(self.temp_dir)
        
        # Check if metadata file exists
        metadata_file = self.temp_path / "test.mmm"
        self.assertTrue(metadata_file.exists())
    
    def test_has_metadata_false(self):
        """Test has_metadata returns False for files without metadata"""
        self.create_test_img_file("test.img")
        self.manager.set_directory(self.temp_dir)
        
        # Check if metadata file doesn't exist
        metadata_file = self.temp_path / "test.mmm"
        self.assertFalse(metadata_file.exists())
    
    def test_get_cache_stats(self):
        """Test cache statistics"""
        self.manager.set_directory(self.temp_dir)
        stats = self.manager.get_cache_stats()
        
        self.assertIn("size", stats)
        self.assertIn("max_size", stats)
        self.assertIn("ttl", stats)
        self.assertIsInstance(stats["size"], int)
    
    @patch('models.metadata_manager.subprocess.run')
    def test_handbrake_available(self, mock_run):
        """Test HandBrake availability check"""
        mock_run.return_value = Mock(returncode=0)
        
        available = self.manager.test_handbrake()
        self.assertTrue(available)
        mock_run.assert_called_once()
    
    @patch('models.metadata_manager.subprocess.run')
    def test_handbrake_unavailable(self, mock_run):
        """Test HandBrake unavailable"""
        mock_run.side_effect = FileNotFoundError()
        
        available = self.manager.test_handbrake()
        self.assertFalse(available)


if __name__ == '__main__':
    unittest.main()
