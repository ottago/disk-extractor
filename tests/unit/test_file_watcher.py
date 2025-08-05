"""
Unit tests for file watcher utilities
"""

import unittest
import sys
import tempfile
import shutil
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.file_watcher import FileWatcherService, MovieFileHandler


class TestMovieFileHandler(unittest.TestCase):
    """Test movie file handler"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.callback_mock = Mock()
        self.handler = MovieFileHandler(self.callback_mock)
    
    def test_ignores_directories(self):
        """Test that directory events are ignored"""
        from watchdog.events import DirCreatedEvent
        
        event = DirCreatedEvent('/test/directory')
        self.handler.on_any_event(event)
        
        # Should not call callback for directories
        self.callback_mock.assert_not_called()
    
    def test_ignores_non_movie_files(self):
        """Test that non-.img/.mmm files are ignored"""
        from watchdog.events import FileCreatedEvent
        
        # Test various non-movie file extensions
        non_movie_files = [
            '/test/document.txt',
            '/test/image.jpg',
            '/test/video.mp4',
            '/test/archive.zip'
        ]
        
        for file_path in non_movie_files:
            with self.subTest(file_path=file_path):
                event = FileCreatedEvent(file_path)
                self.handler.on_any_event(event)
        
        # Should not call callback for non-movie files
        self.callback_mock.assert_not_called()
    
    def test_processes_img_files(self):
        """Test that .img files are processed"""
        from watchdog.events import FileCreatedEvent
        
        event = FileCreatedEvent('/test/movie.img')
        self.handler.on_any_event(event)
        
        # Wait for debouncing
        time.sleep(1.1)
        
        # Should call callback for .img files
        self.callback_mock.assert_called_once()
        args = self.callback_mock.call_args[0]
        self.assertEqual(args[0], 'created')  # event_type
        self.assertEqual(args[1], '/test/movie.img')  # file_path
        self.assertEqual(args[2], 'movie')  # file_type
    
    def test_processes_mmm_files(self):
        """Test that .mmm files are processed"""
        from watchdog.events import FileModifiedEvent
        
        event = FileModifiedEvent('/test/movie.mmm')
        self.handler.on_any_event(event)
        
        # Wait for debouncing
        time.sleep(1.1)
        
        # Should call callback for .mmm files
        self.callback_mock.assert_called_once()
        args = self.callback_mock.call_args[0]
        self.assertEqual(args[0], 'modified')  # event_type
        self.assertEqual(args[1], '/test/movie.mmm')  # file_path
        self.assertEqual(args[2], 'metadata')  # file_type
    
    def test_case_insensitive_extensions(self):
        """Test that file extensions are case insensitive"""
        from watchdog.events import FileCreatedEvent
        
        # Test uppercase extensions
        event1 = FileCreatedEvent('/test/MOVIE.IMG')
        event2 = FileCreatedEvent('/test/MOVIE.MMM')
        
        self.handler.on_any_event(event1)
        self.handler.on_any_event(event2)
        
        # Wait for debouncing
        time.sleep(1.1)
        
        # Should process both files
        self.assertEqual(self.callback_mock.call_count, 2)
    
    def test_debouncing(self):
        """Test that rapid events are debounced"""
        from watchdog.events import FileModifiedEvent
        
        # Send multiple rapid events for the same file
        for _ in range(5):
            event = FileModifiedEvent('/test/movie.img')
            self.handler.on_any_event(event)
            time.sleep(0.1)  # Small delay between events
        
        # Wait for debouncing
        time.sleep(1.1)
        
        # Should only call callback once due to debouncing
        self.callback_mock.assert_called_once()


class TestFileWatcherService(unittest.TestCase):
    """Test file watcher service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = FileWatcherService()
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create some test files
        (self.test_dir / "movie1.img").touch()
        (self.test_dir / "movie2.img").touch()
        (self.test_dir / "movie1.mmm").touch()
    
    def tearDown(self):
        """Clean up test fixtures"""
        self.service.stop_watching()
        shutil.rmtree(self.test_dir)
    
    def test_add_remove_callback(self):
        """Test adding and removing callbacks"""
        callback1 = Mock()
        callback2 = Mock()
        
        # Initially no callbacks
        self.assertEqual(len(self.service.callbacks), 0)
        
        # Add callbacks
        self.service.add_callback(callback1)
        self.service.add_callback(callback2)
        self.assertEqual(len(self.service.callbacks), 2)
        
        # Remove callback
        self.service.remove_callback(callback1)
        self.assertEqual(len(self.service.callbacks), 1)
        self.assertIn(callback2, self.service.callbacks)
        self.assertNotIn(callback1, self.service.callbacks)
    
    def test_start_watching_valid_directory(self):
        """Test starting to watch a valid directory"""
        result = self.service.start_watching(self.test_dir)
        
        self.assertTrue(result)
        self.assertTrue(self.service.is_watching())
        self.assertEqual(self.service.get_watched_directory(), self.test_dir)
    
    def test_start_watching_invalid_directory(self):
        """Test starting to watch an invalid directory"""
        invalid_dir = self.test_dir / "nonexistent"
        result = self.service.start_watching(invalid_dir)
        
        self.assertFalse(result)
        self.assertFalse(self.service.is_watching())
        self.assertIsNone(self.service.get_watched_directory())
    
    def test_start_watching_file_instead_of_directory(self):
        """Test starting to watch a file instead of directory"""
        file_path = self.test_dir / "movie1.img"
        result = self.service.start_watching(file_path)
        
        self.assertFalse(result)
        self.assertFalse(self.service.is_watching())
    
    def test_stop_watching(self):
        """Test stopping file watching"""
        # Start watching
        self.service.start_watching(self.test_dir)
        self.assertTrue(self.service.is_watching())
        
        # Stop watching
        self.service.stop_watching()
        self.assertFalse(self.service.is_watching())
        self.assertIsNone(self.service.get_watched_directory())
    
    def test_multiple_start_stops_previous_watcher(self):
        """Test that starting a new watcher stops the previous one"""
        # Start watching first directory
        self.service.start_watching(self.test_dir)
        first_observer = self.service.observer
        
        # Start watching second directory
        second_dir = Path(tempfile.mkdtemp())
        try:
            self.service.start_watching(second_dir)
            
            # Should have stopped the first observer
            self.assertNotEqual(self.service.observer, first_observer)
            self.assertEqual(self.service.get_watched_directory(), second_dir)
        finally:
            shutil.rmtree(second_dir)
    
    def test_callback_notification(self):
        """Test that callbacks are notified of file changes"""
        callback1 = Mock()
        callback2 = Mock()
        
        self.service.add_callback(callback1)
        self.service.add_callback(callback2)
        
        # Simulate a file change notification
        self.service._notify_callbacks('created', '/test/movie.img', 'movie')
        
        # Both callbacks should be called
        callback1.assert_called_once_with('created', '/test/movie.img', 'movie')
        callback2.assert_called_once_with('created', '/test/movie.img', 'movie')
    
    def test_callback_error_handling(self):
        """Test that callback errors don't break the service"""
        good_callback = Mock()
        bad_callback = Mock(side_effect=Exception("Test error"))
        
        self.service.add_callback(good_callback)
        self.service.add_callback(bad_callback)
        
        # Should not raise exception even with bad callback
        self.service._notify_callbacks('created', '/test/movie.img', 'movie')
        
        # Good callback should still be called
        good_callback.assert_called_once()
        bad_callback.assert_called_once()
    
    def test_get_stats(self):
        """Test getting watcher statistics"""
        # Initially not watching
        stats = self.service.get_stats()
        self.assertFalse(stats['is_watching'])
        self.assertIsNone(stats['watched_directory'])
        self.assertEqual(stats['callback_count'], 0)
        self.assertFalse(stats['observer_alive'])
        
        # Add callback and start watching
        callback = Mock()
        self.service.add_callback(callback)
        self.service.start_watching(self.test_dir)
        
        stats = self.service.get_stats()
        self.assertTrue(stats['is_watching'])
        self.assertEqual(stats['watched_directory'], str(self.test_dir))
        self.assertEqual(stats['callback_count'], 1)
        self.assertTrue(stats['observer_alive'])
    
    @patch('utils.file_watcher.logger')
    def test_logging(self, mock_logger):
        """Test that appropriate logging occurs"""
        callback = Mock()
        self.service.add_callback(callback)
        
        # Should log when starting to watch
        self.service.start_watching(self.test_dir)
        mock_logger.info.assert_called()
        
        # Should log when stopping
        self.service.stop_watching()
        mock_logger.info.assert_called()


class TestFileWatcherIntegration(unittest.TestCase):
    """Integration tests for file watcher"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.service = FileWatcherService()
        self.callback_results = []
        
        def test_callback(event_type, file_path, file_type):
            self.callback_results.append((event_type, file_path, file_type))
        
        self.service.add_callback(test_callback)
        self.service.start_watching(self.test_dir)
        
        # Give the watcher time to start
        time.sleep(0.5)
    
    def tearDown(self):
        """Clean up test fixtures"""
        self.service.stop_watching()
        shutil.rmtree(self.test_dir)
    
    def test_real_file_creation(self):
        """Test detection of real file creation"""
        # Clear any existing results
        self.callback_results.clear()
        
        # Create a new movie file
        test_file = self.test_dir / "new_movie.img"
        test_file.touch()
        
        # Wait for file system event processing with timeout
        max_wait = 5  # seconds
        wait_interval = 0.1
        waited = 0
        
        while waited < max_wait:
            time.sleep(wait_interval)
            waited += wait_interval
            
            # Check if we got any event for our file
            file_events = [
                result for result in self.callback_results 
                if 'new_movie.img' in result[1]
            ]
            
            if file_events:
                break
        
        # Should have detected some file event
        self.assertTrue(len(self.callback_results) > 0, 
                       f"No events detected after {max_wait}s. Results: {self.callback_results}")
        
        # Find any event for our file (created, closed, modified, etc.)
        file_events = [
            result for result in self.callback_results 
            if 'new_movie.img' in result[1]
        ]
        self.assertTrue(len(file_events) > 0, 
                       f"No events found for new_movie.img. All events: {self.callback_results}")
        
        # Verify it's detected as a movie file
        movie_events = [
            result for result in file_events
            if result[2] == 'movie'
        ]
        self.assertTrue(len(movie_events) > 0,
                       f"File not detected as movie type. Events: {file_events}")
    
    def test_real_file_deletion(self):
        """Test detection of real file deletion"""
        # Create and then delete a file
        test_file = self.test_dir / "temp_movie.img"
        test_file.touch()
        time.sleep(1)  # Let creation event process
        
        # Clear previous results
        self.callback_results.clear()
        
        # Delete the file
        test_file.unlink()
        
        # Wait for file system event processing
        time.sleep(2)
        
        # Should have detected the file deletion
        deletion_events = [
            result for result in self.callback_results 
            if result[0] == 'deleted' and 'temp_movie.img' in result[1]
        ]
        self.assertTrue(len(deletion_events) > 0)


if __name__ == '__main__':
    unittest.main()
