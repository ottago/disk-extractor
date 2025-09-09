"""
Unit tests for encoding models
"""

import unittest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.encoding_models import (
    EncodingStatus, EncodingPhase, EncodingProgress, 
    EncodingJob, EncodingSettings, ExtendedMetadata
)


class TestEncodingStatus(unittest.TestCase):
    """Test EncodingStatus enum"""
    
    def test_status_values(self):
        """Test all status values are correct"""
        self.assertEqual(EncodingStatus.NOT_QUEUED.value, "not_queued")
        self.assertEqual(EncodingStatus.QUEUED.value, "queued")
        self.assertEqual(EncodingStatus.ENCODING.value, "encoding")
        self.assertEqual(EncodingStatus.COMPLETED.value, "completed")
        self.assertEqual(EncodingStatus.FAILED.value, "failed")
        self.assertEqual(EncodingStatus.CANCELLED.value, "cancelled")


class TestEncodingPhase(unittest.TestCase):
    """Test EncodingPhase enum"""
    
    def test_phase_values(self):
        """Test all phase values are correct"""
        self.assertEqual(EncodingPhase.SCANNING.value, "scanning")
        self.assertEqual(EncodingPhase.ENCODING.value, "encoding")
        self.assertEqual(EncodingPhase.MUXING.value, "muxing")
        self.assertEqual(EncodingPhase.COMPLETED.value, "completed")


class TestEncodingProgress(unittest.TestCase):
    """Test EncodingProgress dataclass"""
    
    def test_default_values(self):
        """Test default progress values"""
        progress = EncodingProgress()
        
        self.assertEqual(progress.percentage, 0.0)
        self.assertEqual(progress.fps, 0.0)
        self.assertEqual(progress.time_elapsed, 0)
        self.assertEqual(progress.time_remaining, 0)
        self.assertEqual(progress.current_pass, 1)
        self.assertEqual(progress.total_passes, 1)
        self.assertEqual(progress.phase, EncodingPhase.SCANNING)
        self.assertEqual(progress.average_bitrate, 0.0)
        self.assertEqual(progress.output_size_mb, 0.0)
        self.assertEqual(progress.last_updated, "")
    
    def test_to_dict(self):
        """Test converting progress to dictionary"""
        progress = EncodingProgress(
            percentage=50.0,
            fps=30.0,
            phase=EncodingPhase.ENCODING
        )
        
        data = progress.to_dict()
        
        self.assertEqual(data['percentage'], 50.0)
        self.assertEqual(data['fps'], 30.0)
        self.assertEqual(data['phase'], "encoding")
    
    def test_from_dict(self):
        """Test creating progress from dictionary"""
        data = {
            'percentage': 75.0,
            'fps': 25.0,
            'phase': 'muxing',
            'time_elapsed': 3600
        }
        
        progress = EncodingProgress.from_dict(data)
        
        self.assertEqual(progress.percentage, 75.0)
        self.assertEqual(progress.fps, 25.0)
        self.assertEqual(progress.phase, EncodingPhase.MUXING)
        self.assertEqual(progress.time_elapsed, 3600)


class TestEncodingJob(unittest.TestCase):
    """Test EncodingJob dataclass"""
    
    def test_required_fields(self):
        """Test job with required fields only"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        self.assertEqual(job.file_name, "test.img")
        self.assertEqual(job.title_number, 1)
        self.assertEqual(job.movie_name, "Test Movie")
        self.assertEqual(job.output_filename, "Test Movie.mp4")
        self.assertEqual(job.preset_name, "Fast 1080p30")
        self.assertEqual(job.status, EncodingStatus.NOT_QUEUED)
        self.assertEqual(job.queue_position, 0)
        self.assertIsNotNone(job.progress)
        self.assertEqual(job.failure_logs, [])
    
    def test_post_init(self):
        """Test __post_init__ sets defaults correctly"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        # Should have created_at timestamp
        self.assertNotEqual(job.created_at, "")
        
        # Should have progress object
        self.assertIsInstance(job.progress, EncodingProgress)
        
        # Should have empty failure logs list
        self.assertEqual(job.failure_logs, [])
    
    def test_to_dict(self):
        """Test converting job to dictionary"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30",
            status=EncodingStatus.QUEUED
        )
        
        data = job.to_dict()
        
        self.assertEqual(data['file_name'], "test.img")
        self.assertEqual(data['status'], "queued")
        self.assertIn('progress', data)
        self.assertIsInstance(data['progress'], dict)
    
    def test_from_dict(self):
        """Test creating job from dictionary"""
        data = {
            'file_name': 'test.img',
            'title_number': 1,
            'movie_name': 'Test Movie',
            'output_filename': 'Test Movie.mp4',
            'preset_name': 'Fast 1080p30',
            'status': 'completed',
            'progress': {
                'percentage': 100.0,
                'phase': 'completed'
            }
        }
        
        job = EncodingJob.from_dict(data)
        
        self.assertEqual(job.file_name, "test.img")
        self.assertEqual(job.status, EncodingStatus.COMPLETED)
        self.assertEqual(job.progress.percentage, 100.0)


class TestEncodingSettings(unittest.TestCase):
    """Test EncodingSettings dataclass"""
    
    def test_default_values(self):
        """Test default settings values"""
        settings = EncodingSettings()
        
        self.assertEqual(settings.max_concurrent_encodes, 1)
        self.assertFalse(settings.testing_mode)
        self.assertEqual(settings.test_duration_seconds, 30)
        self.assertEqual(settings.output_directory, "/movies")
        self.assertEqual(settings.default_preset, "Fast 1080p30")
        self.assertFalse(settings.auto_queue_new_files)
        self.assertEqual(settings.progress_update_interval, 1)
    
    def test_to_dict(self):
        """Test converting settings to dictionary"""
        settings = EncodingSettings(
            max_concurrent_encodes=2,
            testing_mode=True
        )
        
        data = settings.to_dict()
        
        self.assertEqual(data['max_concurrent_encodes'], 2)
        self.assertTrue(data['testing_mode'])
        self.assertIn('notification_settings', data)
    
    def test_from_dict(self):
        """Test creating settings from dictionary"""
        data = {
            'max_concurrent_encodes': 3,
            'testing_mode': True,
            'output_directory': '/tmp/output',
            'notification_settings': {
                'on_completion': False,
                'on_failure': True
            }
        }
        
        settings = EncodingSettings.from_dict(data)
        
        self.assertEqual(settings.max_concurrent_encodes, 3)
        self.assertTrue(settings.testing_mode)
        self.assertEqual(settings.output_directory, '/tmp/output')
        self.assertFalse(settings.notification_settings['on_completion'])
        self.assertTrue(settings.notification_settings['on_failure'])


class TestExtendedMetadata(unittest.TestCase):
    """Test ExtendedMetadata static methods"""
    
    def test_default_structure(self):
        """Test default metadata structure"""
        metadata = ExtendedMetadata.get_default_structure("test.img", 1000.0)
        
        self.assertEqual(metadata['file_name'], "test.img")
        self.assertEqual(metadata['size_mb'], 1000.0)
        self.assertEqual(metadata['titles'], [])
        self.assertIn('encoding', metadata)
    
    def test_ensure_encoding_structure(self):
        """Test ensuring encoding structure exists"""
        data = {
            'file_name': 'test.img',
            'size_mb': 1000.0,
            'titles': []
        }
        
        result = ExtendedMetadata.ensure_encoding_structure(data)
        
        self.assertIn('encoding', result)
        self.assertIn('jobs', result['encoding'])
        self.assertIn('history', result['encoding'])
    
    def test_add_encoding_job(self):
        """Test adding encoding job to metadata"""
        metadata = ExtendedMetadata.get_default_structure("test.img")
        job_data = {
            'job_id': 'test_123',
            'title_number': 1,
            'status': 'queued'
        }
        
        result = ExtendedMetadata.add_encoding_job(metadata, job_data)
        
        self.assertEqual(len(result['encoding']['jobs']), 1)
        self.assertEqual(result['encoding']['jobs'][0]['job_id'], 'test_123')


if __name__ == '__main__':
    unittest.main()
