#!/usr/bin/env python3
"""
Disk Extractor - Movie Metadata Manager

A web-based application for managing movie metadata stored in .mmm files 
alongside .img movie files, with HandBrake integration for video processing.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Union
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_socketio import SocketIO, emit

# Import our modules
from config import Config
from models.metadata_manager import MovieMetadataManager, MetadataError
from models.encoding_engine import EncodingEngine
from models.encoding_models import EncodingProgress, EncodingStatus
from api.routes import init_api_routes
from api.encoding_routes import create_encoding_routes, create_settings_routes
from api.template_routes import create_template_routes
from utils.security import apply_security_headers, check_path_traversal, log_security_event
from utils.json_helpers import prepare_for_template

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'disk-extractor-secret-key-change-in-production')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)

# Global manager instances
manager = MovieMetadataManager()
encoding_engine = EncodingEngine(manager)

# App creation guard to prevent multiple creations
_app_created = False


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.debug(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to Disk Extractor'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.debug(f"Client disconnected: {request.sid}")


@socketio.on('request_file_list')
def handle_request_file_list():
    """Handle request for current file list"""
    try:
        emit('file_list_update', {
            'movies': manager.movies,
            'directory': str(manager.directory) if manager.directory else None
        })
    except Exception as e:
        logger.error(f"Error sending file list: {e}")
        emit('error', {'message': 'Failed to get file list'})


@socketio.on('request_encoding_status')
def handle_request_encoding_status():
    """Handle request for current encoding status"""
    try:
        jobs = encoding_engine.get_all_jobs()
        
        # Group jobs by status
        status_groups = {
            'encoding': [],
            'queued': [],
            'completed': [],
            'failed': []
        }
        
        for job in jobs:
            job_data = job.to_dict()
            if job.status == EncodingStatus.ENCODING:
                status_groups['encoding'].append(job_data)
            elif job.status == EncodingStatus.QUEUED:
                status_groups['queued'].append(job_data)
            elif job.status == EncodingStatus.COMPLETED:
                status_groups['completed'].append(job_data)
            elif job.status == EncodingStatus.FAILED:
                status_groups['failed'].append(job_data)
        
        emit('encoding_status_update', {
            'jobs': status_groups,
            'summary': {
                'total_jobs': len(jobs),
                'encoding_count': len(status_groups['encoding']),
                'queued_count': len(status_groups['queued']),
                'completed_count': len(status_groups['completed']),
                'failed_count': len(status_groups['failed'])
            }
        })
    except Exception as e:
        logger.error(f"Error sending encoding status: {e}")
        emit('error', {'message': 'Failed to get encoding status'})


def notify_encoding_progress(job_id: str, progress: EncodingProgress) -> None:
    """Notify all connected clients of encoding progress"""
    try:
        progress_data = prepare_for_template(progress.to_dict())
        socketio.emit('encoding_progress', {
            'job_id': job_id,
            'progress': progress_data
        })
        logger.debug(f"Sent progress update for job: {job_id} - {progress.percentage}%")
    except Exception as e:
        logger.error(f"Error notifying encoding progress: {e}")


def notify_encoding_status_change(job_id: str, status: EncodingStatus) -> None:
    """Notify all connected clients of encoding status changes"""
    try:
        socketio.emit('encoding_status_change', {
            'job_id': job_id,
            'status': status.value
        })
        logger.debug(f"Sent status change for job: {job_id} - {status.value}")
        
        # Also trigger file list update since encoding status affects file display
        # Extract filename from job_id (format: filename_title_hash)
        # Split by '_' and take all parts except the last two (title and hash)
        parts = job_id.split('_')
        if len(parts) >= 3:
            # Rejoin all parts except the last two
            filename = '_'.join(parts[:-2])
        else:
            # Fallback to first part if format is unexpected
            filename = parts[0]
        
        notify_file_changes('encoding_status_updated', filename)
    except Exception as e:
        logger.error(f"Error notifying encoding status change: {e}")


def notify_file_changes(change_type: str, filename: Optional[str] = None) -> None:
    """Notify all connected clients of file changes"""
    try:
        # Prepare movies data for JSON serialization
        movies_data = prepare_for_template(manager.movies)
        
        # Send general file list update
        socketio.emit('file_list_update', {
            'movies': movies_data,
            'directory': str(manager.directory) if manager.directory else None,
            'change_type': change_type,
            'filename': filename
        })
        
        # Send specific metadata update if it's a metadata change
        if change_type == 'metadata_updated' and filename:
            # Find the updated movie data
            movie_data = None
            for movie in movies_data:  # Use prepared data
                if movie['file_name'] == filename:
                    movie_data = movie
                    break
            
            if movie_data:
                socketio.emit('metadata_updated', {
                    'filename': filename,
                    'movie_data': movie_data
                })
                logger.debug(f"Sent metadata update for: {filename}")
            else:
                logger.debug(f"Movie data not found for: {filename}")
        
        logger.debug(f"Notified clients of file change: {change_type} - {filename}")
    except Exception as e:
        logger.error(f"Error notifying file changes: {e}", exc_info=True)


# Security middleware
@app.after_request
def add_security_headers(response: Response) -> Response:
    """Add security headers to all responses"""
    is_api_endpoint = request.endpoint and request.endpoint.startswith('api.')
    return apply_security_headers(response, is_api_endpoint)


@app.before_request
def check_security() -> Optional[Response]:
    """Check for security issues in requests"""
    if request.path.startswith('/api/'):
        # Check for path traversal attempts
        if check_path_traversal(request.path):
            log_security_event("Path traversal attempt", request.path, request.remote_addr)
            logger.warning(f"Blocked path traversal attempt: {request.path}")
            return jsonify({
                'success': False,
                'error': 'Invalid filename: path traversal detected'
            }), 400
    return None


@app.errorhandler(404)
def handle_404(error) -> Union[Response, tuple]:
    """Handle 404 errors, especially for API endpoints with malicious paths"""
    if request.path.startswith('/api/'):
        # For API endpoints, return JSON error instead of HTML
        return jsonify({
            'success': False,
            'error': 'Invalid filename: path traversal detected'
        }), 400
    
    # For non-API endpoints, return normal 404
    return error


@app.route('/api/encoding/download/<filename>')
def download_output_file(filename: str) -> Union[Response, tuple]:
    """Download an output file"""
    try:
        from flask import send_file
        import os
        
        logger.info(f"Download request for file: {filename}")
        
        # Validate filename to prevent path traversal
        if '..' in filename or filename.startswith('/') or '/' in filename:
            logger.warning(f"Invalid filename rejected: {filename}")
            return jsonify({'success': False, 'error': 'Invalid filename'}), 400
        
        # Get the movies directory from metadata manager
        if not manager or not manager.directory:
            logger.error("Movies directory not configured")
            return jsonify({'success': False, 'error': 'Movies directory not configured'}), 500
        
        # Search for the file in encoding history to get the correct path
        file_path = None
        for movie in manager.movies:
            metadata = manager.load_metadata(movie['file_name'])
            if metadata and 'encoding' in metadata and 'jobs' in metadata['encoding']:
                for job in metadata['encoding']['jobs']:
                    if job.get('output_filename') == filename and job.get('output_path'):
                        file_path = job['output_path']
                        break
                if file_path:
                    break
        
        if not file_path:
            # Fallback to looking in root movies directory
            file_path = os.path.join(str(manager.directory), filename)
        
        logger.info(f"Looking for file at: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Ensure the resolved path is still within the movies directory (security check)
        movies_dir = os.path.realpath(str(manager.directory))
        resolved_path = os.path.realpath(file_path)
        if not resolved_path.startswith(movies_dir):
            logger.warning(f"Access denied for path: {resolved_path}")
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        logger.info(f"Serving file: {resolved_path}")
        return send_file(file_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        return jsonify({'success': False, 'error': 'Download failed'}), 500


# Main routes
@app.route('/')
def index() -> Union[str, Response]:
    """Main interface"""
    if not manager.directory:
        return redirect(url_for('setup'))
    
    # Prepare movies data for template to handle enum serialization
    movies_data = prepare_for_template(manager.movies)
    
    return render_template('index.html', 
                         movies=movies_data, 
                         directory=str(manager.directory))


@app.route('/settings')
def settings() -> str:
    """Settings page"""
    return render_template('settings.html')


@app.route('/setup', methods=['GET', 'POST'])
def setup() -> str:
    """Directory selection page"""
    if request.method == 'POST':
        directory = request.form.get('directory', '').strip()
        if directory and Path(directory).exists():
            try:
                manager.set_directory(directory)
                return redirect(url_for('index'))
            except MetadataError as e:
                return render_template('setup.html', error=str(e))
        else:
            return render_template('setup.html', 
                                 error="Directory does not exist or is not accessible")
    
    return render_template('setup.html')


@app.route('/health')
def health() -> Union[Response, tuple]:
    """Health check endpoint"""
    try:
        handbrake_available = manager.test_handbrake()
        cache_stats = manager.get_cache_stats()
        
        # Get file watcher stats
        from utils.file_watcher import file_watcher
        watcher_stats = file_watcher.get_stats()
        
        return jsonify({
            'status': 'ok',
            'handbrake': 'available' if handbrake_available else 'unavailable',
            'directory': str(manager.directory) if manager.directory else None,
            'movie_count': len(manager.movies),
            'cache_stats': cache_stats,
            'file_watcher': watcher_stats,
            'encoding_cache_stats': encoding_engine.get_cache_stats(),
            'config': {
                'handbrake_timeout': Config.HANDBRAKE_TIMEOUT,
                'max_cache_size': Config.MAX_CACHE_SIZE,
                'cache_ttl': Config.CACHE_TTL,
                'encoding_jobs_cache_ttl': Config.ENCODING_JOBS_CACHE_TTL
            }
        })
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


def create_app(directory: Optional[Union[str, Path]] = None) -> Flask:
    """
    Application factory function
    
    Args:
        directory: Initial directory to use
        
    Returns:
        Configured Flask application
    """
    global _app_created
    
    # Prevent multiple app creations in the same process
    if _app_created:
        logger.warning("App already created in this process, returning existing configuration")
        return app
    
    _app_created = True
    
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Set directory if provided
    if directory:
        try:
            manager.set_directory(directory)
            logger.info(f"Using directory: {directory}")
        except MetadataError as e:
            logger.error(f"Error setting directory: {e}")
            sys.exit(1)
    
    # Register file change callback
    manager.add_change_callback(notify_file_changes)
    
    # Initialize and start encoding engine
    encoding_engine.add_progress_callback(notify_encoding_progress)
    encoding_engine.add_status_callback(notify_encoding_status_change)
    
    # Add notification handler
    def handle_notification(notification_data):
        """Handle encoding notifications"""
        notification_type = notification_data.get('type', 'unknown')
        message = notification_data.get('message', '')
        job_data = notification_data.get('job')
        
        logger.info(f"📢 Notification [{notification_type.upper()}]: {message}")
        
        # You could extend this to send actual notifications (email, desktop, etc.)
        # For now, we just log them
        
        # Optionally send via WebSocket to connected clients
        if socketio:
            socketio.emit('notification', {
                'type': notification_type,
                'message': message,
                'timestamp': notification_data.get('timestamp'),
                'job': job_data
            })
    
    encoding_engine.add_notification_callback(handle_notification)
    encoding_engine.start()
    
    # Register API routes
    api_bp = init_api_routes(manager)
    app.register_blueprint(api_bp)
    
    # Register encoding API routes
    encoding_bp = create_encoding_routes(manager, encoding_engine)
    app.register_blueprint(encoding_bp)
    
    # Debug: Print registered routes
    logger.debug("Registered routes:")
    for rule in app.url_map.iter_rules():
        logger.debug(f"  {rule.rule} -> {rule.endpoint}")
    
    
    # Register settings API routes
    settings_bp = create_settings_routes(encoding_engine, socketio)
    app.register_blueprint(settings_bp)
    
    # Register template API routes
    template_bp = create_template_routes(encoding_engine.get_template_manager())
    app.register_blueprint(template_bp)
    
    # Register directory API routes
    from api.directory_routes import create_directory_routes
    directory_bp = create_directory_routes()
    app.register_blueprint(directory_bp)
    
    return app


def main() -> None:
    """Main entry point"""
    # Check for command line arguments
    directory: Optional[str] = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print("Usage: python3 app.py [directory] [--help]")
            print("  directory: Path to directory containing .img files")
            print("  --help: Show this help message")
            sys.exit(0)
        else:
            directory = sys.argv[1]
    
    # Create and configure app
    app_instance = create_app(directory)
    
    # Run the Flask app with SocketIO
    logger.info("Starting Disk Extractor - Movie Metadata Manager")
    logger.info(f"Access the web interface at: http://{Config.HOST}:{Config.PORT}")
    logger.info("Real-time file monitoring enabled")
    
    try:
        socketio.run(
            app_instance,
            host=Config.HOST, 
            port=Config.PORT, 
            debug=Config.DEBUG,
            allow_unsafe_werkzeug=True  # For development
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        # Clean up encoding engine
        encoding_engine.stop()
        # Clean up file watcher
        from utils.file_watcher import file_watcher
        file_watcher.stop_watching()
    except Exception as e:
        logger.error(f"Application error: {e}")
        # Clean up encoding engine
        encoding_engine.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()
