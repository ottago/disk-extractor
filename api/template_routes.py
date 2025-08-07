"""
API routes for HandBrake template management

Provides REST endpoints for uploading, managing, and using HandBrake templates.
"""

import json
import logging
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename
from typing import Dict, Any, Union

from models.template_manager import TemplateManager
from utils.validation import ValidationError
from utils.json_helpers import prepare_for_template

logger = logging.getLogger(__name__)


def create_template_routes(template_manager: TemplateManager) -> Blueprint:
    """
    Create template management API routes
    
    Args:
        template_manager: TemplateManager instance
        
    Returns:
        Flask Blueprint with template routes
    """
    bp = Blueprint('template_api', __name__, url_prefix='/api/templates')
    
    @bp.route('', methods=['GET'])
    def list_templates() -> Union[Response, tuple]:
        """Get list of all available templates"""
        try:
            templates = template_manager.list_templates()
            return jsonify({
                'success': True,
                'templates': templates
            })
            
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/upload', methods=['POST'])
    def upload_template() -> Union[Response, tuple]:
        """Upload a new HandBrake template"""
        try:
            # Check if file was uploaded
            if 'template' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'No template file provided'
                }), 400
            
            file = request.files['template']
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'No file selected'
                }), 400
            
            # Validate file type
            if not file.filename.lower().endswith('.json'):
                return jsonify({
                    'success': False,
                    'error': 'Template must be a .json file'
                }), 400
            
            # Read and parse JSON
            try:
                template_data = json.loads(file.read().decode('utf-8'))
            except json.JSONDecodeError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid JSON format: {str(e)}'
                }), 400
            except UnicodeDecodeError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid file encoding: {str(e)}'
                }), 400
            
            # Extract template name
            template_name = template_data.get('PresetName')
            if not template_name:
                return jsonify({
                    'success': False,
                    'error': 'Template missing PresetName field'
                }), 400
            
            # Sanitize template name
            template_name = secure_filename(template_name)
            if not template_name:
                return jsonify({
                    'success': False,
                    'error': 'Invalid template name'
                }), 400
            
            # Save template
            success = template_manager.save_template(template_name, template_data)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Template "{template_name}" uploaded successfully',
                    'template_name': template_name
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save template'
                }), 500
                
        except Exception as e:
            logger.error(f"Error uploading template: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/<template_name>', methods=['GET'])
    def get_template(template_name: str) -> Union[Response, tuple]:
        """Get details of a specific template"""
        try:
            template = template_manager.get_template(template_name)
            
            if not template:
                return jsonify({
                    'success': False,
                    'error': f'Template "{template_name}" not found'
                }), 404
            
            return jsonify({
                'success': True,
                'template': {
                    'name': template.name,
                    'description': template.description,
                    'category': template.category,
                    'video_encoder': template.get_video_encoder(),
                    'audio_encoder': template.get_audio_encoder(),
                    'container': template.container_settings,
                    'file_extension': template.get_file_extension(),
                    'supports_chapters': template.supports_chapters(),
                    'video_quality': template.video_quality,
                    'two_pass': template.two_pass
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting template: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/<template_name>', methods=['DELETE'])
    def delete_template(template_name: str) -> Union[Response, tuple]:
        """Delete a template"""
        try:
            success = template_manager.delete_template(template_name)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Template "{template_name}" deleted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Template "{template_name}" not found'
                }), 404
                
        except Exception as e:
            logger.error(f"Error deleting template: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/validate', methods=['POST'])
    def validate_template() -> Union[Response, tuple]:
        """Validate a template without saving it"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No JSON data provided'
                }), 400
            
            template_data = data.get('template_data')
            if not template_data:
                return jsonify({
                    'success': False,
                    'error': 'No template_data provided'
                }), 400
            
            # Validate template
            is_valid = template_manager._validate_template(template_data)
            
            if is_valid:
                # Extract template info for preview
                template_name = template_data.get('PresetName', 'Unknown')
                template_description = template_data.get('PresetDescription', '')
                video_encoder = template_data.get('VideoEncoder', 'Unknown')
                
                return jsonify({
                    'success': True,
                    'valid': True,
                    'template_info': {
                        'name': template_name,
                        'description': template_description,
                        'video_encoder': video_encoder
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'valid': False,
                    'error': 'Template validation failed'
                })
                
        except Exception as e:
            logger.error(f"Error validating template: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/preview-command', methods=['POST'])
    def preview_command() -> Union[Response, tuple]:
        """Preview HandBrake command that would be generated"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No JSON data provided'
                }), 400
            
            # Extract parameters
            template_name = data.get('template_name', '')
            file_name = data.get('file_name', 'example.img')
            title_number = data.get('title_number', 1)
            movie_name = data.get('movie_name', 'Example Movie')
            testing_mode = data.get('testing_mode', False)
            test_duration = data.get('test_duration', 60)
            
            # Generate output filename
            output_filename = template_manager.generate_output_filename(
                movie_name, '', template_name
            )
            
            # Build command (using dummy paths for preview)
            from pathlib import Path
            input_path = Path('/movies') / file_name
            output_path = Path('/output') / output_filename
            
            cmd = template_manager.build_handbrake_command(
                input_file=input_path,
                output_file=output_path,
                template_name=template_name,
                title_number=title_number,
                testing_mode=testing_mode,
                test_duration=test_duration
            )
            
            return jsonify({
                'success': True,
                'command': cmd,
                'command_string': ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd),
                'output_filename': output_filename
            })
            
        except Exception as e:
            logger.error(f"Error previewing command: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    return bp
