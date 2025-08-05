"""
File system watcher for Disk Extractor

Monitors directory for changes to .img and .mmm files and notifies the application.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Set, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)


class MovieFileHandler(FileSystemEventHandler):
    """Handles file system events for movie files"""
    
    def __init__(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Initialize the file handler
        
        Args:
            callback: Function to call when relevant files change
                     Signature: callback(event_type, file_path, file_type)
        """
        super().__init__()
        self.callback = callback
        self.debounce_delay = 1.0  # Seconds to wait before processing events
        self.pending_events: Dict[str, Dict[str, Any]] = {}
        self.debounce_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
    
    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Only process .img and .mmm files
        if file_path.suffix.lower() not in ['.img', '.mmm']:
            return
        
        # Determine file type
        file_type = 'movie' if file_path.suffix.lower() == '.img' else 'metadata'
        
        # Log the event
        logger.debug(f"File system event: {event.event_type} - {file_path} ({file_type})")
        
        # Add to pending events with debouncing
        self._add_pending_event(event.event_type, str(file_path), file_type)
    
    def _add_pending_event(self, event_type: str, file_path: str, file_type: str) -> None:
        """Add event to pending list with debouncing"""
        with self.lock:
            # Store the latest event for this file
            self.pending_events[file_path] = {
                'event_type': event_type,
                'file_path': file_path,
                'file_type': file_type,
                'timestamp': time.time()
            }
            
            # Cancel existing timer and start a new one
            if self.debounce_timer:
                self.debounce_timer.cancel()
            
            self.debounce_timer = threading.Timer(self.debounce_delay, self._process_pending_events)
            self.debounce_timer.start()
    
    def _process_pending_events(self) -> None:
        """Process all pending events"""
        with self.lock:
            events_to_process = list(self.pending_events.values())
            self.pending_events.clear()
            self.debounce_timer = None
        
        # Process each unique event
        for event_data in events_to_process:
            try:
                self.callback(
                    event_data['event_type'],
                    event_data['file_path'],
                    event_data['file_type']
                )
            except Exception as e:
                logger.error(f"Error processing file event: {e}")


class FileWatcherService:
    """Service for monitoring file system changes"""
    
    def __init__(self) -> None:
        """Initialize the file watcher service"""
        self.observer: Optional[Observer] = None
        self.watched_directory: Optional[Path] = None
        self.callbacks: Set[Callable[[str, str, str], None]] = set()
        self.is_running = False
        self.lock = threading.Lock()
    
    def add_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Add a callback function to be called when files change
        
        Args:
            callback: Function with signature callback(event_type, file_path, file_type)
        """
        with self.lock:
            self.callbacks.add(callback)
            callback_name = getattr(callback, '__name__', str(callback))
            logger.debug(f"Added file watcher callback: {callback_name}")
    
    def remove_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Remove a callback function
        
        Args:
            callback: Function to remove
        """
        with self.lock:
            self.callbacks.discard(callback)
            callback_name = getattr(callback, '__name__', str(callback))
            logger.debug(f"Removed file watcher callback: {callback_name}")
    
    def start_watching(self, directory: Path) -> bool:
        """
        Start watching a directory for changes
        
        Args:
            directory: Directory to watch
            
        Returns:
            True if watching started successfully
        """
        try:
            directory = Path(directory).resolve()
            
            if not directory.exists() or not directory.is_dir():
                logger.error(f"Invalid directory for watching: {directory}")
                return False
            
            # Stop existing watcher if running
            self.stop_watching()
            
            with self.lock:
                self.watched_directory = directory
                
                # Create observer and handler
                self.observer = Observer()
                handler = MovieFileHandler(self._notify_callbacks)
                
                # Start watching
                self.observer.schedule(handler, str(directory), recursive=False)
                self.observer.start()
                self.is_running = True
                
                logger.info(f"Started watching directory: {directory}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to start file watching: {e}")
            return False
    
    def stop_watching(self) -> None:
        """Stop watching for file changes"""
        with self.lock:
            if self.observer and self.is_running:
                try:
                    self.observer.stop()
                    self.observer.join(timeout=5.0)  # Wait up to 5 seconds
                    logger.info(f"Stopped watching directory: {self.watched_directory}")
                except Exception as e:
                    logger.error(f"Error stopping file watcher: {e}")
                finally:
                    self.observer = None
                    self.is_running = False
                    self.watched_directory = None
    
    def is_watching(self) -> bool:
        """
        Check if the service is currently watching
        
        Returns:
            True if watching is active
        """
        return self.is_running and self.observer is not None
    
    def get_watched_directory(self) -> Optional[Path]:
        """
        Get the currently watched directory
        
        Returns:
            Path to watched directory or None
        """
        return self.watched_directory
    
    def _notify_callbacks(self, event_type: str, file_path: str, file_type: str) -> None:
        """Notify all registered callbacks of a file change"""
        with self.lock:
            callbacks_to_call = list(self.callbacks)
        
        for callback in callbacks_to_call:
            try:
                callback(event_type, file_path, file_type)
            except Exception as e:
                callback_name = getattr(callback, '__name__', str(callback))
                logger.error(f"Error in file watcher callback {callback_name}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get file watcher statistics
        
        Returns:
            Dictionary with watcher statistics
        """
        return {
            'is_watching': self.is_watching(),
            'watched_directory': str(self.watched_directory) if self.watched_directory else None,
            'callback_count': len(self.callbacks),
            'observer_alive': self.observer.is_alive() if self.observer else False
        }
    
    def __del__(self) -> None:
        """Cleanup when service is destroyed"""
        self.stop_watching()


# Global file watcher service instance
file_watcher = FileWatcherService()
