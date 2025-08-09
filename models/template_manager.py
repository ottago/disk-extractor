"""
HandBrake Template Manager for Disk Extractor

Manages HandBrake JSON presets, merges them with metadata, and generates CLI commands.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from config import Config
from utils.validation import validate_filename, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class AudioTrackSelection:
    """Audio track selection from metadata"""
    track_number: int
    language_code: str
    description: str
    selected: bool = False


@dataclass
class SubtitleTrackSelection:
    """Subtitle track selection from metadata"""
    track_number: int
    language_code: str
    name: str
    selected: bool = False


class HandBrakeTemplate:
    """Represents a HandBrake JSON preset template"""
    
    def __init__(self, template_data: Dict[str, Any]):
        """
        Initialize template from JSON data
        
        Args:
            template_data: HandBrake JSON preset data
        """
        self.data = template_data
        self.name = template_data.get('PresetName', 'Unknown')
        self.description = template_data.get('PresetDescription', '')
        self.category = template_data.get('PresetCategory', 'Custom')
        
        # Extract key settings
        self.video_settings = template_data.get('VideoEncoder', {})
        self.audio_settings = template_data.get('AudioList', [])
        self.subtitle_settings = template_data.get('SubtitleList', [])
        self.container_settings = template_data.get('FileFormat', 'mp4')
        
        # Quality settings
        self.video_quality = template_data.get('VideoQualitySlider', 22)
        self.video_bitrate = template_data.get('VideoAvgBitrate', None)
        self.two_pass = template_data.get('VideoTwoPass', False)
        
        # Dimensions and cropping
        self.width = template_data.get('PictureWidth', None)
        self.height = template_data.get('PictureHeight', None)
        self.crop = template_data.get('PictureCrop', [0, 0, 0, 0])
        
    def get_file_extension(self) -> str:
        """Get appropriate file extension for this template"""
        container_map = {
            'mp4': 'mp4',
            'mkv': 'mkv',
            'webm': 'webm',
            'avi': 'avi'
        }
        return container_map.get(self.container_settings.lower(), 'mp4')
    
    def supports_chapters(self) -> bool:
        """Check if template supports chapter markers"""
        return self.data.get('ChapterMarkers', False)
    
    def get_video_encoder(self) -> str:
        """Get video encoder name"""
        return self.data.get('VideoEncoder', 'x264')
    
    def get_audio_encoder(self) -> str:
        """Get default audio encoder"""
        if self.audio_settings:
            return self.audio_settings[0].get('AudioEncoder', 'av_aac')
        return 'av_aac'


class TemplateManager:
    """Manages HandBrake templates and metadata integration"""
    
    def __init__(self):
        """Initialize template manager"""
        self.templates: Dict[str, HandBrakeTemplate] = {}
        
        # Use settings directory for templates
        app_dir = Path(__file__).parent.parent
        self.templates_dir = app_dir / 'settings'
        self.templates_dir.mkdir(exist_ok=True)
        
        # Load existing templates
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load all templates from the templates directory"""
        try:
            for template_file in self.templates_dir.glob('*.json'):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    
                    template = HandBrakeTemplate(template_data)
                    self.templates[template.name] = template
                    logger.info(f"Loaded template: {template.name}")
                    
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to load template {template_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
    
    def save_template(self, name: str, template_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Save a new template
        
        Args:
            name: Template name
            template_data: HandBrake JSON preset data
            
        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            # Validate template data
            is_valid, validation_error = self._validate_template(template_data)
            if not is_valid:
                return False, validation_error
            
            # Create template object
            template = HandBrakeTemplate(template_data)
            
            # Save to file
            template_file = self.templates_dir / f"{name}.json"
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2)
            
            # Add to memory
            self.templates[name] = template
            
            logger.info(f"Saved template: {name}")
            return True, ""
            
        except PermissionError as e:
            error_msg = f"Permission denied: Cannot write to settings directory. Check file permissions."
            logger.error(f"Permission error saving template {name}: {e}")
            return False, error_msg
        except OSError as e:
            error_msg = f"File system error: {str(e)}"
            logger.error(f"OS error saving template {name}: {e}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Error saving template {name}: {e}")
            return False, error_msg
    
    def delete_template(self, name: str) -> bool:
        """
        Delete a template
        
        Args:
            name: Template name
            
        Returns:
            True if deleted successfully
        """
        try:
            if name not in self.templates:
                return False
            
            # Remove file
            template_file = self.templates_dir / f"{name}.json"
            if template_file.exists():
                template_file.unlink()
            
            # Remove from memory
            del self.templates[name]
            
            logger.info(f"Deleted template: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting template {name}: {e}")
            return False
    
    def get_template(self, name: str) -> Optional[HandBrakeTemplate]:
        """
        Get a template by name
        
        Args:
            name: Template name
            
        Returns:
            Template object or None
        """
        return self.templates.get(name)
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """
        Get list of all templates
        
        Returns:
            List of template information
        """
        templates = []
        for name, template in self.templates.items():
            templates.append({
                'name': name,
                'description': template.description,
                'category': template.category,
                'video_encoder': template.get_video_encoder(),
                'audio_encoder': template.get_audio_encoder(),
                'container': template.container_settings,
                'supports_chapters': template.supports_chapters()
            })
        return templates
    
    def build_handbrake_command(self, 
                               input_file: Path,
                               output_file: Path,
                               template_name: str,
                               title_number: int,
                               audio_tracks: List[AudioTrackSelection] = None,
                               subtitle_tracks: List[SubtitleTrackSelection] = None,
                               testing_mode: bool = False,
                               test_duration: int = 60) -> List[str]:
        """
        Build HandBrake CLI command with template and metadata
        
        Args:
            input_file: Input .img file path
            output_file: Output file path
            template_name: Name of template to use
            title_number: Title number to encode
            audio_tracks: Selected audio tracks from metadata
            subtitle_tracks: Selected subtitle tracks from metadata
            testing_mode: Enable testing mode with duration limit
            test_duration: Test duration in seconds
            
        Returns:
            HandBrake CLI command as list of strings
        """
        template = self.get_template(template_name)
        if not template:
            raise HandBrakeError(f"Template '{template_name}' not found.")
        
        # Start with base command
        cmd = [
            Config.HANDBRAKE_CLI_PATH,
            '--input', str(input_file),
            '--output', str(output_file),
            '--title', str(title_number)
        ]
        
        # Add video settings from template
        self._add_video_settings(cmd, template)
        
        # Add audio settings (merge template with metadata selections)
        self._add_audio_settings(cmd, template, audio_tracks or [])
        
        # Add subtitle settings (merge template with metadata selections)
        self._add_subtitle_settings(cmd, template, subtitle_tracks or [])
        
        # Add container and other settings
        self._add_container_settings(cmd, template)
        
        # Add testing mode parameters if enabled
        if testing_mode:
            cmd.extend([
                '--start-at', 'seconds:0',
                '--stop-at', f'seconds:{test_duration}'
            ])
        
        return cmd
    
    def _build_basic_command(self, input_file: Path, output_file: Path, 
                           title_number: int, testing_mode: bool, 
                           test_duration: int) -> List[str]:
        """Build basic HandBrake command without template"""
        cmd = [
            Config.HANDBRAKE_CLI_PATH,
            '--input', str(input_file),
            '--output', str(output_file),
            '--title', str(title_number),
            '--encoder', 'x264',
            '--quality', '22',
            '--aencoder', 'av_aac',
            '--ab', '128'
        ]
        
        if testing_mode:
            cmd.extend([
                '--start-at', 'seconds:0',
                '--stop-at', f'seconds:{test_duration}'
            ])
        
        return cmd
    
    def _add_video_settings(self, cmd: List[str], template: HandBrakeTemplate) -> None:
        """Add video encoding settings from template"""
        # Video encoder
        if template.get_video_encoder():
            cmd.extend(['--encoder', template.get_video_encoder()])
        
        # Quality settings
        if template.video_bitrate:
            cmd.extend(['--vb', str(template.video_bitrate)])
        else:
            cmd.extend(['--quality', str(template.video_quality)])
        
        # Two-pass encoding
        if template.two_pass:
            cmd.append('--two-pass')
        
        # Dimensions
        if template.width and template.height:
            cmd.extend(['--width', str(template.width)])
            cmd.extend(['--height', str(template.height)])
        
        # Cropping
        if template.crop and any(template.crop):
            crop_str = ':'.join(map(str, template.crop))
            cmd.extend(['--crop', crop_str])
    
    def _add_audio_settings(self, cmd: List[str], template: HandBrakeTemplate, 
                          selected_tracks: List[AudioTrackSelection]) -> None:
        """Add audio encoding settings from template and metadata"""
        if not selected_tracks:
            # Use template default audio settings
            if template.audio_settings:
                audio_setting = template.audio_settings[0]
                cmd.extend(['--aencoder', audio_setting.get('AudioEncoder', 'av_aac')])
                if 'AudioBitrate' in audio_setting:
                    cmd.extend(['--ab', str(audio_setting['AudioBitrate'])])
            return
        
        # Use selected tracks from metadata
        audio_tracks = []
        audio_encoders = []
        audio_bitrates = []
        
        for track in selected_tracks:
            if track.selected:
                audio_tracks.append(str(track.track_number))
                
                # Use template encoder or default
                if template.audio_settings:
                    encoder = template.audio_settings[0].get('AudioEncoder', 'av_aac')
                    bitrate = template.audio_settings[0].get('AudioBitrate', 128)
                else:
                    encoder = 'av_aac'
                    bitrate = 128
                
                audio_encoders.append(encoder)
                audio_bitrates.append(str(bitrate))
        
        if audio_tracks:
            cmd.extend(['--audio', ','.join(audio_tracks)])
            cmd.extend(['--aencoder', ','.join(audio_encoders)])
            cmd.extend(['--ab', ','.join(audio_bitrates)])
    
    def _add_subtitle_settings(self, cmd: List[str], template: HandBrakeTemplate,
                             selected_tracks: List[SubtitleTrackSelection]) -> None:
        """Add subtitle settings from template and metadata"""
        if not selected_tracks:
            return
        
        subtitle_tracks = []
        for track in selected_tracks:
            if track.selected:
                subtitle_tracks.append(str(track.track_number))
        
        if subtitle_tracks:
            cmd.extend(['--subtitle', ','.join(subtitle_tracks)])
    
    def _add_container_settings(self, cmd: List[str], template: HandBrakeTemplate) -> None:
        """Add container and other settings from template"""
        # Container format
        if template.container_settings:
            cmd.extend(['--format', template.container_settings])
        
        # Chapter markers
        if template.supports_chapters():
            cmd.append('--markers')
    
    def _validate_template(self, template_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate HandBrake template data
        
        Args:
            template_data: Template data to validate
            
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        try:
            # Check required fields
            required_fields = ['PresetName']
            for field in required_fields:
                if field not in template_data:
                    error_msg = f"Template missing required field: {field}"
                    logger.error(error_msg)
                    return False, error_msg
            
            # Validate preset name
            name = template_data['PresetName']
            if not isinstance(name, str) or len(name.strip()) == 0:
                error_msg = "Invalid preset name: must be a non-empty string"
                logger.error(error_msg)
                return False, error_msg
            
            # Check for dangerous settings (basic validation)
            if 'VideoEncoder' in template_data:
                encoder = template_data['VideoEncoder']
                if not isinstance(encoder, str):
                    error_msg = "Invalid video encoder: must be a string"
                    logger.error(error_msg)
                    return False, error_msg
            
            return True, ""
            
        except Exception as e:
            error_msg = f"Template validation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def extract_metadata_tracks(self, enhanced_metadata: Dict[str, Any], 
                              title_number: int) -> Tuple[List[AudioTrackSelection], 
                                                        List[SubtitleTrackSelection]]:
        """
        Extract selected audio and subtitle tracks from enhanced metadata
        
        Args:
            enhanced_metadata: Enhanced metadata from HandBrake scan
            title_number: Title number to extract tracks for
            
        Returns:
            Tuple of (audio_tracks, subtitle_tracks)
        """
        audio_tracks = []
        subtitle_tracks = []
        
        try:
            # Find the title in metadata
            title_data = None
            for title in enhanced_metadata.get('titles', []):
                if title.get('title_number') == title_number:
                    title_data = title
                    break
            
            if not title_data:
                return audio_tracks, subtitle_tracks
            
            # Extract selected audio tracks
            selected_audio = title_data.get('selected_audio_tracks', [])
            for track_num in selected_audio:
                # Find track details in audio_tracks list
                for audio_track in title_data.get('audio_tracks', []):
                    if audio_track.get('TrackNumber') == track_num:
                        audio_tracks.append(AudioTrackSelection(
                            track_number=track_num,
                            language_code=audio_track.get('LanguageCode', ''),
                            description=audio_track.get('Description', ''),
                            selected=True
                        ))
                        break
            
            # Extract selected subtitle tracks
            selected_subtitles = title_data.get('selected_subtitle_tracks', [])
            for track_num in selected_subtitles:
                # Find track details in subtitle_tracks list
                for subtitle_track in title_data.get('subtitle_tracks', []):
                    if subtitle_track.get('TrackNumber') == track_num:
                        subtitle_tracks.append(SubtitleTrackSelection(
                            track_number=track_num,
                            language_code=subtitle_track.get('LanguageCode', ''),
                            name=subtitle_track.get('Name', ''),
                            selected=True
                        ))
                        break
            
        except Exception as e:
            logger.error(f"Error extracting metadata tracks: {e}")
        
        return audio_tracks, subtitle_tracks
    
    def generate_output_filename(self, movie_name: str, release_date: str, 
                               template_name: str) -> str:
        """
        Generate output filename based on movie metadata and template
        
        Args:
            movie_name: Movie name from metadata
            release_date: Release date from metadata
            template_name: Template name
            
        Returns:
            Generated filename
        """
        try:
            # Get template for file extension
            template = self.get_template(template_name)
            extension = template.get_file_extension() if template else 'mp4'
            
            # Sanitize movie name for filename
            safe_name = self._sanitize_filename(movie_name)
            
            # Add release year if available
            if release_date and len(release_date) >= 4:
                try:
                    year = release_date[:4]
                    if year.isdigit():
                        safe_name += f" ({year})"
                except:
                    pass
            
            return f"{safe_name}.{extension}"
            
        except Exception as e:
            logger.error(f"Error generating output filename: {e}")
            return f"{self._sanitize_filename(movie_name)}.mp4"
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for filesystem compatibility
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace problematic characters
        import re
        
        # Replace problematic characters with underscores
        sanitized = re.sub(r'[<>"/\\|?*]', '_', filename)
        
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
        
        # Limit length and strip whitespace
        sanitized = sanitized.strip()[:200]
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "movie"
        
        return sanitized
