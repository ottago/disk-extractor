"""
HandBrake scanner for Disk Extractor

Handles HandBrake CLI integration for scanning media files.
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Union

from config import Config
from utils.security import safe_decode_subprocess_output

logger = logging.getLogger(__name__)


class HandBrakeError(Exception):
    """Custom exception for HandBrake-related errors"""
    pass


class HandBrakeScanner:
    """Handles HandBrake CLI integration for scanning media files"""
    
    @staticmethod
    def _check_handbrake_available() -> bool:
        """
        Check if HandBrake CLI is available
        
        Returns:
            True if HandBrake CLI is available
        """
        try:
            result = subprocess.run([Config.HANDBRAKE_CLI_PATH, '--version'], 
                                  capture_output=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @staticmethod
    def scan_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Scan a media file using HandBrake CLI
        
        Args:
            file_path: Path to the media file
            
        Returns:
            HandBrake scan results
            
        Raises:
            HandBrakeError: If scanning fails
            FileNotFoundError: If file or HandBrake CLI not found
            PermissionError: If file is not readable
            TimeoutError: If scan times out
        """
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
            raise HandBrakeError(f"Invalid file path: {e}")
        
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
            cmd = [Config.HANDBRAKE_CLI_PATH, '--scan', '--title', '0', '--json', '--input', file_path_str]
            logger.info(f"Running HandBrake command for: {filename}")
            
            # Use binary output to avoid UTF-8 decode errors
            result = subprocess.run(cmd, capture_output=True, text=False, timeout=Config.HANDBRAKE_TIMEOUT)
            
            # Safely decode the output
            stdout_decoded = safe_decode_subprocess_output(result.stdout)
            stderr_decoded = safe_decode_subprocess_output(result.stderr)
            
            logger.info(f"HandBrake exit code: {result.returncode}")
            
            # Store raw output for debugging/viewing (always capture this)
            raw_output_data = {
                'stdout': stdout_decoded,
                'stderr': stderr_decoded,
                'exit_code': result.returncode,
                'command': ' '.join(cmd),
                'scan_timestamp': datetime.now().isoformat()
            }
            
            if result.returncode == 0:
                try:
                    # Parse JSON output - HandBrake may output multiple JSON documents
                    data = HandBrakeScanner._parse_handbrake_json(stdout_decoded)
                    logger.info(f"Successfully parsed HandBrake JSON for: {filename}")
                    
                    # Log basic info about what we found
                    title_count = len(data.get('TitleList', []))
                    logger.info(f"Found {title_count} titles in: {filename}")
                    
                    # Store raw output for debugging/viewing
                    data['_raw_handbrake_output'] = raw_output_data
                    
                    return data
                except json.JSONDecodeError as e:
                    error_msg = f"HandBrake returned invalid JSON for {filename}: {e}"
                    logger.error(error_msg)
                    logger.error(f"Raw HandBrake output: {repr(stdout_decoded[:1000])}")
                    # Create HandBrakeError with raw output data attached
                    error = HandBrakeError(error_msg)
                    error.raw_output = raw_output_data
                    raise error
            else:
                # HandBrake failed - return error details
                error_msg = f"HandBrake scan failed for {filename} (exit code {result.returncode})"
                if stderr_decoded:
                    error_msg += f": {stderr_decoded.strip()}"
                logger.error(error_msg)
                # Create HandBrakeError with raw output data attached
                error = HandBrakeError(error_msg)
                error.raw_output = raw_output_data
                raise error
                
        except subprocess.TimeoutExpired:
            error_msg = f"HandBrake scan timed out after {Config.HANDBRAKE_TIMEOUT} seconds for file: {filename}"
            logger.error(error_msg)
            error = TimeoutError(error_msg)
            # Try to attach any partial output if available
            try:
                error.raw_output = {
                    'stdout': '',
                    'stderr': '',
                    'exit_code': -1,
                    'command': ' '.join(cmd),
                    'scan_timestamp': datetime.now().isoformat(),
                    'timeout': True
                }
            except:
                pass
            raise error
        except FileNotFoundError as e:
            logger.error(f"HandBrake CLI not available: {e}")
            error = FileNotFoundError(str(e))
            try:
                error.raw_output = {
                    'stdout': '',
                    'stderr': str(e),
                    'exit_code': -1,
                    'command': ' '.join(cmd) if 'cmd' in locals() else 'HandBrake CLI not found',
                    'scan_timestamp': datetime.now().isoformat(),
                    'handbrake_not_found': True
                }
            except:
                pass
            raise error
        except PermissionError as e:
            logger.error(f"Permission error: {e}")
            error = PermissionError(str(e))
            try:
                error.raw_output = {
                    'stdout': '',
                    'stderr': str(e),
                    'exit_code': -1,
                    'command': ' '.join(cmd) if 'cmd' in locals() else 'Permission denied',
                    'scan_timestamp': datetime.now().isoformat(),
                    'permission_error': True
                }
            except:
                pass
            raise error
        except Exception as e:
            logger.error(f"Unexpected error scanning {filename}: {e}")
            error = HandBrakeError(f"Unexpected error scanning {filename}: {e}")
            try:
                error.raw_output = {
                    'stdout': '',
                    'stderr': str(e),
                    'exit_code': -1,
                    'command': ' '.join(cmd) if 'cmd' in locals() else 'Unknown command',
                    'scan_timestamp': datetime.now().isoformat(),
                    'unexpected_error': True
                }
            except:
                pass
            raise error

    @staticmethod
    def _parse_handbrake_json(raw_output: str) -> Dict[str, Any]:
        """
        Parse HandBrake JSON output which may contain multiple JSON documents
        or have additional text mixed with JSON.
        
        Args:
            raw_output: Raw HandBrake output
            
        Returns:
            Parsed JSON data
            
        Raises:
            json.JSONDecodeError: If JSON cannot be parsed
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
    
    @staticmethod
    def test_availability() -> bool:
        """
        Test if HandBrake is available and working
        
        Returns:
            True if HandBrake is available
        """
        return HandBrakeScanner._check_handbrake_available()
