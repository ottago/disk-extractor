"""
Integration tests for API endpoints
"""

import unittest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import create_app
from models.metadata_manager import MovieMetadataManager


class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoint integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test app
        self.app = create_app(self.temp_dir)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create test files
        self.create_test_files()
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_files(self):
        """Create test .img files"""
        (self.temp_path / "movie1.img").write_bytes(b"fake content 1")
        (self.temp_path / "movie2.img").write_bytes(b"fake content 2")
        
        # Create metadata file
        metadata = {
            "file_name": "movie1.img",
            "size_mb": 1000.0,
            "titles": [
                {
                    "title_number": 1,
                    "selected": True,
                    "movie_name": "Test Movie",
                    "release_date": "2023-01-01",
                    "synopsis": "A test movie",
                    "duration_seconds": 7200,
                    "audio_tracks": [],
                    "subtitle_tracks": [],
                    "selected_audio_tracks": [],
                    "selected_subtitle_tracks": []
                }
            ]
        }
        
        (self.temp_path / "movie1.mmm").write_text(json.dumps(metadata, indent=2))
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('handbrake', data)
        self.assertIn('movie_count', data)
    
    def test_file_list_endpoint(self):
        """Test file list API endpoint"""
        response = self.client.get('/api/file_list')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('movies', data)
        self.assertEqual(len(data['movies']), 2)
    
    def test_save_metadata_endpoint(self):
        """Test save metadata API endpoint"""
        metadata = {
            "filename": "movie2.img",
            "file_name": "movie2.img",
            "titles": [
                {
                    "title_number": 1,
                    "movie_name": "Updated Movie",
                    "release_date": "2023-02-01"
                }
            ]
        }
        
        response = self.client.post('/api/save_metadata',
                                  json=metadata,
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    def test_save_metadata_invalid_data(self):
        """Test save metadata with invalid data"""
        response = self.client.post('/api/save_metadata',
                                  json={"invalid": "data"},
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    @patch('models.metadata_manager.HandBrakeScanner')
    def test_scan_file_endpoint(self, mock_scanner_class):
        """Test scan file API endpoint"""
        # Mock HandBrake scanner
        mock_scanner = Mock()
        mock_scanner.scan_file.return_value = {
            "titles": [{"title_number": 1, "duration_seconds": 7200}]
        }
        mock_scanner_class.return_value = mock_scanner
        
        response = self.client.get('/api/scan_file/movie1.img')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('metadata', data)
    
    def test_scan_file_nonexistent(self):
        """Test scanning non-existent file"""
        response = self.client.get('/api/scan_file/nonexistent.img')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    def test_enhanced_metadata_endpoint(self):
        """Test enhanced metadata API endpoint"""
        with patch('models.metadata_manager.HandBrakeScanner') as mock_scanner_class:
            mock_scanner = Mock()
            mock_scanner.scan_file.return_value = {
                "titles": [{"title_number": 1, "duration_seconds": 7200}]
            }
            mock_scanner_class.return_value = mock_scanner
            
            response = self.client.get('/api/enhanced_metadata/movie1.img')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(data['success'])
            self.assertIn('metadata', data)
    
    def test_raw_output_endpoint(self):
        """Test raw output API endpoint"""
        response = self.client.get('/api/raw_output/movie1.img')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        # Should return success=False since file hasn't been scanned
        self.assertFalse(data['success'])
    
    def test_handbrake_test_endpoint(self):
        """Test HandBrake test API endpoint"""
        with patch('models.metadata_manager.MovieMetadataManager.test_handbrake') as mock_test:
            mock_test.return_value = True
            
            response = self.client.get('/api/handbrake/test')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(data['available'])
    
    def test_encoding_status_endpoint(self):
        """Test encoding status API endpoint"""
        response = self.client.get('/api/encoding/status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('jobs', data)
        self.assertIn('summary', data)
    
    def test_encoding_queue_endpoint(self):
        """Test encoding queue API endpoint"""
        job_data = {
            "file_name": "movie1.img",
            "title_number": 1,
            "movie_name": "Test Movie",
            "output_filename": "Test Movie.mp4",
            "preset_name": "Fast 1080p30"
        }
        
        response = self.client.post('/api/encoding/queue',
                                  json=job_data,
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('job_id', data)
    
    def test_encoding_queue_invalid_data(self):
        """Test encoding queue with invalid data"""
        response = self.client.post('/api/encoding/queue',
                                  json={"invalid": "data"},
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_settings_get_endpoint(self):
        """Test get settings API endpoint"""
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('max_concurrent_encodes', data)
        self.assertIn('testing_mode', data)
    
    def test_settings_post_endpoint(self):
        """Test update settings API endpoint"""
        settings_data = {
            "max_concurrent_encodes": 2,
            "testing_mode": True,
            "output_directory": "/tmp/output"
        }
        
        response = self.client.post('/api/settings',
                                  json=settings_data,
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    def test_templates_list_endpoint(self):
        """Test list templates API endpoint"""
        response = self.client.get('/api/templates')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('templates', data)
        self.assertIsInstance(data['templates'], list)
    
    def test_directory_browse_endpoint(self):
        """Test directory browse API endpoint"""
        browse_data = {
            "path": str(self.temp_path.parent)
        }
        
        response = self.client.post('/api/directory/browse',
                                  json=browse_data,
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('directories', data)
    
    def test_path_traversal_protection(self):
        """Test path traversal protection"""
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32',
            'movie/../../../etc/passwd.img'
        ]
        
        for path in malicious_paths:
            with self.subTest(path=path):
                response = self.client.get(f'/api/scan_file/{path}')
                self.assertEqual(response.status_code, 400)
                
                data = json.loads(response.data)
                self.assertFalse(data['success'])
                self.assertIn('path traversal', data['error'].lower())
    
    def test_main_page_loads(self):
        """Test main page loads correctly"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Disk Extractor', response.data)
    
    def test_settings_page_loads(self):
        """Test settings page loads correctly"""
        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Settings', response.data)


if __name__ == '__main__':
    unittest.main()
