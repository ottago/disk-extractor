"""
Configuration management for Disk Extractor

Centralizes all configuration settings and constants.
"""

import os
from pathlib import Path


class Config:
    """Application configuration settings"""
    
    # HandBrake settings
    HANDBRAKE_TIMEOUT = int(os.getenv('HANDBRAKE_TIMEOUT', 120))
    # Try Docker path first, then local path
    _handbrake_paths = ['/usr/local/bin/HandBrakeCLI', '/usr/bin/HandBrakeCLI']
    HANDBRAKE_CLI_PATH = os.getenv('HANDBRAKE_CLI_PATH')
    if not HANDBRAKE_CLI_PATH:
        for path in _handbrake_paths:
            if os.path.exists(path):
                HANDBRAKE_CLI_PATH = path
                break
        else:
            HANDBRAKE_CLI_PATH = _handbrake_paths[0]  # Default to Docker path
    
    # Cache settings
    MAX_CACHE_SIZE = int(os.getenv('MAX_CACHE_SIZE', 100))
    CACHE_TTL = int(os.getenv('CACHE_TTL', 3600))  # 1 hour
    
    # File settings
    ALLOWED_EXTENSIONS = ['.img']
    MAX_FILENAME_LENGTH = 255
    MAX_SYNOPSIS_LENGTH = 5000
    MAX_MOVIE_NAME_LENGTH = 1000
    
    # Security settings
    ALLOWED_FILENAME_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.()[]'
    
    # Title suggestion settings
    MIN_TITLE_DURATION_MINUTES = 10  # Skip titles shorter than this (likely trailers)
    MIN_COLLAPSED_DURATION_SECONDS = 1800  # 30 minutes - collapse shorter titles by default
    
    # Flask settings
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # Logging settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate configuration settings"""
        errors = []
        
        if cls.HANDBRAKE_TIMEOUT <= 0:
            errors.append("HANDBRAKE_TIMEOUT must be positive")
        
        if cls.MAX_CACHE_SIZE <= 0:
            errors.append("MAX_CACHE_SIZE must be positive")
        
        if cls.MIN_TITLE_DURATION_MINUTES < 0:
            errors.append("MIN_TITLE_DURATION_MINUTES must be non-negative")
        
        if not Path(cls.HANDBRAKE_CLI_PATH).exists():
            errors.append(f"HandBrake CLI not found at {cls.HANDBRAKE_CLI_PATH}")
        
        if errors:
            raise ValueError("Configuration errors: " + "; ".join(errors))
        
        return True


# Security headers configuration
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "media-src 'self'; "
        "frame-src 'none';"
    )
}

# API cache control headers
API_CACHE_HEADERS = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0'
}
