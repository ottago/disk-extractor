"""
End-to-end integration tests
"""

import unittest
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import create_app
from tests.test_config import TestEnvironment, create_sample_metadata, create_mock_handbrake_scanner


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_env = TestEnvironment()
        self.temp_path = self.test_env.setup()
        
        # Create test app
        self.app = create_app(str(self.temp_path))
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create test files
        self.setup_test_data()
    
    def tearDown(self):
        """Clean up test environment"""
        self.test_env.teardown()
    
    def setup_test_data(self):
        """Set up test data"""
        # Create test .img files
        self.test_env.create_test_file("movie1.img", 1024 * 1024)  # 1MB
        self.test_env.create_test_file("movie2.img", 2 * 1024 * 1024)  # 2MB
        
        # Create metadata for movie1
        metadata = create_sample_metadata("movie1.img")
        self.test_env.create_test_metadata("movie1.img", metadata)
    
    def test_complete_workflow(self):
        """Test complete workflow from file discovery to encoding"""
        
        # 1. Check health endpoint
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        health_data = json.loads(response.data)
        self.assertEqual(health_data['status'], 'ok')
        
        # 2. Get file list
        response = self.client.get('/api/file_list')
        self.assertEqual(response.status_code, 200)
        file_data = json.loads(response.data)
        self.assertEqual(len(file_data['movies']), 2)
        
        # 3. Scan a file (mock HandBrake)
        with patch('models.metadata_manager.HandBrakeScanner') as mock_scanner_class:
            mock_scanner_class.return_value = create_mock_handbrake_scanner()
            
            response = self.client.get('/api/scan_file/movie2.img')
            self.assertEqual(response.status_code, 200)
            scan_data = json.loads(response.data)
            self.assertTrue(scan_data['success'])
        
        # 4. Save metadata
        metadata = {
            "filename": "movie2.img",
            "file_name": "movie2.img",
            "titles": [
                {
                    "title_number": 1,
                    "movie_name": "Test Movie 2",
                    "release_date": "2023-02-01",
                    "synopsis": "Second test movie",
                    "selected": True,
                    "selected_audio_tracks": [1],
                    "selected_subtitle_tracks": []
                }
            ]
        }
        
        response = self.client.post('/api/save_metadata',
                                  json=metadata,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        save_data = json.loads(response.data)
        self.assertTrue(save_data['success'])
        
        # 5. Queue encoding job
        job_data = {
            "file_name": "movie2.img",
            "title_number": 1,
            "movie_name": "Test Movie 2",
            "output_filename": "Test Movie 2 (2023).mp4",
            "preset_name": "Fast 1080p30"
        }
        
        response = self.client.post('/api/encoding/queue',
                                  json=job_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        queue_data = json.loads(response.data)
        self.assertTrue(queue_data['success'])
        job_id = queue_data['job_id']
        
        # 6. Check encoding status
        response = self.client.get('/api/encoding/status')
        self.assertEqual(response.status_code, 200)
        status_data = json.loads(response.data)
        self.assertGreater(status_data['summary']['total_jobs'], 0)
        
        # 7. Get job progress
        response = self.client.get(f'/api/encoding/progress/{job_id}')
        self.assertEqual(response.status_code, 200)
        progress_data = json.loads(response.data)
        self.assertTrue(progress_data['success'])
        
        # 8. Remove job from queue
        response = self.client.delete(f'/api/encoding/queue/{job_id}')
        self.assertEqual(response.status_code, 200)
        remove_data = json.loads(response.data)
        self.assertTrue(remove_data['success'])
    
    def test_template_management_workflow(self):
        """Test template management workflow"""
        
        # 1. List templates (should be empty initially)
        response = self.client.get('/api/templates')
        self.assertEqual(response.status_code, 200)
        templates_data = json.loads(response.data)
        initial_count = len(templates_data['templates'])
        
        # 2. Upload a new template
        template_data = {
            "name": "test_template",
            "content": {
                "PresetList": [
                    {
                        "PresetName": "Test Preset",
                        "VideoEncoder": "x264",
                        "VideoQualityType": 1,
                        "VideoQualitySlider": 22.0
                    }
                ]
            }
        }
        
        response = self.client.post('/api/templates/upload',
                                  json=template_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        upload_data = json.loads(response.data)
        self.assertTrue(upload_data['success'])
        
        # 3. List templates again (should have one more)
        response = self.client.get('/api/templates')
        self.assertEqual(response.status_code, 200)
        templates_data = json.loads(response.data)
        self.assertEqual(len(templates_data['templates']), initial_count + 1)
        
        # 4. Get specific template
        response = self.client.get('/api/templates/test_template')
        self.assertEqual(response.status_code, 200)
        template_data = json.loads(response.data)
        self.assertTrue(template_data['success'])
        self.assertEqual(template_data['template']['name'], 'test_template')
        
        # 5. Validate template
        validation_data = {
            "content": {
                "PresetList": [
                    {
                        "PresetName": "Valid Preset",
                        "VideoEncoder": "x265"
                    }
                ]
            }
        }
        
        response = self.client.post('/api/templates/validate',
                                  json=validation_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        validation_result = json.loads(response.data)
        self.assertTrue(validation_result['valid'])
        
        # 6. Delete template
        response = self.client.delete('/api/templates/test_template')
        self.assertEqual(response.status_code, 200)
        delete_data = json.loads(response.data)
        self.assertTrue(delete_data['success'])
    
    def test_settings_management_workflow(self):
        """Test settings management workflow"""
        
        # 1. Get current settings
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        settings_data = json.loads(response.data)
        original_max_concurrent = settings_data['max_concurrent_encodes']
        
        # 2. Update settings
        new_settings = {
            "max_concurrent_encodes": 2,
            "testing_mode": True,
            "test_duration_seconds": 60,
            "output_directory": str(self.temp_path / "output"),
            "auto_queue_new_files": True
        }
        
        response = self.client.post('/api/settings',
                                  json=new_settings,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        update_data = json.loads(response.data)
        self.assertTrue(update_data['success'])
        
        # 3. Verify settings were updated
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        updated_settings = json.loads(response.data)
        self.assertEqual(updated_settings['max_concurrent_encodes'], 2)
        self.assertTrue(updated_settings['testing_mode'])
        
        # 4. Restore original settings
        restore_settings = {
            "max_concurrent_encodes": original_max_concurrent,
            "testing_mode": False
        }
        
        response = self.client.post('/api/settings',
                                  json=restore_settings,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
    
    def test_error_handling(self):
        """Test error handling across the application"""
        
        # 1. Test invalid file operations
        response = self.client.get('/api/scan_file/nonexistent.img')
        self.assertEqual(response.status_code, 200)
        error_data = json.loads(response.data)
        self.assertFalse(error_data['success'])
        
        # 2. Test invalid metadata save
        response = self.client.post('/api/save_metadata',
                                  json={"invalid": "data"},
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        error_data = json.loads(response.data)
        self.assertFalse(error_data['success'])
        
        # 3. Test invalid encoding queue
        response = self.client.post('/api/encoding/queue',
                                  json={"missing": "required_fields"},
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.data)
        self.assertFalse(error_data['success'])
        
        # 4. Test path traversal protection
        response = self.client.get('/api/scan_file/../../../etc/passwd')
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.data)
        self.assertIn('path traversal', error_data['error'].lower())
    
    def test_bulk_operations(self):
        """Test bulk operations"""
        
        # 1. Create multiple encoding jobs
        jobs = []
        for i in range(3):
            job_data = {
                "file_name": f"movie{i+1}.img",
                "title_number": 1,
                "movie_name": f"Test Movie {i+1}",
                "output_filename": f"Test Movie {i+1}.mp4",
                "preset_name": "Fast 1080p30"
            }
            jobs.append(job_data)
        
        # Queue first job individually
        response = self.client.post('/api/encoding/queue',
                                  json=jobs[0],
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # 2. Test bulk queue operations
        bulk_data = {
            "operation": "queue_multiple",
            "jobs": jobs[1:]  # Queue remaining jobs
        }
        
        response = self.client.post('/api/encoding/queue/bulk',
                                  json=bulk_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        bulk_result = json.loads(response.data)
        self.assertTrue(bulk_result['success'])
        
        # 3. Verify all jobs were queued
        response = self.client.get('/api/encoding/status')
        self.assertEqual(response.status_code, 200)
        status_data = json.loads(response.data)
        self.assertEqual(status_data['summary']['total_jobs'], 3)
        
        # 4. Clear all jobs
        clear_data = {
            "operation": "clear_all"
        }
        
        response = self.client.post('/api/encoding/queue/bulk',
                                  json=clear_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
