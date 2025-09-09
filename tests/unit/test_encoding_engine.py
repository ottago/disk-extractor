"""
Unit tests for EncodingEngine
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.encoding_engine import EncodingEngine
from models.encoding_models import EncodingJob, EncodingStatus, EncodingProgress, EncodingSettings
from models.metadata_manager import MovieMetadataManager


class TestEncodingEngine(unittest.TestCase):
    """Test EncodingEngine functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create mock metadata manager
        self.mock_manager = Mock(spec=MovieMetadataManager)
        self.mock_manager.directory = self.temp_path
        
        self.engine = EncodingEngine(self.mock_manager)
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        if hasattr(self, 'engine'):
            self.engine.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_settings_default(self):
        """Test loading default settings"""
        settings = self.engine.load_settings()
        
        self.assertIsInstance(settings, EncodingSettings)
        self.assertEqual(settings.max_concurrent_encodes, 1)
        self.assertFalse(settings.testing_mode)
    
    def test_save_settings(self):
        """Test saving settings"""
        settings = EncodingSettings(
            max_concurrent_encodes=2,
            testing_mode=True,
            test_duration_seconds=60
        )
        
        success = self.engine.save_settings(settings)
        self.assertTrue(success)
        
        # Verify settings were saved
        loaded = self.engine.load_settings()
        self.assertEqual(loaded.max_concurrent_encodes, 2)
        self.assertTrue(loaded.testing_mode)
    
    def test_queue_job(self):
        """Test queuing an encoding job"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        queued_job = self.engine.queue_job(job)
        
        self.assertIsNotNone(queued_job.job_id)
        self.assertEqual(queued_job.status, EncodingStatus.QUEUED)
        self.assertEqual(len(self.engine.get_all_jobs()), 1)
    
    def test_remove_job(self):
        """Test removing a job from queue"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        queued_job = self.engine.queue_job(job)
        job_id = queued_job.job_id
        
        success = self.engine.remove_job(job_id)
        self.assertTrue(success)
        self.assertEqual(len(self.engine.get_all_jobs()), 0)
    
    def test_get_job_by_id(self):
        """Test getting job by ID"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        queued_job = self.engine.queue_job(job)
        job_id = queued_job.job_id
        
        retrieved = self.engine.get_job_by_id(job_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_id, job_id)
    
    def test_get_jobs_by_file(self):
        """Test getting jobs by filename"""
        job1 = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie 1",
            output_filename="Test Movie 1.mp4",
            preset_name="Fast 1080p30"
        )
        
        job2 = EncodingJob(
            file_name="test.img",
            title_number=2,
            movie_name="Test Movie 2",
            output_filename="Test Movie 2.mp4",
            preset_name="Fast 1080p30"
        )
        
        self.engine.queue_job(job1)
        self.engine.queue_job(job2)
        
        file_jobs = self.engine.get_jobs_by_file("test.img")
        self.assertEqual(len(file_jobs), 2)
    
    def test_get_jobs_by_status(self):
        """Test getting jobs by status"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        self.engine.queue_job(job)
        
        queued_jobs = self.engine.get_jobs_by_status(EncodingStatus.QUEUED)
        self.assertEqual(len(queued_jobs), 1)
        
        encoding_jobs = self.engine.get_jobs_by_status(EncodingStatus.ENCODING)
        self.assertEqual(len(encoding_jobs), 0)
    
    def test_update_job_progress(self):
        """Test updating job progress"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        queued_job = self.engine.queue_job(job)
        job_id = queued_job.job_id
        
        progress = EncodingProgress(percentage=50.0, fps=30.0)
        self.engine.update_job_progress(job_id, progress)
        
        updated_job = self.engine.get_job_by_id(job_id)
        self.assertEqual(updated_job.progress.percentage, 50.0)
        self.assertEqual(updated_job.progress.fps, 30.0)
    
    def test_update_job_status(self):
        """Test updating job status"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        queued_job = self.engine.queue_job(job)
        job_id = queued_job.job_id
        
        self.engine.update_job_status(job_id, EncodingStatus.ENCODING)
        
        updated_job = self.engine.get_job_by_id(job_id)
        self.assertEqual(updated_job.status, EncodingStatus.ENCODING)
    
    def test_get_cache_stats(self):
        """Test getting cache statistics"""
        stats = self.engine.get_cache_stats()
        
        self.assertIn("jobs_cache_size", stats)
        self.assertIn("jobs_cache_maxsize", stats)
        self.assertIn("jobs_cache_ttl", stats)
    
    def test_clear_completed_jobs(self):
        """Test clearing completed jobs"""
        job = EncodingJob(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        queued_job = self.engine.queue_job(job)
        job_id = queued_job.job_id
        
        # Mark as completed
        self.engine.update_job_status(job_id, EncodingStatus.COMPLETED)
        
        # Clear completed jobs
        cleared_count = self.engine.clear_completed_jobs()
        self.assertEqual(cleared_count, 1)
        self.assertEqual(len(self.engine.get_all_jobs()), 0)
    
    def test_bulk_queue_operations(self):
        """Test bulk queue operations"""
        jobs = [
            EncodingJob(
                file_name="test1.img",
                title_number=1,
                movie_name="Test Movie 1",
                output_filename="Test Movie 1.mp4",
                preset_name="Fast 1080p30"
            ),
            EncodingJob(
                file_name="test2.img",
                title_number=1,
                movie_name="Test Movie 2",
                output_filename="Test Movie 2.mp4",
                preset_name="Fast 1080p30"
            )
        ]
        
        results = self.engine.bulk_queue_jobs(jobs)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(len(self.engine.get_all_jobs()), 2)
        
        for result in results:
            self.assertTrue(result['success'])
            self.assertIn('job_id', result)


if __name__ == '__main__':
    unittest.main()
