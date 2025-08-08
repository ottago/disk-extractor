"""
API routes for Disk Extractor

Contains all API endpoint handlers.
"""

import logging
from typing import Any
from flask import Blueprint, request, jsonify, Response

from utils.validation import validate_metadata_input, ValidationError
from utils.security import log_security_event
from utils.json_helpers import prepare_for_template
from models.metadata_manager import MovieMetadataManager

logger = logging.getLogger(__name__)


def init_api_routes(manager: MovieMetadataManager) -> Blueprint:
    """
    Initialize API routes with the metadata manager
    
    Args:
        manager: MovieMetadataManager instance
        
    Returns:
        Configured API blueprint
    """
    # Create API blueprint inside the function to avoid multiple registration issues
    api_bp = Blueprint('api', __name__, url_prefix='/api')
    
    @api_bp.route('/save_metadata', methods=['POST'])
    def save_metadata() -> Response:
        """Save metadata for a file"""
        try:
            # Handle potential JSON parsing errors
            try:
                data = request.get_json()
            except Exception as json_error:
                logger.warning(f"JSON parsing error: {json_error}")
                return jsonify({'success': False, 'error': 'Invalid JSON format'})
            
            if data is None:
                return jsonify({'success': False, 'error': 'No data provided'})
            
            if not isinstance(data, dict):
                return jsonify({'success': False, 'error': 'Invalid data format'})
            
            # Validate and sanitize input
            try:
                validated_data = validate_metadata_input(data)
            except ValidationError as e:
                log_security_event("Invalid metadata input", str(e), request.remote_addr)
                return jsonify({'success': False, 'error': str(e)})
            
            success = manager.save_metadata(validated_data['filename'], validated_data)
            return jsonify({'success': success})
            
        except Exception as e:
            logger.error(f"Error in save_metadata endpoint: {e}")
            return jsonify({'success': False, 'error': 'Internal server error'})
    
    @api_bp.route('/file_list')
    def file_list() -> Response:
        """Get updated file list with status"""
        try:
            # Don't scan directory here - rely on file watcher for updates
            # Only scan if the movies list is empty (initial load)
            if not manager.movies and manager.directory:
                logger.debug("Movies list empty, performing initial directory scan")
                manager.scan_directory()
            
            movies_data = prepare_for_template(manager.movies)
            return jsonify({'movies': movies_data})
        except Exception as e:
            logger.error(f"Error in file_list endpoint: {e}")
            return jsonify({'success': False, 'error': 'Internal server error'})
    
    @api_bp.route('/scan_file/<filename>')
    def scan_file(filename: str) -> Response:
        """API endpoint to trigger HandBrake scan for a specific file"""
        if not manager:
            return jsonify({'success': False, 'error': 'No directory configured'})
        
        try:
            # Clear cache to force rescan
            if filename in manager.handbrake_cache:
                del manager.handbrake_cache[filename]
            
            enhanced_metadata = manager.get_enhanced_metadata(filename)
            
            # Save the scan results to disk automatically
            # This preserves any existing metadata while updating with scan results
            # Load existing metadata first
            existing_metadata = manager.load_metadata(filename)
            
            # Update with enhanced metadata structure, preserving existing user data
            updated_metadata = {
                'file_name': filename,
                'size_mb': enhanced_metadata.get('size_mb', existing_metadata.get('size_mb', 0)),
                'titles': []
            }
            
            # Process each title from the enhanced metadata
            for enhanced_title in enhanced_metadata.get('titles', []):
                title_number = enhanced_title.get('title_number')
                
                # Find existing title data if any
                existing_title = None
                for existing in existing_metadata.get('titles', []):
                    if existing.get('title_number') == title_number:
                        existing_title = existing
                        break
                
                # Create updated title preserving user selections
                updated_title = {
                    'title_number': title_number,
                    'selected': existing_title.get('selected', False) if existing_title else False,
                    'movie_name': existing_title.get('movie_name', '') if existing_title else '',
                    'release_date': existing_title.get('release_date', '') if existing_title else '',
                    'synopsis': existing_title.get('synopsis', '') if existing_title else '',
                    'selected_audio_tracks': existing_title.get('selected_audio_tracks', []) if existing_title else [],
                    'selected_subtitle_tracks': existing_title.get('selected_subtitle_tracks', []) if existing_title else []
                }
                
                updated_metadata['titles'].append(updated_title)
            
            # Save the updated metadata to disk
            save_success = manager.save_metadata(filename, updated_metadata)
            if save_success:
                logger.info(f"Scan results saved to disk for: {filename}")
            else:
                msg = f"Failed to save scan results to disk for: {filename}"
                logger.warning(msg)
                return jsonify({
                    'success': False, 
                    'error': msg,
                    'filename': filename
                })
            
            metadata_data = prepare_for_template(enhanced_metadata)
            return jsonify({
                'success': True, 
                'metadata': metadata_data,
                'filename': filename
            })
        except ValidationError as e:
            log_security_event("Invalid filename in scan_file", f"{filename} - {e}", request.remote_addr)
            return jsonify({
                'success': False, 
                'error': str(e),
                'filename': filename
            })
        except FileNotFoundError:
            logger.error(f"File not found: {filename}")
            return jsonify({
                'success': False, 
                'error': 'File not found',
                'filename': filename
            })
        except PermissionError:
            logger.error(f"Permission denied: {filename}")
            return jsonify({
                'success': False, 
                'error': 'Permission denied',
                'filename': filename
            })
        except Exception as e:
            logger.error(f"Error scanning {filename}: {e}")
            return jsonify({
                'success': False, 
                'error': 'Internal server error',
                'filename': filename
            })
    
    @api_bp.route('/enhanced_metadata/<filename>')
    def enhanced_metadata(filename: str) -> Response:
        """API endpoint to get enhanced metadata for a file"""
        if not manager:
            return jsonify({'success': False, 'error': 'No directory configured'})
        
        try:
            enhanced_metadata = manager.get_enhanced_metadata(filename)
            metadata_data = prepare_for_template(enhanced_metadata)
            return jsonify({
                'success': True, 
                'metadata': metadata_data,
                'filename': filename
            })
        except ValidationError as e:
            log_security_event("Invalid filename in enhanced_metadata", f"{filename} - {e}", request.remote_addr)
            return jsonify({
                'success': False, 
                'error': str(e),
                'filename': filename
            })
        except FileNotFoundError:
            logger.error(f"File not found: {filename}")
            return jsonify({
                'success': False, 
                'error': 'File not found',
                'filename': filename
            })
        except PermissionError:
            logger.error(f"Permission denied: {filename}")
            return jsonify({
                'success': False, 
                'error': 'Permission denied',
                'filename': filename
            })
        except Exception as e:
            logger.error(f"Error getting metadata for {filename}: {e}")
            return jsonify({
                'success': False, 
                'error': 'Internal server error',
                'filename': filename
            })
    
    @api_bp.route('/raw_output/<filename>')
    def raw_output(filename: str) -> Response:
        """API endpoint to get raw HandBrake output for a file"""
        if not manager:
            return jsonify({'success': False, 'error': 'No directory configured'})
        
        try:
            # Validate filename
            from utils.validation import validate_filename
            filename = validate_filename(filename)
            
            # Check if we have cached HandBrake data for this file
            if filename in manager.handbrake_cache:
                cached_data = manager.handbrake_cache[filename]
                if '_raw_handbrake_output' in cached_data:
                    raw_data = cached_data['_raw_handbrake_output']
                    return jsonify({
                        'success': True,
                        'filename': filename,
                        'raw_output': raw_data,
                        'has_raw_data': True
                    })
                else:
                    return jsonify({
                        'success': True,
                        'message': 'No raw output available (file scanned before raw output saving was implemented)',
                        'filename': filename,
                        'has_raw_data': False,
                        'suggestion': 'Use the rescan button to generate raw output data'
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'File not scanned yet',
                    'filename': filename,
                    'suggestion': 'Scan the file first to generate raw output data'
                })
                
        except ValidationError as e:
            log_security_event("Invalid filename in raw_output", f"{filename} - {e}", request.remote_addr)
            return jsonify({
                'success': False,
                'error': str(e),
                'filename': filename
            })
        except Exception as e:
            logger.error(f"Error getting raw output for {filename}: {e}")
            return jsonify({
                'success': False,
                'error': 'Internal server error',
                'filename': filename
            })
    
    @api_bp.route('/handbrake/test')
    def test_handbrake() -> Response:
        """Test HandBrake functionality"""
        try:
            available = manager.test_handbrake()
            return jsonify({
                'available': available,
                'message': 'HandBrake is working' if available else 'HandBrake is not available'
            })
        except Exception as e:
            logger.error(f"Error testing HandBrake: {e}")
            return jsonify({
                'available': False,
                'message': 'Error testing HandBrake',
                'error': str(e)
            })
    
    return api_bp
