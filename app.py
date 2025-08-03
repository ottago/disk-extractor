#!/usr/bin/env python3
"""
Disk Extractor - Movie Metadata Manager

A web-based application for managing movie metadata stored in .mmm files 
alongside .img movie files, with HandBrake integration for video processing.
"""

import os
import sys
import json
import subprocess
import logging
import re
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from urllib.parse import unquote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Security: Add security headers to all responses
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # Prevent XSS attacks
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Content Security Policy to prevent XSS
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # Allow inline scripts for now
        "style-src 'self' 'unsafe-inline'; "   # Allow inline styles
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "media-src 'self'; "
        "frame-src 'none';"
    )
    
    # Prevent caching of sensitive data
    if request.endpoint and request.endpoint.startswith('api'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response

# Security: Check for path traversal attempts in all requests
@app.before_request
def check_path_traversal():
    """Check for path traversal attempts in request paths"""
    if request.path.startswith('/api/'):
        # Check for obvious path traversal patterns in the URL
        suspicious_patterns = ['../', '..\\', '%2e%2e%2f', '%2e%2e%5c', '%2e%2e/', '..%2f', '..%5c']
        path_lower = request.path.lower()
        
        for pattern in suspicious_patterns:
            if pattern in path_lower:
                logger.warning(f"Path traversal attempt detected: {request.path} from {request.remote_addr}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid filename: path traversal detected'
                }), 400

# Security: Handle 404 errors on API endpoints to prevent information disclosure
@app.errorhandler(404)
def handle_404(error):
    """Handle 404 errors, especially for API endpoints with malicious paths"""
    if request.path.startswith('/api/'):
        # For API endpoints, return JSON error instead of HTML
        return jsonify({
            'success': False,
            'error': 'Invalid filename: path traversal detected'
        }), 400  # Return 400 instead of 404 for security
    
    # For non-API endpoints, return normal 404
    return error

def validate_filename(filename):
    """
    Validate filename to prevent path traversal and ensure it's a valid .img file
    
    Args:
        filename (str): The filename to validate
        
    Returns:
        str: The validated filename
        
    Raises:
        ValueError: If filename is invalid or potentially malicious
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # URL decode the filename first
    filename = unquote(filename)
    
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError("Invalid filename: path traversal detected")
    
    # Check for null bytes (another common attack vector)
    if '\x00' in filename:
        raise ValueError("Invalid filename: null byte detected")
    
    # Ensure it's a valid .img file
    if not filename.lower().endswith('.img'):
        raise ValueError("Invalid filename: only .img files are allowed")
    
    # Check filename length (reasonable limit)
    if len(filename) > 255:
        raise ValueError("Invalid filename: filename too long")
    
    # Check for valid characters (alphanumeric, spaces, hyphens, underscores, dots)
    import string
    allowed_chars = string.ascii_letters + string.digits + ' -_.()[]'
    if not all(c in allowed_chars for c in filename[:-4]):  # Exclude .img extension from check
        raise ValueError("Invalid filename: contains invalid characters")
    
    return filename

def safe_decode_subprocess_output(output_bytes):
    """Safely decode subprocess output, handling various encodings"""
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

class LanguageMapper:
    """Maps language codes to human-readable names"""
    
    LANGUAGE_MAP = {
        'eng': 'English',
        'spa': 'Spanish', 'es': 'Spanish',
        'fre': 'French', 'fra': 'French', 'fr': 'French',
        'ger': 'German', 'deu': 'German', 'de': 'German',
        'ita': 'Italian', 'it': 'Italian',
        'por': 'Portuguese', 'pt': 'Portuguese',
        'jpn': 'Japanese', 'ja': 'Japanese',
        'kor': 'Korean', 'ko': 'Korean',
        'chi': 'Chinese', 'zho': 'Chinese', 'zh': 'Chinese',
        'rus': 'Russian', 'ru': 'Russian',
        'ara': 'Arabic', 'ar': 'Arabic',
        'hin': 'Hindi', 'hi': 'Hindi',
        'und': 'Unknown'
    }
    
    @classmethod
    def get_language_name(cls, lang_code):
        """Get human-readable language name from code"""
        if not lang_code:
            return 'Unknown'
        return cls.LANGUAGE_MAP.get(lang_code.lower(), lang_code.upper())

class HandBrakeScanner:
    """Handles HandBrake CLI integration for scanning media files"""
    
    @staticmethod
    def _check_handbrake_available():
        """Check if HandBrake CLI is available"""
        try:
            result = subprocess.run(['/usr/local/bin/HandBrakeCLI', '--version'], 
                                  capture_output=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @staticmethod
    def scan_file(file_path):
        """Scan a media file using HandBrake CLI"""
        # Validate and sanitize file path
        try:
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {file_path}")
            
            # Ensure it's actually an .img file
            if not str(file_path).lower().endswith('.img'):
                raise ValueError(f"File is not an .img file: {file_path}")
            
            # Convert back to string for subprocess
            file_path_str = str(file_path)
            
        except (OSError, ValueError) as e:
            logger.error(f"Invalid file path: {e}")
            raise
        
        filename = file_path.name
        logger.info(f"Starting HandBrake scan for: {filename}")
        
        try:
            # Check if HandBrake CLI is available
            if not HandBrakeScanner._check_handbrake_available():
                error_msg = "HandBrake CLI not found. Please install HandBrake."
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Check if file is readable
            if not os.access(file_path_str, os.R_OK):
                error_msg = f"File not readable: {file_path_str}"
                logger.error(error_msg)
                raise PermissionError(error_msg)
            
            # Run HandBrake CLI scan - using validated file path
            cmd = ['/usr/local/bin/HandBrakeCLI', '--scan', '--title', '0', '--json', '--input', file_path_str]
            logger.info(f"Running HandBrake command for: {filename}")
            
            # Use binary output to avoid UTF-8 decode errors
            result = subprocess.run(cmd, capture_output=True, text=False, timeout=120)
            
            # Safely decode the output
            stdout_decoded = safe_decode_subprocess_output(result.stdout)
            stderr_decoded = safe_decode_subprocess_output(result.stderr)
            
            logger.info(f"HandBrake exit code: {result.returncode}")
            
            if result.returncode == 0:
                try:
                    # Parse JSON output - HandBrake may output multiple JSON documents
                    data = HandBrakeScanner._parse_handbrake_json(stdout_decoded)
                    logger.info(f"Successfully parsed HandBrake JSON for: {filename}")
                    
                    # Log basic info about what we found
                    title_count = len(data.get('TitleList', []))
                    logger.info(f"Found {title_count} titles in: {filename}")
                    
                    # Store raw output for debugging/viewing
                    data['_raw_handbrake_output'] = {
                        'stdout': stdout_decoded,
                        'stderr': stderr_decoded,
                        'exit_code': result.returncode,
                        'command': ' '.join(cmd),
                        'scan_timestamp': datetime.now().isoformat()
                    }
                    
                    return data
                except json.JSONDecodeError as e:
                    error_msg = f"HandBrake returned invalid JSON for {filename}: {e}"
                    logger.error(error_msg)
                    logger.error(f"Raw HandBrake output: {repr(stdout_decoded[:1000])}")
                    raise ValueError(error_msg)
            else:
                # HandBrake failed - return error details
                error_msg = f"HandBrake scan failed for {filename} (exit code {result.returncode})"
                if stderr_decoded:
                    error_msg += f": {stderr_decoded.strip()}"
                logger.error(error_msg)
                raise subprocess.CalledProcessError(result.returncode, cmd, stderr_decoded)
                
        except subprocess.TimeoutExpired:
            error_msg = f"HandBrake scan timed out after 120 seconds for file: {filename}"
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except FileNotFoundError as e:
            logger.error(f"HandBrake CLI not available: {e}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"HandBrake process error: {e}")
            raise RuntimeError(f"HandBrake scan failed: {e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error scanning {filename}: {e}")
            raise

    @staticmethod
    def _parse_handbrake_json(raw_output):
        """
        Parse HandBrake JSON output which may contain multiple JSON documents
        or have additional text mixed with JSON.
        """
        if not raw_output or not raw_output.strip():
            raise json.JSONDecodeError("Empty output", "", 0)
        
        # Try parsing as single JSON document first (most common case)
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            pass
        
        # HandBrake outputs multiple JSON objects with labels like:
        # Version: { ... }
        # Progress: { ... }
        # JSON Title Set: { ... }
        # We want the "JSON Title Set" one specifically
        
        # Method 1: Look for labeled JSON sections
        lines = raw_output.strip().split('\n')
        current_json_lines = []
        current_label = None
        json_sections = {}
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check if this line starts a new JSON section
            if ':' in line and (line_stripped.endswith('{') or '{' in line):
                # Save previous section if we have one
                if current_json_lines and current_label:
                    json_text = '\n'.join(current_json_lines)
                    try:
                        json_sections[current_label] = json.loads(json_text)
                    except json.JSONDecodeError:
                        pass
                
                # Start new section
                parts = line.split(':', 1)
                current_label = parts[0].strip()
                json_part = parts[1].strip()
                current_json_lines = [json_part] if json_part else []
            elif current_json_lines:
                # Continue building current JSON section
                current_json_lines.append(line)
                
                # Check if this completes the JSON (ends with })
                if line_stripped.endswith('}') and line_stripped.count('}') >= line_stripped.count('{'):
                    json_text = '\n'.join(current_json_lines)
                    try:
                        parsed = json.loads(json_text)
                        if current_label:
                            json_sections[current_label] = parsed
                        current_json_lines = []
                        current_label = None
                    except json.JSONDecodeError:
                        # Continue collecting lines
                        pass
        
        # Save any remaining section
        if current_json_lines and current_label:
            json_text = '\n'.join(current_json_lines)
            try:
                json_sections[current_label] = json.loads(json_text)
            except json.JSONDecodeError:
                pass
        
        # Look for the title set data in order of preference
        for preferred_key in ['JSON Title Set', 'TitleSet', 'Title Set']:
            if preferred_key in json_sections:
                return json_sections[preferred_key]
        
        # Look for any section with TitleList
        for label, data in json_sections.items():
            if isinstance(data, dict) and 'TitleList' in data:
                return data
        
        # Method 2: Look for the largest JSON block in the output
        # HandBrake typically outputs the main JSON as one large block
        potential_json_blocks = []
        
        # Try to find JSON blocks by looking for balanced braces
        i = 0
        while i < len(raw_output):
            if raw_output[i] == '{':
                # Found start of potential JSON block
                brace_count = 1
                start = i
                i += 1
                
                while i < len(raw_output) and brace_count > 0:
                    if raw_output[i] == '{':
                        brace_count += 1
                    elif raw_output[i] == '}':
                        brace_count -= 1
                    i += 1
                
                if brace_count == 0:  # Found complete JSON block
                    json_block = raw_output[start:i]
                    try:
                        parsed = json.loads(json_block)
                        # Prefer blocks with TitleList
                        priority = 2 if 'TitleList' in parsed else 1
                        potential_json_blocks.append((priority, len(json_block), parsed))
                    except json.JSONDecodeError:
                        pass
            else:
                i += 1
        
        # Return the highest priority, largest valid JSON block
        if potential_json_blocks:
            potential_json_blocks.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return potential_json_blocks[0][2]
        
        # Method 3: Try to extract JSON from lines that look like complete JSON objects
        json_objects = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip obvious non-JSON lines and partial JSON fragments
            if (line.startswith('[') or line.startswith('{')) and (line.endswith(']') or line.endswith('}')):
                # Additional check: must be a reasonably complete JSON (not just a fragment)
                if len(line) < 20:  # Skip very short JSON fragments
                    continue
                try:
                    obj = json.loads(line)
                    # Prefer objects that look like main HandBrake results
                    if isinstance(obj, dict) and ('TitleList' in obj or 'Version' in obj or len(obj) > 2):
                        json_objects.append(obj)
                except json.JSONDecodeError:
                    continue
        
        # If we found JSON objects, prefer one with TitleList
        if json_objects:
            for obj in json_objects:
                if 'TitleList' in obj:
                    return obj
            # If no TitleList found, return the largest object
            return max(json_objects, key=lambda x: len(str(x)))
        
        # If all methods fail, raise an error with helpful information
        logger.error(f"Failed to parse HandBrake JSON output. Raw output length: {len(raw_output)}")
        logger.error(f"Output preview: {repr(raw_output[:500])}")
        logger.error(f"Output suffix: {repr(raw_output[-200:])}")
        
        raise json.JSONDecodeError(
            f"Could not parse HandBrake JSON output. Tried multiple parsing methods. "
            f"Output length: {len(raw_output)} chars. "
            f"Preview: {repr(raw_output[:200])}...",
            raw_output,
            0
        )

class MovieMetadataManager:
    def __init__(self, directory=None):
        self.directory = directory
        self.movies = []
        self.handbrake_cache = {}  # Cache HandBrake scan results
        if directory:
            self.scan_directory()
    
    def set_directory(self, directory):
        """Set the working directory and scan for movies"""
        self.directory = Path(directory)
        self.scan_directory()
    
    def scan_directory(self):
        """Scan directory for .img files and their metadata"""
        if not self.directory or not self.directory.exists():
            self.movies = []
            return
        
        self.movies = []
        img_files = list(self.directory.glob("*.img"))
        
        for img_file in img_files:
            metadata_file = img_file.with_suffix('.mmm')
            
            # Load metadata if it exists
            metadata = {
                'file_name': img_file.name,
                'movie_name': img_file.stem,
                'release_date': '',
                'synopsis': '',
                'size_mb': None,
                'titles': []
            }
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        saved_metadata = json.load(f)
                        metadata.update(saved_metadata)
                except (json.JSONDecodeError, IOError):
                    pass  # Use default metadata if file is corrupted
            
            # Get file size
            try:
                size_bytes = img_file.stat().st_size
                metadata['size_mb'] = round(size_bytes / (1024 * 1024), 1)
            except OSError:
                pass
            
            metadata['has_metadata'] = self.has_meaningful_metadata(img_file.name)
            self.movies.append(metadata)
        
        # Sort by filename
        self.movies.sort(key=lambda x: x['file_name'].lower())
    
    def has_meaningful_metadata(self, img_file):
        """Check if a file has meaningful metadata (not just selected titles)"""
        metadata = self.load_metadata(img_file)
        
        # Check if any selected title has a movie name filled in
        for title in metadata.get('titles', []):
            if title.get('selected', False) and title.get('movie_name', '').strip():
                return True
        
        return False
    
    def get_handbrake_data(self, img_file):
        """Get HandBrake scan data for a file, with caching"""
        if img_file not in self.handbrake_cache:
            file_path = self.directory / img_file
            logger.info(f"Scanning {img_file} with HandBrake...")
            try:
                self.handbrake_cache[img_file] = HandBrakeScanner.scan_file(str(file_path))
                logger.info(f"Successfully scanned {img_file}")
            except Exception as e:
                logger.error(f"Failed to scan {img_file}: {e}")
                
                # Try to capture raw output even for failed scans
                error_cache = {
                    'error': str(e),
                    'TitleList': []  # Empty list so other code doesn't break
                }
                
                # If it's a subprocess error, try to extract raw output from the exception
                if hasattr(e, 'cmd') and hasattr(e, 'returncode'):
                    # This is a subprocess error - try to run the command again to get raw output
                    try:
                        import subprocess
                        cmd = ['/usr/local/bin/HandBrakeCLI', '--scan', '--title', '0', '--json', '--input', str(file_path)]
                        result = subprocess.run(cmd, capture_output=True, text=False, timeout=120)
                        
                        # Safely decode the output
                        stdout_decoded = safe_decode_subprocess_output(result.stdout)
                        stderr_decoded = safe_decode_subprocess_output(result.stderr)
                        
                        error_cache['_raw_handbrake_output'] = {
                            'stdout': stdout_decoded,
                            'stderr': stderr_decoded,
                            'exit_code': result.returncode,
                            'command': ' '.join(cmd),
                            'scan_timestamp': datetime.now().isoformat()
                        }
                    except Exception as raw_error:
                        logger.debug(f"Could not capture raw output for failed scan: {raw_error}")
                
                self.handbrake_cache[img_file] = error_cache
        return self.handbrake_cache[img_file]
    
    def format_duration(self, duration_dict):
        """Convert HandBrake duration dict to human readable format"""
        hours = duration_dict.get('Hours', 0)
        minutes = duration_dict.get('Minutes', 0)
        seconds = duration_dict.get('Seconds', 0)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def get_title_suggestions(self, handbrake_data):
        """Generate smart suggestions for title selection"""
        suggestions = []
        
        for title in handbrake_data.get('TitleList', []):
            duration = title.get('Duration', {})
            total_minutes = duration.get('Hours', 0) * 60 + duration.get('Minutes', 0)
            
            # Suggest titles longer than 10 minutes (skip trailers/extras)
            suggested = total_minutes >= 10
            
            suggestions.append({
                'title_index': title.get('Index', 0),
                'suggested': suggested,
                'reason': 'Main content' if suggested else 'Too short (likely trailer/extra)'
            })
        
        return suggestions
    
    def get_audio_suggestions(self, audio_list):
        """Generate smart suggestions for audio track selection"""
        suggestions = []
        
        for audio in audio_list:
            lang_code = audio.get('LanguageCode', '').lower()
            description = audio.get('Description', '').lower()
            
            # Get human-readable language name
            language_name = LanguageMapper.get_language_name(lang_code)
            
            # Prefer English and commentary tracks
            suggested = (
                lang_code == 'eng' or 
                'english' in description or
                'commentary' in description
            )
            
            # Build reason list with proper language names
            reason = []
            
            # Add language name (always show the actual language)
            if language_name != 'Unknown':
                reason.append(language_name)
            
            if 'commentary' in description:
                reason.append('Commentary')
            
            if lang_code == 'eng' or 'english' in description:
                # Don't add "English" again if we already have it from language_name
                if language_name != 'English':
                    reason.append('English')
            
            suggestions.append({
                'track_number': audio.get('TrackNumber', 0),
                'suggested': suggested,
                'reason': ', '.join(reason),
                'language_name': language_name,
                'language_code': lang_code
            })
        
        return suggestions
    
    def get_subtitle_suggestions(self, subtitle_list):
        """Generate smart suggestions for subtitle track selection"""
        suggestions = []
        
        for subtitle in subtitle_list:
            lang_code = subtitle.get('LanguageCode', '').lower()
            name = subtitle.get('Name', '').lower()
            
            # Get human-readable language name
            language_name = LanguageMapper.get_language_name(lang_code)
            
            # Prefer English subtitles
            suggested = (
                lang_code == 'eng' or 
                'english' in name
            )
            
            # Use the actual language name instead of just "English" or "Non-English"
            reason = language_name
            
            suggestions.append({
                'track_number': subtitle.get('TrackNumber', 0),
                'suggested': suggested,
                'reason': reason,
                'language_name': language_name,
                'language_code': lang_code
            })
        
        return suggestions
    
    def load_metadata(self, img_file):
        """Load metadata for the given .img file"""
        mmm_path = self.directory / (Path(img_file).stem + '.mmm')
        
        # Get file size
        file_size_mb = 0
        try:
            img_path = self.directory / img_file
            size_bytes = img_path.stat().st_size
            file_size_mb = round(size_bytes / (1024 * 1024), 1)
        except OSError:
            pass
        
        # Default metadata structure
        metadata = {
            'file_name': img_file,
            'size_mb': file_size_mb,
            'titles': []
        }
        
        # Try to load existing .mmm file
        if mmm_path.exists():
            try:
                with open(mmm_path, 'r') as f:
                    saved_metadata = json.load(f)
                # Check if it's new format (has 'titles' key)
                if 'titles' in saved_metadata:
                    metadata.update(saved_metadata)
                else:
                    # Convert old format to new
                    metadata['titles'] = [{
                        'title_number': 1,
                        'selected': True,
                        'movie_name': saved_metadata.get('movie_name', ''),
                        'release_date': saved_metadata.get('release_date', ''),
                        'synopsis': saved_metadata.get('synopsis', ''),
                        'duration': '',
                        'selected_audio_tracks': [],
                        'selected_subtitle_tracks': []
                    }]
            except (IOError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load metadata for {img_file}: {e}")
                pass
        
        return metadata
    
    def save_metadata(self, img_file, metadata):
        """Save metadata to .mmm file"""
        mmm_file = Path(img_file).stem + '.mmm'
        mmm_path = self.directory / mmm_file
        
        try:
            with open(mmm_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Update in-memory data
            for movie in self.movies:
                if movie['file_name'] == img_file:
                    movie.update(metadata)
                    movie['has_metadata'] = self.has_meaningful_metadata(img_file)
                    break
            
            return True
        except (IOError, UnicodeEncodeError) as e:
            logger.error(f"Could not save metadata for {img_file}: {e}")
            return False
    
    def get_enhanced_metadata(self, img_file):
        """Get complete metadata including HandBrake scan data and suggestions"""
        # Validate filename
        try:
            img_file = validate_filename(img_file)
        except ValueError as e:
            logger.error(f"Invalid filename in get_enhanced_metadata: {img_file} - {e}")
            raise
        
        # Ensure the file exists in our directory
        file_path = self.directory / img_file
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {img_file}")
        
        metadata = self.load_metadata(img_file)
        handbrake_data = self.get_handbrake_data(img_file)
        
        # Enhance with HandBrake data and suggestions
        enhanced_titles = []
        title_suggestions = self.get_title_suggestions(handbrake_data)
        
        for title in handbrake_data.get('TitleList', []):
            title_index = title.get('Index', 0)
            
            # Find existing metadata for this title
            existing_title = None
            for saved_title in metadata.get('titles', []):
                if saved_title.get('title_number') == title_index:
                    existing_title = saved_title
                    break
            
            # Get suggestions
            title_suggestion = next((s for s in title_suggestions if s['title_index'] == title_index), {})
            audio_suggestions = self.get_audio_suggestions(title.get('AudioList', []))
            subtitle_suggestions = self.get_subtitle_suggestions(title.get('SubtitleList', []))
            
            enhanced_title = {
                'title_number': title_index,
                'duration': self.format_duration(title.get('Duration', {})),
                'video_info': {
                    'width': title.get('VideoTracks', [{}])[0].get('Width', 0),
                    'height': title.get('VideoTracks', [{}])[0].get('Height', 0),
                    'frame_rate': title.get('VideoTracks', [{}])[0].get('FrameRate', 0),
                    'chapters': len(title.get('VideoTracks', [{}])[0].get('Chapters', []))
                },
                'audio_tracks': title.get('AudioList', []),
                'subtitle_tracks': title.get('SubtitleList', []),
                'suggestions': {
                    'title': title_suggestion,
                    'audio': audio_suggestions,
                    'subtitles': subtitle_suggestions
                },
                # Metadata fields
                'selected': existing_title.get('selected', False) if existing_title else False,
                'movie_name': existing_title.get('movie_name', '') if existing_title else '',
                'release_date': existing_title.get('release_date', '') if existing_title else '',
                'synopsis': existing_title.get('synopsis', '') if existing_title else '',
                'selected_audio_tracks': existing_title.get('selected_audio_tracks', []) if existing_title else [],
                'selected_subtitle_tracks': existing_title.get('selected_subtitle_tracks', []) if existing_title else []
            }
            
            enhanced_titles.append(enhanced_title)
        
        return {
            'file_name': metadata['file_name'],
            'size_mb': metadata['size_mb'],
            'titles': enhanced_titles,
            'scan_error': handbrake_data.get('error')
        }
    
    def test_handbrake(self):
        """Test if HandBrake is available and working"""
        return HandBrakeScanner._check_handbrake_available()

# Global manager instance
manager = MovieMetadataManager()

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
            manager.set_directory(directory)
            return redirect(url_for('index'))
        else:
            return render_template('setup.html', 
                                 error="Directory does not exist or is not accessible")
    
    return render_template('setup.html')

@app.route('/api/save_metadata', methods=['POST'])
def save_metadata():
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
        
        filename = data.get('filename')
        if not filename:
            return jsonify({'success': False, 'error': 'Filename is required'})
        
        # Validate filename for security
        try:
            filename = validate_filename(filename)
        except ValueError as e:
            logger.warning(f"Invalid filename rejected: {filename} - {e}")
            return jsonify({'success': False, 'error': f'Invalid filename: {e}'})
        
        # Validate metadata structure
        titles = data.get('titles', [])
        if not isinstance(titles, list):
            return jsonify({'success': False, 'error': 'Titles must be a list'})
        
        # Sanitize string inputs
        def sanitize_string(value, max_length=1000):
            if not isinstance(value, str):
                return ''
            # Remove null bytes and limit length
            return value.replace('\x00', '').strip()[:max_length]
        
        metadata = {
            'movie_name': sanitize_string(data.get('movie_name', '')),
            'release_date': sanitize_string(data.get('release_date', ''), 10),  # YYYY-MM-DD format
            'synopsis': sanitize_string(data.get('synopsis', ''), 5000),  # Longer limit for synopsis
            'file_name': filename,
            'titles': titles  # Will be validated by the manager
        }
        
        success = manager.save_metadata(filename, metadata)
        return jsonify({'success': success})
        
    except Exception as e:
        logger.error(f"Error in save_metadata endpoint: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'})

@app.route('/api/file_list')
def file_list():
    """Get updated file list with status"""
    manager.scan_directory()  # Refresh the list
    return jsonify({'movies': manager.movies})

@app.route('/api/scan_file/<filename>')
def api_scan_file(filename):
    """API endpoint to trigger HandBrake scan for a specific file"""
    if not manager:
        return jsonify({'success': False, 'error': 'No directory configured'})
    
    try:
        # Validate filename for security
        try:
            filename = validate_filename(filename)
        except ValueError as e:
            logger.warning(f"Invalid filename rejected in scan_file: {filename} - {e}")
            return jsonify({'success': False, 'error': f'Invalid filename: {e}'})
        
        # Clear cache to force rescan
        if filename in manager.handbrake_cache:
            del manager.handbrake_cache[filename]
        
        enhanced_metadata = manager.get_enhanced_metadata(filename)
        return jsonify({
            'success': True, 
            'metadata': enhanced_metadata,
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

@app.route('/api/enhanced_metadata/<filename>')
def api_enhanced_metadata(filename):
    """API endpoint to get enhanced metadata for a file"""
    if not manager:
        return jsonify({'success': False, 'error': 'No directory configured'})
    
    try:
        # Validate filename for security
        try:
            filename = validate_filename(filename)
        except ValueError as e:
            logger.warning(f"Invalid filename rejected in enhanced_metadata: {filename} - {e}")
            return jsonify({'success': False, 'error': f'Invalid filename: {e}'})
        
        enhanced_metadata = manager.get_enhanced_metadata(filename)
        return jsonify({
            'success': True, 
            'metadata': enhanced_metadata,
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

@app.route('/health')
def health():
    """Health check endpoint"""
    handbrake_available = manager.test_handbrake()
    return jsonify({
        'status': 'ok',
        'handbrake': 'available' if handbrake_available else 'unavailable',
        'directory': str(manager.directory) if manager.directory else None,
        'movie_count': len(manager.movies)
    })

@app.route('/api/handbrake/test')
def test_handbrake():
    """Test HandBrake functionality"""
    available = manager.test_handbrake()
    return jsonify({
        'available': available,
        'message': 'HandBrake is working' if available else 'HandBrake is not available'
    })

@app.route('/api/raw_output/<filename>')
def api_raw_output(filename):
    """API endpoint to get raw HandBrake output for a file"""
    if not manager:
        return jsonify({'success': False, 'error': 'No directory configured'})
    
    try:
        # Validate filename for security
        try:
            filename = validate_filename(filename)
        except ValueError as e:
            logger.warning(f"Invalid filename rejected in raw_output: {filename} - {e}")
            return jsonify({'success': False, 'error': f'Invalid filename: {e}'})
        
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
            
    except Exception as e:
        logger.error(f"Error getting raw output for {filename}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'filename': filename
        })

if __name__ == '__main__':
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print("Usage: python3 app.py [directory] [--help]")
            print("  directory: Path to directory containing .img files")
            print("  --help: Show this help message")
            sys.exit(0)
        else:
            # Directory specified as command line argument
            directory = sys.argv[1]
            if Path(directory).exists():
                manager.set_directory(directory)
                print(f"Using directory: {directory}")
            else:
                print(f"Error: Directory '{directory}' does not exist")
                sys.exit(1)
    
    # Run the Flask app
    print("Starting Disk Extractor - Movie Metadata Manager")
    print("Access the web interface at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
