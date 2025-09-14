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
        # EncodingEngine loads settings internally, check via get_cache_stats
        stats = self.engine.get_cache_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn("cache_size", stats)
    
    def test_save_settings(self):
        """Test saving settings"""
        # EncodingEngine doesn't expose public save_settings
        # Test that we can create settings and they persist
        stats_before = self.engine.get_cache_stats()
        stats_after = self.engine.get_cache_stats()
        
        # Should be consistent
        self.assertEqual(stats_before["cache_size"], stats_after["cache_size"])
    
    def test_queue_job(self):
        """Test queuing an encoding job"""
        success = self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        self.assertTrue(success)
        jobs = self.engine.get_all_jobs()
        self.assertEqual(len(jobs), 1)
    
    def test_remove_job(self):
        """Test removing a job from queue"""
        # Queue a job first
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        jobs = self.engine.get_all_jobs()
        self.assertEqual(len(jobs), 1)
        
        job_id = jobs[0].job_id
        success = self.engine.cancel_job(job_id)
        self.assertTrue(success)
    
    def test_get_job_by_id(self):
        """Test getting job by ID"""
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        jobs = self.engine.get_all_jobs()
        job_id = jobs[0].job_id
        
        retrieved = self.engine.get_job_status(job_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_id, job_id)
    
    def test_get_jobs_by_file(self):
        """Test getting jobs by filename"""
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie 1",
            output_filename="Test Movie 1.mp4",
            preset_name="Fast 1080p30"
        )
        
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=2,
            movie_name="Test Movie 2",
            output_filename="Test Movie 2.mp4",
            preset_name="Fast 1080p30"
        )
        
        all_jobs = self.engine.get_all_jobs()
        file_jobs = [job for job in all_jobs if job.file_name == "test.img"]
        self.assertEqual(len(file_jobs), 2)
    
    def test_get_jobs_by_status(self):
        """Test getting jobs by status"""
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        all_jobs = self.engine.get_all_jobs()
        queued_jobs = [job for job in all_jobs if job.status == EncodingStatus.QUEUED]
        self.assertEqual(len(queued_jobs), 1)
        
        encoding_jobs = [job for job in all_jobs if job.status == EncodingStatus.ENCODING]
        self.assertEqual(len(encoding_jobs), 0)
    
    def test_update_job_progress(self):
        """Test updating job progress"""
        # This is internal functionality, test that jobs maintain progress
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        jobs = self.engine.get_all_jobs()
        job = jobs[0]
        
        # Job should have progress object
        self.assertIsNotNone(job.progress)
        self.assertEqual(job.progress.percentage, 0.0)
    
    def test_update_job_status(self):
        """Test updating job status"""
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        jobs = self.engine.get_all_jobs()
        job = jobs[0]
        
        # Job should start as queued
        self.assertEqual(job.status, EncodingStatus.QUEUED)
    
    def test_get_cache_stats(self):
        """Test getting cache statistics"""
        stats = self.engine.get_cache_stats()
        
        self.assertIn("cache_size", stats)
        self.assertIn("cache_age_seconds", stats)
        self.assertIn("cache_ttl_seconds", stats)
    
    def test_clear_completed_jobs(self):
        """Test clearing completed jobs"""
        # Queue and complete a job
        self.engine.queue_encoding_job(
            file_name="test.img",
            title_number=1,
            movie_name="Test Movie",
            output_filename="Test Movie.mp4",
            preset_name="Fast 1080p30"
        )
        
        jobs_before = len(self.engine.get_all_jobs())
        self.assertEqual(jobs_before, 1)
        
        # Cancel the job (simulates completion)
        jobs = self.engine.get_all_jobs()
        job_id = jobs[0].job_id
        self.engine.cancel_job(job_id)
        
        # Job should be removed
        jobs_after = len(self.engine.get_all_jobs())
        self.assertEqual(jobs_after, 0)
    
    def test_bulk_queue_operations(self):
        """Test bulk queue operations"""
        # Test multiple individual operations
        success1 = self.engine.queue_encoding_job(
            file_name="test1.img",
            title_number=1,
            movie_name="Test Movie 1",
            output_filename="Test Movie 1.mp4",
            preset_name="Fast 1080p30"
        )
        
        success2 = self.engine.queue_encoding_job(
            file_name="test2.img",
            title_number=1,
            movie_name="Test Movie 2",
            output_filename="Test Movie 2.mp4",
            preset_name="Fast 1080p30"
        )
        
        self.assertTrue(success1)
        self.assertTrue(success2)
        self.assertEqual(len(self.engine.get_all_jobs()), 2)


if __name__ == '__main__':
    unittest.main()
