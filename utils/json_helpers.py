"""
JSON serialization helpers for Disk Extractor

Handles serialization of custom objects like enums, dataclasses, etc.
"""

import json
from enum import Enum
from dataclasses import is_dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union


def make_json_serializable(obj: Any) -> Any:
    """
    Convert objects to JSON-serializable format
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    if obj is None:
        return None
    
    # Handle enums
    if isinstance(obj, Enum):
        return obj.value
    
    # Handle dataclasses
    if is_dataclass(obj):
        return make_json_serializable(asdict(obj))
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle Path objects
    if isinstance(obj, Path):
        return str(obj)
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    
    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    
    # Handle sets
    if isinstance(obj, set):
        return [make_json_serializable(item) for item in obj]
    
    # Return primitive types as-is
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # For other objects, try to convert to string
    try:
        return str(obj)
    except Exception:
        return f"<{type(obj).__name__} object>"


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize object to JSON string
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments for json.dumps
        
    Returns:
        JSON string
    """
    serializable_obj = make_json_serializable(obj)
    return json.dumps(serializable_obj, **kwargs)


def prepare_for_template(data: Any) -> Any:
    """
    Prepare data for use in Jinja2 templates
    
    This ensures all objects can be serialized by the template's tojson filter.
    
    Args:
        data: Data to prepare
        
    Returns:
        Template-safe version of the data
    """
    return make_json_serializable(data)
