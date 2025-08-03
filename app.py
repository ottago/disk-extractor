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
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Import our modules
from config import Config
from models.metadata_manager import MovieMetadataManager, MetadataError
from api.routes import init_api_routes
from utils.security import apply_security_headers, check_path_traversal, log_security_event

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Global manager instance
manager = MovieMetadataManager()


# Security middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    is_api_endpoint = request.endpoint and request.endpoint.startswith('api.')
    return apply_security_headers(response, is_api_endpoint)


@app.before_request
def check_security():
    """Check for security issues in requests"""
    if request.path.startswith('/api/'):
        # Check for path traversal attempts
        if check_path_traversal(request.path):
            log_security_event("Path traversal attempt", request.path, request.remote_addr)
            return jsonify({
                'success': False,
                'error': 'Invalid filename: path traversal detected'
            }), 400


@app.errorhandler(404)
def handle_404(error):
    """Handle 404 errors, especially for API endpoints with malicious paths"""
    if request.path.startswith('/api/'):
        # For API endpoints, return JSON error instead of HTML
        return jsonify({
            'success': False,
            'error': 'Invalid filename: path traversal detected'
        }), 400
    
    # For non-API endpoints, return normal 404
    return error


# Main routes
@app.route('/')
def index():
    """Main interface"""
    if not manager.directory:
        return redirect(url_for('setup'))
    
    return render_template('index.html', 
                         movies=manager.movies, 
                         directory=str(manager.directory))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
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
def health():
    """Health check endpoint"""
    try:
        handbrake_available = manager.test_handbrake()
        cache_stats = manager.get_cache_stats()
        
        return jsonify({
            'status': 'ok',
            'handbrake': 'available' if handbrake_available else 'unavailable',
            'directory': str(manager.directory) if manager.directory else None,
            'movie_count': len(manager.movies),
            'cache_stats': cache_stats,
            'config': {
                'handbrake_timeout': Config.HANDBRAKE_TIMEOUT,
                'max_cache_size': Config.MAX_CACHE_SIZE,
                'cache_ttl': Config.CACHE_TTL
            }
        })
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


def create_app(directory=None):
    """
    Application factory function
    
    Args:
        directory (str, optional): Initial directory to use
        
    Returns:
        Flask: Configured Flask application
    """
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
    
    # Register API routes
    api_bp = init_api_routes(manager)
    app.register_blueprint(api_bp)
    
    return app


def main():
    """Main entry point"""
    # Check for command line arguments
    directory = None
    
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
    
    # Run the Flask app
    logger.info("Starting Disk Extractor - Movie Metadata Manager")
    logger.info(f"Access the web interface at: http://{Config.HOST}:{Config.PORT}")
    
    try:
        app_instance.run(
            host=Config.HOST, 
            port=Config.PORT, 
            debug=Config.DEBUG
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
