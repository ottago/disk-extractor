"""
Input validation utilities for Disk Extractor

Provides secure validation functions for user inputs.
"""

import string
from urllib.parse import unquote
from typing import Dict, Any, Optional, Union
from config import Config


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def validate_filename(filename: str) -> str:
    """
    Validate filename to prevent path traversal and ensure it's a valid .img file
    
    Args:
        filename: The filename to validate
        
    Returns:
        The validated filename
        
    Raises:
        ValidationError: If filename is invalid or potentially malicious
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    # URL decode the filename first
    filename = unquote(filename)
    
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValidationError("Invalid filename: path traversal detected")
    
    # Check for null bytes (another common attack vector)
    if '\x00' in filename:
        raise ValidationError("Invalid filename: null byte detected")
    
    # Ensure it's a valid .img file
    if not filename.lower().endswith('.img'):
        raise ValidationError("Invalid filename: only .img files are allowed")
    
    # Check filename length
    if len(filename) > Config.MAX_FILENAME_LENGTH:
        raise ValidationError("Invalid filename: filename too long")
    
    # Check for valid characters
    if not all(c in Config.ALLOWED_FILENAME_CHARS for c in filename[:-4]):  # Exclude .img extension
        raise ValidationError("Invalid filename: contains invalid characters")
    
    return filename


def sanitize_string(value: Any, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input by removing dangerous characters and limiting length
    
    Args:
        value: The value to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return ''
    
    # Remove null bytes and strip whitespace
    sanitized = value.replace('\x00', '').strip()
    
    # Apply length limit if specified
    if max_length is not None:
        sanitized = sanitized[:max_length]
    
    return sanitized


def validate_metadata_input(data: Any) -> Dict[str, Any]:
    """
    Validate metadata input structure and content
    
    Args:
        data: The metadata to validate
        
    Returns:
        Validated and sanitized metadata
        
    Raises:
        ValidationError: If data is invalid
    """
    if not isinstance(data, dict):
        raise ValidationError("Metadata must be a dictionary")
    
    filename = data.get('filename')
    if not filename:
        raise ValidationError("Filename is required")
    
    # Validate filename
    filename = validate_filename(filename)
    
    # Validate titles structure
    titles = data.get('titles', [])
    if not isinstance(titles, list):
        raise ValidationError("Titles must be a list")
    
    # Sanitize string fields
    validated_data: Dict[str, Any] = {
        'filename': filename,
        'file_name': filename,
        'movie_name': sanitize_string(data.get('movie_name', ''), Config.MAX_MOVIE_NAME_LENGTH),
        'release_date': sanitize_string(data.get('release_date', ''), 10),  # YYYY-MM-DD format
        'synopsis': sanitize_string(data.get('synopsis', ''), Config.MAX_SYNOPSIS_LENGTH),
        'titles': titles
    }
    
    return validated_data


def validate_year(year_str: str) -> str:
    """
    Validate year string
    
    Args:
        year_str: Year string to validate
        
    Returns:
        Validated year or empty string
    """
    if not year_str:
        return ''
    
    year_str = year_str.strip()
    
    # Check if it's a 4-digit year
    if len(year_str) == 4 and year_str.isdigit():
        year = int(year_str)
        # Reasonable year range
        if 1900 <= year <= 2100:
            return year_str
    
    return ''
