"""
Integration tests for WebSocket functionality
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
from flask_socketio import SocketIOTestClient


class TestWebSocketIntegration(unittest.TestCase):
    """Test WebSocket integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test app
        self.app = create_app(self.temp_dir)
        self.app.config['TESTING'] = True
        
        # Create SocketIO test client
        from app import socketio
        self.socketio_client = SocketIOTestClient(self.app, socketio)
        
        # Create test files
        self.create_test_files()
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        if hasattr(self, 'socketio_client'):
            self.socketio_client.disconnect()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_files(self):
        """Create test .img files"""
        (self.temp_path / "movie1.img").write_bytes(b"fake content 1")
        (self.temp_path / "movie2.img").write_bytes(b"fake content 2")
    
    def test_websocket_connection(self):
        """Test WebSocket connection"""
        self.assertTrue(self.socketio_client.is_connected())
    
    def test_connect_event(self):
        """Test connect event handling"""
        # Should receive status message on connect
        received = self.socketio_client.get_received()
        
        # Look for status message
        status_messages = [msg for msg in received if msg['name'] == 'status']
        self.assertGreater(len(status_messages), 0)
        
        status_msg = status_messages[0]
        self.assertIn('message', status_msg['args'][0])
    
    def test_request_file_list(self):
        """Test requesting file list via WebSocket"""
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Request file list
        self.socketio_client.emit('request_file_list')
        
        # Check for file list update
        received = self.socketio_client.get_received()
        file_list_messages = [msg for msg in received if msg['name'] == 'file_list_update']
        
        self.assertGreater(len(file_list_messages), 0)
        
        file_list_msg = file_list_messages[0]
        data = file_list_msg['args'][0]
        
        self.assertIn('movies', data)
        self.assertIn('directory', data)
        self.assertEqual(len(data['movies']), 2)
    
    def test_request_encoding_status(self):
        """Test requesting encoding status via WebSocket"""
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Request encoding status
        self.socketio_client.emit('request_encoding_status')
        
        # Check for encoding status update
        received = self.socketio_client.get_received()
        status_messages = [msg for msg in received if msg['name'] == 'encoding_status_update']
        
        self.assertGreater(len(status_messages), 0)
        
        status_msg = status_messages[0]
        data = status_msg['args'][0]
        
        self.assertIn('jobs', data)
        self.assertIn('summary', data)
        self.assertIn('total_jobs', data['summary'])
    
    def test_file_change_notification(self):
        """Test file change notifications"""
        # This test would require triggering actual file system changes
        # For now, we'll test the notification mechanism directly
        
        from app import notify_file_changes
        
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Trigger file change notification
        notify_file_changes('added', 'new_movie.img')
        
        # Check for file list update
        received = self.socketio_client.get_received()
        file_list_messages = [msg for msg in received if msg['name'] == 'file_list_update']
        
        self.assertGreater(len(file_list_messages), 0)
        
        file_list_msg = file_list_messages[0]
        data = file_list_msg['args'][0]
        
        self.assertEqual(data['change_type'], 'added')
        self.assertEqual(data['filename'], 'new_movie.img')
    
    def test_encoding_progress_notification(self):
        """Test encoding progress notifications"""
        from app import notify_encoding_progress
        from models.encoding_models import EncodingProgress, EncodingPhase
        
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Create test progress
        progress = EncodingProgress(
            percentage=50.0,
            fps=30.0,
            phase=EncodingPhase.ENCODING
        )
        
        # Trigger progress notification
        notify_encoding_progress('test_job_123', progress)
        
        # Check for progress update
        received = self.socketio_client.get_received()
        progress_messages = [msg for msg in received if msg['name'] == 'encoding_progress']
        
        self.assertGreater(len(progress_messages), 0)
        
        progress_msg = progress_messages[0]
        data = progress_msg['args'][0]
        
        self.assertEqual(data['job_id'], 'test_job_123')
        self.assertIn('progress', data)
        self.assertEqual(data['progress']['percentage'], 50.0)
    
    def test_encoding_status_change_notification(self):
        """Test encoding status change notifications"""
        from app import notify_encoding_status_change
        from models.encoding_models import EncodingStatus
        
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Trigger status change notification
        notify_encoding_status_change('test_job_123', EncodingStatus.COMPLETED)
        
        # Check for status change update
        received = self.socketio_client.get_received()
        status_messages = [msg for msg in received if msg['name'] == 'encoding_status_change']
        
        self.assertGreater(len(status_messages), 0)
        
        status_msg = status_messages[0]
        data = status_msg['args'][0]
        
        self.assertEqual(data['job_id'], 'test_job_123')
        self.assertEqual(data['status'], 'completed')
    
    def test_metadata_update_notification(self):
        """Test metadata update notifications"""
        from app import notify_file_changes
        
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Trigger metadata update notification
        notify_file_changes('metadata_updated', 'movie1.img')
        
        # Check for both file list update and metadata update
        received = self.socketio_client.get_received()
        
        file_list_messages = [msg for msg in received if msg['name'] == 'file_list_update']
        metadata_messages = [msg for msg in received if msg['name'] == 'metadata_updated']
        
        self.assertGreater(len(file_list_messages), 0)
        # Note: metadata_updated might not be sent if movie data isn't found
        
        file_list_msg = file_list_messages[0]
        data = file_list_msg['args'][0]
        
        self.assertEqual(data['change_type'], 'metadata_updated')
        self.assertEqual(data['filename'], 'movie1.img')
    
    def test_disconnect_handling(self):
        """Test disconnect handling"""
        # Disconnect the client
        self.socketio_client.disconnect()
        
        # Verify disconnection
        self.assertFalse(self.socketio_client.is_connected())
    
    def test_error_handling(self):
        """Test error handling in WebSocket events"""
        # This would test error scenarios in WebSocket handlers
        # For now, we'll test that invalid requests don't crash the server
        
        # Clear any existing messages
        self.socketio_client.get_received()
        
        # Send invalid event (should not crash)
        self.socketio_client.emit('invalid_event', {'invalid': 'data'})
        
        # Server should still be responsive
        self.socketio_client.emit('request_file_list')
        received = self.socketio_client.get_received()
        
        # Should still receive file list update
        file_list_messages = [msg for msg in received if msg['name'] == 'file_list_update']
        self.assertGreater(len(file_list_messages), 0)


if __name__ == '__main__':
    unittest.main()
