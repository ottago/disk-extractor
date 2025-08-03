"""
Security utilities for Disk Extractor

Provides security-related helper functions.
"""

import subprocess
import logging
from typing import Optional
from flask import Response
from config import SECURITY_HEADERS, API_CACHE_HEADERS

logger = logging.getLogger(__name__)


def safe_decode_subprocess_output(output_bytes: Optional[bytes]) -> str:
    """
    Safely decode subprocess output, handling various encodings
    
    Args:
        output_bytes: Raw subprocess output
        
    Returns:
        Decoded string
    """
    if not output_bytes:
        return ""
    
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    for encoding in encodings:
        try:
            return output_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    # If all else fails, decode with errors='replace'
    return output_bytes.decode('utf-8', errors='replace')


def apply_security_headers(response: Response, is_api_endpoint: bool = False) -> Response:
    """
    Apply security headers to Flask response
    
    Args:
        response: Flask response object
        is_api_endpoint: Whether this is an API endpoint
        
    Returns:
        Flask response object with security headers
    """
    # Apply standard security headers
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    
    # Apply cache control for API endpoints
    if is_api_endpoint:
        for header, value in API_CACHE_HEADERS.items():
            response.headers[header] = value
    
    return response


def check_path_traversal(path: str) -> bool:
    """
    Check if a path contains path traversal attempts
    
    Args:
        path: Path to check
        
    Returns:
        True if path traversal detected
    """
    if not path:
        return False
    
    suspicious_patterns = ['../', '..\\', '%2e%2e%2f', '%2e%2e%5c', '%2e%2e/', '..%2f', '..%5c']
    path_lower = path.lower()
    
    return any(pattern in path_lower for pattern in suspicious_patterns)


def log_security_event(event_type: str, details: str, remote_addr: Optional[str] = None) -> None:
    """
    Log security-related events
    
    Args:
        event_type: Type of security event
        details: Event details
        remote_addr: Remote IP address
    """
    log_msg = f"SECURITY: {event_type} - {details}"
    if remote_addr:
        log_msg += f" from {remote_addr}"
    
    logger.warning(log_msg)
