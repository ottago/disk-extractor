"""
API routes for encoding management

Provides REST endpoints for managing encoding jobs, queue, and settings.
"""

import logging
import os
from flask import Blueprint, request, jsonify, Response
from typing import Dict, Any, Union, List

from models.encoding_engine import EncodingEngine
from models.encoding_models import EncodingSettings, EncodingStatus, ExtendedMetadata
from utils.validation import validate_filename, ValidationError
from utils.json_helpers import prepare_for_template

logger = logging.getLogger(__name__)


def create_encoding_routes(metadata_manager, encoding_engine: EncodingEngine) -> Blueprint:
    """
    Create encoding API routes
    
    Args:
        metadata_manager: MovieMetadataManager instance
        encoding_engine: EncodingEngine instance
        
    Returns:
        Flask Blueprint with encoding routes
    """
    bp = Blueprint('encoding_api', __name__, url_prefix='/api/encoding')
    
    @bp.route('/queue', methods=['POST'])
    def queue_encoding() -> Union[Response, tuple]:
        """Queue a file for encoding"""
        try:
            logger.info(f"Received encoding queue request from {request.remote_addr}")
            
            data = request.get_json()
            if not data:
                logger.warning("No JSON data provided in encoding queue request")
                return jsonify({
                    'success': False,
                    'error': 'No JSON data provided'
                }), 400
            
            logger.debug(f"Queue encoding request data: {data}")
            
            # Validate required fields
            file_name = data.get('file_name', '').strip()
            title_number = data.get('title_number')
            movie_name = data.get('movie_name', '').strip()
            
            if not file_name:
                logger.warning("Missing file_name in encoding queue request")
                return jsonify({
                    'success': False,
                    'error': 'file_name is required'
                }), 400
            
            if title_number is None:
                logger.warning(f"Missing title_number in encoding queue request for file: {file_name}")
                return jsonify({
                    'success': False,
                    'error': 'title_number is required'
                }), 400
            
            if not movie_name:
                logger.warning(f"Missing movie_name in encoding queue request for file: {file_name}, title: {title_number}")
                return jsonify({
                    'success': False,
                    'error': 'movie_name is required'
                }), 400
            
            # Validate filename
            try:
                file_name = validate_filename(file_name)
            except ValidationError as e:
                logger.error(f"Filename validation failed for '{file_name}': {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Invalid filename: {str(e)}'
                }), 400
            
            # Validate title number
            try:
                title_number = int(title_number)
                if title_number < 1:
                    raise ValueError("Title number must be positive")
            except (ValueError, TypeError) as e:
                logger.error(f"Title number validation failed for '{title_number}': {str(e)}")
                return jsonify({
                    'success': False,
                    'error': 'title_number must be a positive integer'
                }), 400
            
            # Optional preset name
            # NKW preset_name = data.get('preset_name', '').strip()
            # NKW logger.debug(f"Using preset: {preset_name or 'default'}")
            
            # Check if file exists
            if not metadata_manager.directory:
                logger.error("No directory configured for metadata manager")
                return jsonify({
                    'success': False,
                    'error': 'No directory configured'
                }), 500
            
            img_path = metadata_manager.directory / file_name
            if not img_path.exists():
                logger.error(f"File not found: {img_path}")
                return jsonify({
                    'success': False,
                    'error': f'File not found: {file_name}'
                }), 404
            
            logger.info(f"Queuing encoding job: file={file_name}, title={title_number}, movie={movie_name}")
            
            # Queue the encoding job
            job_id = encoding_engine.queue_encoding_job(
                file_name=file_name,
                title_number=title_number,
                movie_name=movie_name
                # NKW preset_name=preset_name
            )
            
            logger.info(f"Successfully queued encoding job with ID: {job_id}")
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': f'Queued encoding job for {movie_name}'
            })
            
        except Exception as e:
            logger.error(f"Error queuing encoding job: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/queue/<job_id>', methods=['DELETE'])
    def remove_from_queue(job_id: str) -> Union[Response, tuple]:
        """Remove a job from the encoding queue"""
        try:
            success = encoding_engine.cancel_job(job_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Job {job_id} removed from queue'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Job {job_id} not found or cannot be cancelled'
                }), 404
                
        except Exception as e:
            logger.error(f"Error removing job from queue: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/cancel/<path:job_id>', methods=['POST'])
    def cancel_encoding(job_id: str) -> Union[Response, tuple]:
        """Cancel an active encoding job"""
        try:
            success = encoding_engine.cancel_job(job_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Job {job_id} cancelled'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Job {job_id} not found or cannot be cancelled'
                }), 404
                
        except Exception as e:
            logger.error(f"Error cancelling encoding job: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/status', methods=['GET'])
    def get_encoding_status() -> Union[Response, tuple]:
        """Get status of all encoding jobs"""
        try:
            jobs = encoding_engine.get_all_jobs()
            
            # Group jobs by status
            status_groups = {
                'encoding': [],
                'queued': [],
                'completed': [],
                'failed': [],
                'cancelled': []
            }
            
            # Get active job IDs for jobs that are currently active
            active_job_ids = {}
            with encoding_engine._lock:
                for job_id, active_job in encoding_engine.active_jobs.items():
                    job_key = f"{active_job.file_name}_{active_job.title_number}"
                    active_job_ids[job_key] = job_id
            
            # Get queued job IDs safely
            queued_job_ids = encoding_engine.get_queued_job_ids()
            
            for job in jobs:
                job_data = job.to_dict()
                
                # Add job_id for active, queued, or other jobs
                job_key = f"{job.file_name}_{job.title_number}"
                if job_key in active_job_ids:
                    job_data['job_id'] = active_job_ids[job_key]
                elif job_key in queued_job_ids:
                    job_data['job_id'] = queued_job_ids[job_key]
                
                if job.status == EncodingStatus.ENCODING:
                    status_groups['encoding'].append(job_data)
                elif job.status == EncodingStatus.QUEUED:
                    status_groups['queued'].append(job_data)
                elif job.status == EncodingStatus.COMPLETED:
                    status_groups['completed'].append(job_data)
                elif job.status == EncodingStatus.FAILED:
                    status_groups['failed'].append(job_data)
                elif job.status == EncodingStatus.CANCELLED:
                    status_groups['cancelled'].append(job_data)
            
            status_groups_data = prepare_for_template(status_groups)
            return jsonify({
                'success': True,
                'jobs': status_groups_data,
                'summary': {
                    'total_jobs': len(jobs),
                    'encoding_count': len(status_groups['encoding']),
                    'queued_count': len(status_groups['queued']),
                    'completed_count': len(status_groups['completed']),
                    'failed_count': len(status_groups['failed']),
                    'cancelled_count': len(status_groups['cancelled'])
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting encoding status: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/progress/<job_id>', methods=['GET'])
    def get_job_progress(job_id: str) -> Union[Response, tuple]:
        """Get progress for a specific job"""
        try:
            job = encoding_engine.get_job_status(job_id)
            
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'Job {job_id} not found'
                }), 404
            
            job_data = prepare_for_template(job.to_dict())
            return jsonify({
                'success': True,
                'job': job_data
            })
            
        except Exception as e:
            logger.error(f"Error getting job progress: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/file/<file_name>/jobs', methods=['GET'])
    def get_file_encoding_jobs(file_name: str) -> Union[Response, tuple]:
        """Get all encoding jobs for a specific file"""
        try:
            logger.info(f"get_file_encoding_jobs file_name={file_name}")
            # Validate filename
            try:
                file_name = validate_filename(file_name)
            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid filename: {str(e)}'
                }), 400
            
            # Load metadata
            metadata = metadata_manager.load_metadata(file_name)
            jobs = ExtendedMetadata.get_encoding_jobs(metadata)
            history = ExtendedMetadata.get_encoding_history(metadata)
            file_status = ExtendedMetadata.get_file_encoding_status(metadata)
            
            return jsonify({
                'success': True,
                'file_name': file_name,
                'status': file_status.value,
                'jobs': [job.to_dict() for job in jobs],
                'history': [entry.to_dict() for entry in history]
            })
            
        except Exception as e:
            logger.error(f"Error getting file encoding jobs: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/queue/bulk', methods=['POST'])
    def bulk_queue_operations() -> Union[Response, tuple]:
        """Perform bulk queue operations"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No JSON data provided'
                }), 400
            
            operation = data.get('operation', '').strip().lower()
            file_names = data.get('file_names', [])

            logger.info(f"bulk_queue_operations operation={operation} file_names={file_names}")
            
            if operation not in ['queue_all', 'clear_queue']:
                return jsonify({
                    'success': False,
                    'error': 'Invalid operation. Must be "queue_all" or "clear_queue"'
                }), 400
            
            results = []
            
            if operation == 'queue_all':
                if not file_names:
                    return jsonify({
                        'success': False,
                        'error': 'file_names list is required for queue_all operation'
                    }), 400
                
                # Queue all files with selected titles
                for file_name in file_names:
                    try:
                        file_name = validate_filename(file_name)
                        metadata = metadata_manager.load_metadata(file_name)
                        
                        # Find selected titles
                        for title in metadata.get('titles', []):
                            if title.get('selected', False) and title.get('movie_name', '').strip():
                                job_id = encoding_engine.queue_encoding_job(
                                    file_name=file_name,
                                    title_number=title.get('title_number', 1),
                                    movie_name=title.get('movie_name', ''),
                                    preset_name=None
                                )
                                results.append({
                                    'file_name': file_name,
                                    'title_number': title.get('title_number', 1),
                                    'job_id': job_id,
                                    'success': True
                                })
                    except Exception as e:
                        results.append({
                            'file_name': file_name,
                            'success': False,
                            'error': str(e)
                        })
            
            elif operation == 'clear_queue':
                # Cancel all queued jobs
                jobs = encoding_engine.get_all_jobs()
                for job in jobs:
                    if job.status == EncodingStatus.QUEUED:
                        job_id = f"{job.file_name}_{job.title_number}"
                        success = encoding_engine.cancel_job(job_id)
                        results.append({
                            'job_id': job_id,
                            'success': success
                        })
            
            return jsonify({
                'success': True,
                'operation': operation,
                'results': results,
                'total_processed': len(results)
            })
            
        except Exception as e:
            logger.error(f"Error in bulk queue operation: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/failure-logs/<path:file_name>/<int:title_number>', methods=['GET'])
    def get_failure_logs(file_name: str, title_number: int) -> Union[Response, tuple]:
        """Get failure logs for a specific failed encoding job"""
        try:
            # Validate filename
            file_name = validate_filename(file_name)
            
            # Find the failed job
            all_jobs = encoding_engine.get_all_jobs()
            failed_job = None
            
            for job in all_jobs:
                if (job.file_name == file_name and 
                    job.title_number == title_number and 
                    job.status == EncodingStatus.FAILED):
                    failed_job = job
                    break
            
            if not failed_job:
                return jsonify({
                    'success': False,
                    'error': 'Failed job not found'
                }), 404
            
            return jsonify({
                'success': True,
                'job': {
                    'file_name': failed_job.file_name,
                    'title_number': failed_job.title_number,
                    'movie_name': failed_job.movie_name,
                    'error_message': failed_job.error_message,
                    'failure_logs': failed_job.failure_logs or [],
                    'failed_at': failed_job.completed_at,
                    'preset_name': failed_job.preset_name
                }
            })
            
        except ValidationError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid filename: {str(e)}'
            }), 400
        except Exception as e:
            logger.error(f"Error getting failure logs: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/clear-failure/<path:file_name>/<int:title_number>', methods=['POST'])
    def clear_failure(file_name: str, title_number: int) -> Union[Response, tuple]:
        """Clear a failed job so it can be retried"""
        try:
            # Validate filename
            file_name = validate_filename(file_name)
            
            if not metadata_manager:
                return jsonify({
                    'success': False,
                    'error': 'Metadata manager not available'
                }), 500
            
            # Load metadata
            metadata = metadata_manager.load_metadata(file_name)
            jobs = ExtendedMetadata.get_encoding_jobs(metadata)
            
            # Find and remove the failed job
            job_removed = False
            updated_jobs = []
            
            for job in jobs:
                if (job.file_name == file_name and 
                    job.title_number == title_number and 
                    job.status == EncodingStatus.FAILED):
                    # Skip this job (remove it)
                    job_removed = True
                    logger.info(f"Cleared failed job: {file_name} title {title_number}")
                else:
                    updated_jobs.append(job)
            
            if not job_removed:
                return jsonify({
                    'success': False,
                    'error': 'Failed job not found'
                }), 404
            
            # Update metadata with the cleaned job list
            metadata = ExtendedMetadata.set_encoding_jobs(metadata, updated_jobs)
            metadata_manager.save_metadata(file_name, metadata)
            
            # Invalidate encoding engine cache
            encoding_engine._invalidate_jobs_cache()
            
            return jsonify({
                'success': True,
                'message': f'Failed job cleared for {file_name} title {title_number}'
            })
            
        except ValidationError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid filename: {str(e)}'
            }), 400
        except Exception as e:
            logger.error(f"Error clearing failure: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/test-endpoint', methods=['POST'])
    def test_endpoint() -> Union[Response, tuple]:
        """Test endpoint to debug the issue"""
        logger.info("Test endpoint called")
        try:
            data = request.get_json()
            logger.info(f"Received data: {data}")
            
            return jsonify({
                'success': True,
                'message': 'Test endpoint working',
                'received_data': data
            })
            
        except Exception as e:
            logger.error(f"Error in test endpoint: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/output-file-size', methods=['POST'])
    def get_output_file_size() -> Union[Response, tuple]:
        """Get the size of an output file"""
        try:
            data = request.get_json()
            if not data or 'output_path' not in data:
                return jsonify({
                    'success': False,
                    'error': 'output_path is required'
                }), 400
            
            output_path = data['output_path']
            
            # Check if file exists and get its size
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                return jsonify({
                    'success': True,
                    'file_size': file_size,
                    'file_path': output_path
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Output file not found: {output_path}'
                }), 404
                
        except Exception as e:
            logger.error(f"Error getting output file size: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('/delete-file', methods=['POST'])
    def delete_encoded_file() -> Union[Response, tuple]:
        """Delete an encoded file and reset its encoding status"""
        logger.info("Delete encoded file endpoint called")
        try:
            data = request.get_json()
            logger.info(f"Received data: {data}")
            
            if not data or 'file_path' not in data:
                logger.warning("Missing file_path in request data")
                return jsonify({
                    'success': False,
                    'error': 'file_path is required'
                }), 400
            
            file_path = data['file_path']
            logger.info(f"Processing file_path: {file_path}")
            
            # Basic path validation (don't use validate_filename as it's for different purpose)
            if not file_path or '..' in file_path:
                logger.warning(f"Invalid file path: {file_path}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid file path'
                }), 400
            
            # Ensure the path is absolute (as it should be from the job output_path)
            if not os.path.isabs(file_path):
                logger.warning(f"File path is not absolute: {file_path}")
                return jsonify({
                    'success': False,
                    'error': 'File path must be absolute'
                }), 400
            
            # Extract filename from path for metadata operations
            file_name = os.path.basename(file_path)
            file_already_missing = False
            file_size = 0
            
            # Check if file exists and get info
            if os.path.exists(file_path):
                # Additional safety check - ensure it's a regular file
                if not os.path.isfile(file_path):
                    logger.warning(f"Path is not a file: {file_path}")
                    return jsonify({
                        'success': False,
                        'error': 'Path is not a file'
                    }), 400
                
                # Get file info before deletion
                file_size = os.path.getsize(file_path)
                
                # Delete the file
                os.remove(file_path)
                logger.info(f"Deleted encoded file: {file_path} ({file_size} bytes)")
            else:
                # File doesn't exist - that's okay, we'll still clear the job status
                file_already_missing = True
                logger.info(f"File already missing: {file_path} - will clear job status anyway")
            
            # Now clear the completed job status from metadata so it can be re-encoded
            # We need to find the source file and title number from the output path
            # This is a bit tricky since we only have the output path
            
            # Try to find the job in metadata by matching output paths
            job_cleared = False
            if metadata_manager:
                try:
                    # Search through all movies to find the job with this output path
                    for movie in metadata_manager.movies:
                        try:
                            metadata = metadata_manager.load_metadata(movie['file_name'])
                            jobs = ExtendedMetadata.get_encoding_jobs(metadata)
                            
                            # Find and remove completed jobs with matching output path
                            updated_jobs = []
                            for job in jobs:
                                if (job.output_path == file_path and 
                                    job.status == EncodingStatus.COMPLETED):
                                    # Skip this job (remove it)
                                    job_cleared = True
                                    logger.info(f"Cleared completed job: {job.file_name} title {job.title_number}")
                                else:
                                    updated_jobs.append(job)
                            
                            # Update metadata if we found and removed a job
                            if job_cleared:
                                metadata = ExtendedMetadata.set_encoding_jobs(metadata, updated_jobs)
                                metadata_manager.save_metadata(movie['file_name'], metadata)
                                
                                # Invalidate encoding engine cache
                                if hasattr(encoding_engine, '_invalidate_jobs_cache'):
                                    encoding_engine._invalidate_jobs_cache()
                                
                                break  # Found and cleared the job, no need to continue
                                
                        except Exception as e:
                            logger.warning(f"Error checking jobs in {movie['file_name']}: {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error clearing job status: {e}")
            
            # Prepare response message
            if file_already_missing and job_cleared:
                message = f'File was already removed and job status cleared. You can now re-encode this title.'
            elif file_already_missing:
                message = f'File was already removed. You can now re-encode this title.'
            elif job_cleared:
                message = f'Successfully deleted {file_name} and cleared job status. You can now re-encode this title.'
            else:
                message = f'Successfully deleted {file_name}.'
            
            return jsonify({
                'success': True,
                'message': message,
                'file_name': file_name,
                'file_size': file_size,
                'file_already_missing': file_already_missing,
                'job_status_cleared': job_cleared
            })
            
        except PermissionError:
            logger.error(f"Permission denied deleting file: {file_path}")
            return jsonify({
                'success': False,
                'error': 'Permission denied - cannot delete file'
            }), 403
        except Exception as e:
            logger.error(f"Error deleting encoded file: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
            
        except PermissionError:
            logger.error(f"Permission denied deleting file: {file_path}")
            return jsonify({
                'success': False,
                'error': 'Permission denied - cannot delete file'
            }), 403
        except Exception as e:
            logger.error(f"Error deleting encoded file: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    return bp


def create_settings_routes(encoding_engine: EncodingEngine, socketio=None) -> Blueprint:
    """
    Create encoding settings API routes
    
    Args:
        encoding_engine: EncodingEngine instance
        
    Returns:
        Flask Blueprint with settings routes
    """
    bp = Blueprint('settings_api', __name__, url_prefix='/api/settings')
    
    @bp.route('', methods=['GET'])
    def get_settings() -> Union[Response, tuple]:
        """Get current encoding settings"""
        try:
            settings = encoding_engine.get_settings()
            return jsonify({
                'success': True,
                'settings': settings.to_dict()
            })
            
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    @bp.route('', methods=['POST'])
    def update_settings() -> Union[Response, tuple]:
        """Update encoding settings"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No JSON data provided'
                }), 400
            
            # Validate settings
            try:
                # Get current settings as base
                current_settings = encoding_engine.get_settings()
                settings_dict = current_settings.to_dict()
                
                # Update with provided values
                settings_dict.update(data)
                
                # Validate specific fields
                if 'max_concurrent_encodes' in settings_dict:
                    max_concurrent = int(settings_dict['max_concurrent_encodes'])
                    if max_concurrent < 1 or max_concurrent > 8:
                        return jsonify({
                            'success': False,
                            'error': 'max_concurrent_encodes must be between 1 and 8'
                        }), 400
                    settings_dict['max_concurrent_encodes'] = max_concurrent
                
                if 'test_duration_seconds' in settings_dict:
                    test_duration = int(settings_dict['test_duration_seconds'])
                    if test_duration < 10 or test_duration > 600:
                        return jsonify({
                            'success': False,
                            'error': 'test_duration_seconds must be between 10 and 600'
                        }), 400
                    settings_dict['test_duration_seconds'] = test_duration
                
                if 'progress_update_interval' in settings_dict:
                    update_interval = int(settings_dict['progress_update_interval'])
                    if update_interval < 1 or update_interval > 10:
                        return jsonify({
                            'success': False,
                            'error': 'progress_update_interval must be between 1 and 10'
                        }), 400
                    settings_dict['progress_update_interval'] = update_interval
                
                # Create new settings object
                new_settings = EncodingSettings.from_dict(settings_dict)
                
                # Update encoding engine
                encoding_engine.update_settings(new_settings)
                
                # Notify clients via WebSocket if available
                if socketio:
                    socketio.emit('settings_updated', {
                        'settings': new_settings.to_dict()
                    })
                
                return jsonify({
                    'success': True,
                    'message': 'Settings updated successfully',
                    'settings': new_settings.to_dict()
                })
                
            except (ValueError, TypeError) as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid settings data: {str(e)}'
                }), 400
            
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500
    
    return bp
