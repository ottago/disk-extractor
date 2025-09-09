"""
Test configuration and utilities
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock


class TestConfig:
    """Test configuration constants"""
    
    # Test timeouts
    DEFAULT_TIMEOUT = 30
    HANDBRAKE_TIMEOUT = 10
    
    # Test file sizes
    SMALL_FILE_SIZE = 1024  # 1KB
    MEDIUM_FILE_SIZE = 1024 * 1024  # 1MB
    
    # Mock HandBrake output
    MOCK_HANDBRAKE_OUTPUT = """
+ title 1:
  + duration: 02:00:00
  + size: 1920x1080, pixel aspect: 1/1, display aspect: 1.78, 23.976 fps
  + audio tracks:
    + 1, English (AC3) (5.1 ch) (iso639-2: eng)
    + 2, Spanish (AC3) (2.0 ch) (iso639-2: spa)
  + subtitle tracks:
    + 1, English (PGS) (iso639-2: eng)
    + 2, Spanish (PGS) (iso639-2: spa)
+ title 2:
  + duration: 00:30:00
  + size: 1920x1080, pixel aspect: 1/1, display aspect: 1.78, 23.976 fps
  + audio tracks:
    + 1, English (AC3) (2.0 ch) (iso639-2: eng)
  + subtitle tracks:
    + 1, English (PGS) (iso639-2: eng)
"""


class TestEnvironment:
    """Test environment manager"""
    
    def __init__(self):
        self.temp_dir = None
        self.temp_path = None
        self.original_env = {}
    
    def setup(self) -> Path:
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix="disk_extractor_test_")
        self.temp_path = Path(self.temp_dir)
        
        # Set test environment variables
        test_env = {
            'HANDBRAKE_TIMEOUT': str(TestConfig.HANDBRAKE_TIMEOUT),
            'MAX_CACHE_SIZE': '10',
            'CACHE_TTL': '60',
            'LOG_LEVEL': 'ERROR',  # Reduce log noise in tests
            'FILE_WATCHER_ENABLED': 'False',  # Disable file watcher in tests
            'FLASK_DEBUG': 'False'
        }
        
        for key, value in test_env.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        return self.temp_path
    
    def teardown(self):
        """Clean up test environment"""
        # Restore original environment
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        
        # Clean up temp directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_file(self, filename: str, size: int = TestConfig.SMALL_FILE_SIZE) -> Path:
        """Create a test file with specified size"""
        file_path = self.temp_path / filename
        file_path.write_bytes(b"x" * size)
        return file_path
    
    def create_test_metadata(self, filename: str, metadata: Dict[str, Any]) -> Path:
        """Create a test metadata file"""
        import json
        metadata_path = self.temp_path / f"{Path(filename).stem}.mmm"
        metadata_path.write_text(json.dumps(metadata, indent=2))
        return metadata_path


def create_mock_handbrake_scanner():
    """Create a mock HandBrake scanner for testing"""
    mock_scanner = Mock()
    
    # Mock successful scan
    mock_scanner.scan_file.return_value = {
        "titles": [
            {
                "title_number": 1,
                "duration_seconds": 7200,
                "video_info": {
                    "width": 1920,
                    "height": 1080,
                    "fps": 23.976,
                    "aspect_ratio": "1.78"
                },
                "audio_tracks": [
                    {
                        "track_number": 1,
                        "language": "English",
                        "codec": "AC3",
                        "channels": "5.1 ch"
                    }
                ],
                "subtitle_tracks": [
                    {
                        "track_number": 1,
                        "language": "English",
                        "format": "PGS"
                    }
                ]
            }
        ]
    }
    
    mock_scanner.test_handbrake.return_value = True
    mock_scanner.get_handbrake_version.return_value = "HandBrake 1.6.1 (Test)"
    
    return mock_scanner


def create_sample_metadata(filename: str) -> Dict[str, Any]:
    """Create sample metadata for testing"""
    return {
        "file_name": filename,
        "size_mb": 1000.0,
        "titles": [
            {
                "title_number": 1,
                "selected": True,
                "movie_name": "Test Movie",
                "release_date": "2023-01-01",
                "synopsis": "A test movie for unit testing",
                "duration_seconds": 7200,
                "audio_tracks": [
                    {
                        "track_number": 1,
                        "language": "English",
                        "codec": "AC3",
                        "channels": "5.1 ch",
                        "selected": True
                    }
                ],
                "subtitle_tracks": [
                    {
                        "track_number": 1,
                        "language": "English",
                        "format": "PGS",
                        "selected": False
                    }
                ],
                "selected_audio_tracks": [1],
                "selected_subtitle_tracks": []
            }
        ],
        "encoding": {
            "jobs": []
        }
    }


def create_sample_encoding_job() -> Dict[str, Any]:
    """Create sample encoding job for testing"""
    return {
        "file_name": "test.img",
        "title_number": 1,
        "movie_name": "Test Movie",
        "output_filename": "Test Movie (2023).mp4",
        "preset_name": "Fast 1080p30",
        "status": "queued",
        "queue_position": 1,
        "created_at": "2023-01-01T12:00:00",
        "progress": {
            "percentage": 0.0,
            "fps": 0.0,
            "phase": "scanning"
        }
    }


def create_sample_template() -> Dict[str, Any]:
    """Create sample HandBrake template for testing"""
    return {
        "PresetList": [
            {
                "PresetName": "Test Template",
                "PresetDescription": "A test template for unit testing",
                "VideoEncoder": "x264",
                "VideoQualityType": 1,
                "VideoQualitySlider": 22.0,
                "VideoFramerate": "auto",
                "VideoFramerateMode": "vfr",
                "AudioList": [
                    {
                        "AudioEncoder": "av_aac",
                        "AudioBitrate": 128,
                        "AudioSamplerate": "auto",
                        "AudioMixdown": "stereo"
                    }
                ],
                "SubtitleList": [],
                "PictureWidth": 1920,
                "PictureHeight": 1080,
                "PicturePAR": "auto"
            }
        ]
    }
