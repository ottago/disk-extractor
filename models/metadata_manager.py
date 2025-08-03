"""
Movie metadata manager for Disk Extractor

Manages movie metadata stored alongside .img files.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from cachetools import TTLCache
from typing import Dict, List, Any, Optional, Union

from config import Config
from models.handbrake_scanner import HandBrakeScanner, HandBrakeError
from utils.language_mapper import LanguageMapper
from utils.validation import validate_filename, ValidationError

logger = logging.getLogger(__name__)


class MetadataError(Exception):
    """Custom exception for metadata-related errors"""
    pass


class MovieMetadataManager:
    """Manages movie metadata and HandBrake integration"""
    
    def __init__(self, directory: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the metadata manager
        
        Args:
            directory: Directory containing movie files
        """
        self.directory: Optional[Path] = None
        self.movies: List[Dict[str, Any]] = []
        # Use TTL cache with size limit for HandBrake results
        self.handbrake_cache: TTLCache = TTLCache(maxsize=Config.MAX_CACHE_SIZE, ttl=Config.CACHE_TTL)
        
        if directory:
            self.set_directory(directory)
    
    def set_directory(self, directory: Union[str, Path]) -> None:
        """
        Set the working directory and scan for movies
        
        Args:
            directory: Directory containing movie files
            
        Raises:
            MetadataError: If directory is invalid
        """
        try:
            self.directory = Path(directory).resolve()
            if not self.directory.exists():
                raise MetadataError(f"Directory does not exist: {directory}")
            if not self.directory.is_dir():
                raise MetadataError(f"Path is not a directory: {directory}")
        except OSError as e:
            raise MetadataError(f"Invalid directory: {e}")
        
        self.scan_directory()
    
    def scan_directory(self) -> None:
        """Scan directory for .img files and their metadata"""
        if not self.directory or not self.directory.exists():
            self.movies = []
            return
        
        self.movies = []
        
        try:
            img_files = list(self.directory.glob("*.img"))
        except OSError as e:
            logger.error(f"Error scanning directory {self.directory}: {e}")
            return
        
        for img_file in img_files:
            try:
                metadata = self._load_file_metadata(img_file)
                self.movies.append(metadata)
            except Exception as e:
                logger.warning(f"Error loading metadata for {img_file.name}: {e}")
                # Add basic metadata even if loading fails
                self.movies.append({
                    'file_name': img_file.name,
                    'movie_name': img_file.stem,
                    'release_date': '',
                    'synopsis': '',
                    'size_mb': self._get_file_size_mb(img_file),
                    'titles': [],
                    'has_metadata': False
                })
        
        # Sort by filename
        self.movies.sort(key=lambda x: x['file_name'].lower())
    
    def _load_file_metadata(self, img_file: Path) -> Dict[str, Any]:
        """
        Load metadata for a single .img file
        
        Args:
            img_file: Path to the .img file
            
        Returns:
            File metadata
        """
        metadata_file = img_file.with_suffix('.mmm')
        
        # Load metadata if it exists
        metadata: Dict[str, Any] = {
            'file_name': img_file.name,
            'movie_name': img_file.stem,
            'release_date': '',
            'synopsis': '',
            'size_mb': self._get_file_size_mb(img_file),
            'titles': []
        }
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    saved_metadata = json.load(f)
                    metadata.update(saved_metadata)
            except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
                logger.warning(f"Could not load metadata file {metadata_file}: {e}")
        
        metadata['has_metadata'] = self.has_meaningful_metadata(img_file.name)
        return metadata
    
    def _get_file_size_mb(self, file_path: Path) -> Optional[float]:
        """
        Get file size in MB
        
        Args:
            file_path: Path to the file
            
        Returns:
            File size in MB, or None if error
        """
        try:
            size_bytes = file_path.stat().st_size
            return round(size_bytes / (1024 * 1024), 1)
        except OSError:
            return None
    
    def has_meaningful_metadata(self, img_file: str) -> bool:
        """
        Check if a file has meaningful metadata (not just selected titles)
        
        Args:
            img_file: Filename of the .img file
            
        Returns:
            True if file has meaningful metadata
        """
        try:
            metadata = self.load_metadata(img_file)
            
            # Check if any selected title has a movie name filled in
            for title in metadata.get('titles', []):
                if title.get('selected', False) and title.get('movie_name', '').strip():
                    return True
            
            return False
        except Exception:
            return False
    
    def get_handbrake_data(self, img_file: str) -> Dict[str, Any]:
        """
        Get HandBrake scan data for a file, with caching
        
        Args:
            img_file: Filename of the .img file
            
        Returns:
            HandBrake scan data
        """
        if img_file not in self.handbrake_cache:
            file_path = self.directory / img_file
            logger.info(f"Scanning {img_file} with HandBrake...")
            try:
                self.handbrake_cache[img_file] = HandBrakeScanner.scan_file(str(file_path))
                logger.info(f"Successfully scanned {img_file}")
            except Exception as e:
                logger.error(f"Failed to scan {img_file}: {e}")
                
                # Create error cache entry
                error_cache: Dict[str, Any] = {
                    'error': str(e),
                    'TitleList': []  # Empty list so other code doesn't break
                }
                
                # Try to capture raw output for failed scans
                if hasattr(e, 'cmd') and hasattr(e, 'returncode'):
                    try:
                        import subprocess
                        from utils.security import safe_decode_subprocess_output
                        
                        cmd = [Config.HANDBRAKE_CLI_PATH, '--scan', '--title', '0', '--json', '--input', str(file_path)]
                        result = subprocess.run(cmd, capture_output=True, text=False, timeout=Config.HANDBRAKE_TIMEOUT)
                        
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
    
    def format_duration(self, duration_dict: Dict[str, int]) -> str:
        """
        Convert HandBrake duration dict to human readable format
        
        Args:
            duration_dict: HandBrake duration dictionary
            
        Returns:
            Formatted duration string
        """
        hours = duration_dict.get('Hours', 0)
        minutes = duration_dict.get('Minutes', 0)
        seconds = duration_dict.get('Seconds', 0)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def get_title_suggestions(self, handbrake_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate smart suggestions for title selection
        
        Args:
            handbrake_data: HandBrake scan data
            
        Returns:
            List of title suggestions
        """
        suggestions: List[Dict[str, Any]] = []
        
        for title in handbrake_data.get('TitleList', []):
            duration = title.get('Duration', {})
            total_minutes = duration.get('Hours', 0) * 60 + duration.get('Minutes', 0)
            
            # Suggest titles longer than configured minimum (skip trailers/extras)
            suggested = total_minutes >= Config.MIN_TITLE_DURATION_MINUTES
            
            suggestions.append({
                'title_index': title.get('Index', 0),
                'suggested': suggested,
                'reason': 'Main content' if suggested else 'Too short (likely trailer/extra)'
            })
        
        return suggestions
    
    def get_audio_suggestions(self, audio_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate smart suggestions for audio track selection
        
        Args:
            audio_list: List of audio tracks from HandBrake
            
        Returns:
            List of audio track suggestions
        """
        suggestions: List[Dict[str, Any]] = []
        
        for audio in audio_list:
            lang_code = audio.get('LanguageCode', '').lower()
            description = audio.get('Description', '').lower()
            
            # Get human-readable language name
            language_name = LanguageMapper.get_language_name(lang_code)
            
            # Prefer English and commentary tracks
            suggested = (
                LanguageMapper.is_english(lang_code) or 
                'english' in description or
                'commentary' in description
            )
            
            # Build reason list with proper language names
            reason: List[str] = []
            
            # Add language name (always show the actual language)
            if language_name != 'Unknown':
                reason.append(language_name)
            
            if 'commentary' in description:
                reason.append('Commentary')
            
            if LanguageMapper.is_english(lang_code) or 'english' in description:
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
    
    def get_subtitle_suggestions(self, subtitle_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate smart suggestions for subtitle track selection
        
        Args:
            subtitle_list: List of subtitle tracks from HandBrake
            
        Returns:
            List of subtitle track suggestions
        """
        suggestions: List[Dict[str, Any]] = []
        
        for subtitle in subtitle_list:
            lang_code = subtitle.get('LanguageCode', '').lower()
            name = subtitle.get('Name', '').lower()
            
            # Get human-readable language name
            language_name = LanguageMapper.get_language_name(lang_code)
            
            # Prefer English subtitles
            suggested = (
                LanguageMapper.is_english(lang_code) or 
                'english' in name
            )
            
            suggestions.append({
                'track_number': subtitle.get('TrackNumber', 0),
                'suggested': suggested,
                'reason': language_name,
                'language_name': language_name,
                'language_code': lang_code
            })
        
        return suggestions
    
    def load_metadata(self, img_file: str) -> Dict[str, Any]:
        """
        Load metadata for the given .img file
        
        Args:
            img_file: Filename of the .img file
            
        Returns:
            File metadata
            
        Raises:
            ValidationError: If filename is invalid
        """
        # Validate filename
        img_file = validate_filename(img_file)
        
        mmm_path = self.directory / (Path(img_file).stem + '.mmm')
        
        # Get file size
        file_size_mb: Optional[float] = 0
        try:
            img_path = self.directory / img_file
            file_size_mb = self._get_file_size_mb(img_path)
        except OSError:
            pass
        
        # Default metadata structure
        metadata: Dict[str, Any] = {
            'file_name': img_file,
            'size_mb': file_size_mb,
            'titles': []
        }
        
        # Try to load existing .mmm file
        if mmm_path.exists():
            try:
                with open(mmm_path, 'r', encoding='utf-8') as f:
                    saved_metadata = json.load(f)
                # Check if it's current format (has 'titles' key)
                if 'titles' in saved_metadata:
                    metadata.update(saved_metadata)
                else:
                    # Convert legacy format to current format
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
            except (IOError, json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Could not load metadata for {img_file}: {e}")
        
        return metadata
    
    def save_metadata(self, img_file: str, metadata: Dict[str, Any]) -> bool:
        """
        Save metadata to .mmm file
        
        Args:
            img_file: Filename of the .img file
            metadata: Metadata to save
            
        Returns:
            True if successful
            
        Raises:
            ValidationError: If filename is invalid
        """
        # Validate filename
        img_file = validate_filename(img_file)
        
        mmm_file = Path(img_file).stem + '.mmm'
        mmm_path = self.directory / mmm_file
        
        try:
            with open(mmm_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
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
    
    def get_enhanced_metadata(self, img_file: str) -> Dict[str, Any]:
        """
        Get complete metadata including HandBrake scan data and suggestions
        
        Args:
            img_file: Filename of the .img file
            
        Returns:
            Enhanced metadata with HandBrake data
            
        Raises:
            ValidationError: If filename is invalid
            FileNotFoundError: If file not found
        """
        # Validate filename
        img_file = validate_filename(img_file)
        
        # Ensure the file exists in our directory
        file_path = self.directory / img_file
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {img_file}")
        
        metadata = self.load_metadata(img_file)
        handbrake_data = self.get_handbrake_data(img_file)
        
        # Enhance with HandBrake data and suggestions
        enhanced_titles: List[Dict[str, Any]] = []
        title_suggestions = self.get_title_suggestions(handbrake_data)
        
        for title in handbrake_data.get('TitleList', []):
            title_index = title.get('Index', 0)
            
            # Find existing metadata for this title
            existing_title: Optional[Dict[str, Any]] = None
            for saved_title in metadata.get('titles', []):
                if saved_title.get('title_number') == title_index:
                    existing_title = saved_title
                    break
            
            # Get suggestions
            title_suggestion = next((s for s in title_suggestions if s['title_index'] == title_index), {})
            audio_suggestions = self.get_audio_suggestions(title.get('AudioList', []))
            subtitle_suggestions = self.get_subtitle_suggestions(title.get('SubtitleList', []))
            
            enhanced_title: Dict[str, Any] = {
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
    
    def test_handbrake(self) -> bool:
        """
        Test if HandBrake is available and working
        
        Returns:
            True if HandBrake is available
        """
        return HandBrakeScanner.test_availability()
    
    def clear_cache(self) -> None:
        """Clear the HandBrake cache"""
        self.handbrake_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Cache statistics
        """
        return {
            'size': len(self.handbrake_cache),
            'max_size': self.handbrake_cache.maxsize,
            'ttl': self.handbrake_cache.ttl
        }
