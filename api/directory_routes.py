"""
API routes for directory browsing

Provides REST endpoints for browsing directories on the server.
"""

import os
import logging
from flask import Blueprint, request, jsonify, Response
from pathlib import Path
from typing import Dict, Any, Union, List

logger = logging.getLogger(__name__)

def create_directory_routes() -> Blueprint:
    """Create and configure directory routes"""
    bp = Blueprint('directory', __name__, url_prefix='/api/directory')
    
    @bp.route('/browse', methods=['POST'])
    def browse_directory() -> Union[Response, tuple]:
        """Browse directories on the server"""
        try:
            data = request.get_json()
            requested_path = data.get('path', '')
            
            # Security: Only allow browsing within /movies
            movies_root = Path('/movies').resolve()
            
            # If no path provided or empty, start at movies root
            if not requested_path or requested_path.strip() == '':
                requested_path = '/movies'
            
            # If path doesn't start with /movies, prepend it
            if not requested_path.startswith('/movies'):
                # Treat as relative path within /movies
                if requested_path.startswith('/'):
                    requested_path = requested_path[1:]  # Remove leading slash
                requested_path = f'/movies/{requested_path}'
            
            path_obj = Path(requested_path).resolve()
            
            # Security check: ensure path is within /movies
            try:
                path_obj.relative_to(movies_root)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Access denied: Path must be within the movies directory'
                }), 403
            
            if not path_obj.exists():
                return jsonify({
                    'success': False,
                    'error': 'Directory does not exist'
                }), 404
            
            if not path_obj.is_dir():
                return jsonify({
                    'success': False,
                    'error': 'Path is not a directory'
                }), 400
            
            # Get directory contents
            directories = []
            try:
                for item in sorted(path_obj.iterdir()):
                    if item.is_dir():
                        directories.append({
                            'name': item.name,
                            'path': str(item),
                            'is_writable': os.access(item, os.W_OK)
                        })
            except PermissionError:
                return jsonify({
                    'success': False,
                    'error': 'Permission denied to read directory'
                }), 403
            
            # Get parent directory (only if not at movies root)
            parent_path = None
            if path_obj != movies_root and path_obj.parent != path_obj:
                parent_path = str(path_obj.parent)
            
            # Convert absolute paths to relative paths for display
            def to_relative_path(abs_path):
                """Convert absolute path to relative path from /movies"""
                try:
                    rel_path = Path(abs_path).relative_to(movies_root)
                    return '/' + str(rel_path) if str(rel_path) != '.' else '/'
                except ValueError:
                    return abs_path  # Fallback to absolute if conversion fails
            
            current_display_path = to_relative_path(str(path_obj))
            parent_display_path = to_relative_path(parent_path) if parent_path else None
            
            return jsonify({
                'success': True,
                'current_path': str(path_obj),  # Keep absolute for internal use
                'current_display_path': current_display_path,  # Relative for display
                'parent_path': parent_path,  # Keep absolute for internal use
                'parent_display_path': parent_display_path,  # Relative for display
                'directories': directories
            })
            
        except Exception as e:
            logger.error(f"Error browsing directory: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    return bp
