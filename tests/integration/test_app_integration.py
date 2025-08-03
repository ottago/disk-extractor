"""
Integration tests for the full Disk Extractor application
"""

import unittest
import sys
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.metadata_manager import MovieMetadataManager


class TestAppIntegration(unittest.TestCase):
    """Test full application integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test movies
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create some test .img files
        (self.test_dir / "movie1.img").touch()
        (self.test_dir / "movie2.img").touch()
        (self.test_dir / "test_movie.img").touch()
        
        # Create test metadata file with proper JSON
        metadata_content = {
            "file_name": "movie1.img",
            "movie_name": "Test Movie 1",
            "release_date": "2023-01-01",
            "synopsis": "A test movie",
            "titles": []
        }
        (self.test_dir / "movie1.mmm").write_text(json.dumps(metadata_content, indent=2))
        
        # Mock HandBrake CLI to avoid dependency
        self.handbrake_patcher = patch('config.Path.exists')
        self.mock_handbrake_exists = self.handbrake_patcher.start()
        self.mock_handbrake_exists.return_value = True
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
        
        # Stop patches
        self.handbrake_patcher.stop()
    
    def test_movie_discovery(self):
        """Test movies are discovered correctly"""
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Should find 3 .img files
        self.assertEqual(len(manager.movies), 3)
        
        # Check movie names
        movie_names = [movie['file_name'] for movie in manager.movies]
        self.assertIn('movie1.img', movie_names)
        self.assertIn('movie2.img', movie_names)
        self.assertIn('test_movie.img', movie_names)
    
    def test_metadata_loading(self):
        """Test metadata loading works correctly"""
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Find movie1 which has metadata
        movie1 = next(movie for movie in manager.movies if movie['file_name'] == 'movie1.img')
        
        # Should have metadata loaded (check the actual metadata content)
        # The has_meaningful_metadata checks for selected titles with movie names
        # Our test metadata doesn't have selected titles, so let's check the loaded data instead
        metadata = manager.load_metadata('movie1.img')
        self.assertEqual(metadata['file_name'], 'movie1.img')
        self.assertEqual(metadata.get('movie_name'), 'Test Movie 1')
        self.assertEqual(metadata.get('release_date'), '2023-01-01')
        self.assertEqual(metadata.get('synopsis'), 'A test movie')
    
    @patch('models.handbrake_scanner.HandBrakeScanner.test_availability')
    def test_handbrake_integration(self, mock_handbrake_test):
        """Test HandBrake integration works"""
        mock_handbrake_test.return_value = True
        
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Test HandBrake availability
        available = manager.test_handbrake()
        self.assertTrue(available)
        
        # Test cache stats
        stats = manager.get_cache_stats()
        self.assertIn('size', stats)
        self.assertIn('max_size', stats)
        self.assertIn('ttl', stats)
    
    def test_validation_integration(self):
        """Test validation works in full workflow"""
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Test valid filename validation
        from utils.validation import validate_filename
        valid_name = validate_filename('test.img')
        self.assertEqual(valid_name, 'test.img')
        
        # Test invalid filename validation
        from utils.validation import ValidationError
        with self.assertRaises(ValidationError):
            validate_filename('../../../etc/passwd')
    
    def test_security_utilities(self):
        """Test security utilities work correctly"""
        from utils.security import check_path_traversal, safe_decode_subprocess_output
        
        # Test path traversal detection
        self.assertTrue(check_path_traversal('/api/scan_file/../../../etc/passwd'))
        self.assertFalse(check_path_traversal('/api/scan_file/movie.img'))
        
        # Test safe decoding
        result = safe_decode_subprocess_output(b'Hello World')
        self.assertEqual(result, 'Hello World')
    
    def test_language_mapping_integration(self):
        """Test language mapping works in context"""
        from utils.language_mapper import LanguageMapper
        
        # Test common language codes
        self.assertEqual(LanguageMapper.get_language_name('eng'), 'English')
        self.assertEqual(LanguageMapper.get_language_name('spa'), 'Spanish')
        
        # Test English detection
        self.assertTrue(LanguageMapper.is_english('eng'))
        self.assertFalse(LanguageMapper.is_english('spa'))


class TestMetadataManagerIntegration(unittest.TestCase):
    """Test metadata manager integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        (self.test_dir / "test.img").touch()
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir)
    
    def test_metadata_save_and_load_cycle(self):
        """Test complete metadata save and load cycle"""
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Create test metadata
        test_metadata = {
            'filename': 'test.img',
            'file_name': 'test.img',
            'movie_name': 'Integration Test Movie',
            'release_date': '2023-12-01',
            'synopsis': 'A movie for integration testing',
            'titles': []
        }
        
        # Save metadata
        success = manager.save_metadata('test.img', test_metadata)
        self.assertTrue(success)
        
        # Verify .mmm file was created
        mmm_file = self.test_dir / 'test.mmm'
        self.assertTrue(mmm_file.exists())
        
        # Load metadata back
        loaded_metadata = manager.load_metadata('test.img')
        self.assertEqual(loaded_metadata['movie_name'], 'Integration Test Movie')
        self.assertEqual(loaded_metadata['release_date'], '2023-12-01')
        self.assertEqual(loaded_metadata['synopsis'], 'A movie for integration testing')
    
    def test_directory_scanning(self):
        """Test directory scanning finds all files"""
        # Create multiple test files
        (self.test_dir / "movie_a.img").touch()
        (self.test_dir / "movie_b.img").touch()
        (self.test_dir / "movie_c.img").touch()
        
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Should find all 4 files (including test.img from setUp)
        self.assertEqual(len(manager.movies), 4)
        
        # Files should be sorted by name
        filenames = [movie['file_name'] for movie in manager.movies]
        self.assertEqual(filenames, sorted(filenames))
    
    def test_cache_functionality(self):
        """Test caching functionality works"""
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Test cache is initially empty
        stats = manager.get_cache_stats()
        self.assertEqual(stats['size'], 0)
        
        # Test cache clearing
        manager.clear_cache()
        stats = manager.get_cache_stats()
        self.assertEqual(stats['size'], 0)
    
    def test_file_size_calculation(self):
        """Test file size calculation works"""
        # Write enough data to ensure non-zero MB calculation (1MB = 1024*1024 bytes)
        test_data = "x" * (1024 * 1024 + 1000)  # Just over 1MB of data
        (self.test_dir / "size_test.img").write_text(test_data)
        
        manager = MovieMetadataManager(str(self.test_dir))
        
        # Find the size test file
        size_test_movie = next(
            movie for movie in manager.movies 
            if movie['file_name'] == 'size_test.img'
        )
        
        # Should have calculated size (should be >= 1 MB for our test file)
        self.assertIsNotNone(size_test_movie['size_mb'])
        self.assertGreaterEqual(size_test_movie['size_mb'], 1.0)  # Should be >= 1 MB


class TestConfigurationIntegration(unittest.TestCase):
    """Test configuration integration"""
    
    def test_config_validation_integration(self):
        """Test configuration validation works in practice"""
        from config import Config
        
        # Test that configuration has expected values
        self.assertIsInstance(Config.HANDBRAKE_TIMEOUT, int)
        self.assertGreater(Config.HANDBRAKE_TIMEOUT, 0)
        
        self.assertIsInstance(Config.MAX_CACHE_SIZE, int)
        self.assertGreater(Config.MAX_CACHE_SIZE, 0)
        
        self.assertIn('.img', Config.ALLOWED_EXTENSIONS)
    
    def test_security_headers_configuration(self):
        """Test security headers are properly configured"""
        from config import SECURITY_HEADERS, API_CACHE_HEADERS
        
        # Test security headers
        self.assertIn('X-Content-Type-Options', SECURITY_HEADERS)
        self.assertIn('X-Frame-Options', SECURITY_HEADERS)
        self.assertIn('Content-Security-Policy', SECURITY_HEADERS)
        
        # Test API cache headers
        self.assertIn('Cache-Control', API_CACHE_HEADERS)
        self.assertIn('Pragma', API_CACHE_HEADERS)


if __name__ == '__main__':
    unittest.main()
