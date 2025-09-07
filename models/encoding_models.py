"""
Encoding data models for Disk Extractor

Defines data structures for encoding jobs, progress tracking, and settings.
"""

from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class EncodingStatus(Enum):
    """Encoding status enumeration"""
    NOT_QUEUED = "not_queued"
    QUEUED = "queued"
    ENCODING = "encoding"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EncodingPhase(Enum):
    """Current phase of encoding process"""
    SCANNING = "scanning"
    ENCODING = "encoding"
    MUXING = "muxing"
    COMPLETED = "completed"


@dataclass
class EncodingProgress:
    """Real-time encoding progress data"""
    percentage: float = 0.0
    fps: float = 0.0
    time_elapsed: int = 0  # seconds
    time_remaining: int = 0  # seconds
    current_pass: int = 1
    total_passes: int = 1
    phase: EncodingPhase = EncodingPhase.SCANNING
    average_bitrate: float = 0.0
    output_size_mb: float = 0.0
    last_updated: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['phase'] = self.phase.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncodingProgress':
        """Create from dictionary"""
        if 'phase' in data and isinstance(data['phase'], str):
            data['phase'] = EncodingPhase(data['phase'])
        return cls(**data)


@dataclass
class EncodingJob:
    """Individual encoding job data"""
    file_name: str
    title_number: int
    movie_name: str
    output_filename: str
    preset_name: str
    status: EncodingStatus = EncodingStatus.NOT_QUEUED
    queue_position: int = 0
    job_id: str = ""  # Backend-generated job ID for tracking
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    progress: Optional[EncodingProgress] = None
    error_message: str = ""
    failure_logs: List[str] = None  # Last 100 lines of output when job fails
    output_path: str = ""
    output_size_mb: float = 0.0  # Size of output file in MB
    
    def __post_init__(self):
        """Initialize default values"""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.progress is None:
            self.progress = EncodingProgress()
        if self.failure_logs is None:
            self.failure_logs = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        if self.progress:
            data['progress'] = self.progress.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncodingJob':
        """Create from dictionary"""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = EncodingStatus(data['status'])
        if 'progress' in data and isinstance(data['progress'], dict):
            data['progress'] = EncodingProgress.from_dict(data['progress'])
        return cls(**data)


@dataclass
class EncodingHistory:
    """Historical encoding attempt data"""
    attempt_id: str
    started_at: str
    completed_at: str
    status: EncodingStatus
    output_size_mb: float = 0.0
    encoding_time_seconds: int = 0
    error_message: str = ""
    preset_used: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncodingHistory':
        """Create from dictionary"""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = EncodingStatus(data['status'])
        return cls(**data)


class ExtendedMetadata:
    """Extended metadata structure with encoding support"""
    
    @staticmethod
    def get_default_structure(file_name: str, size_mb: float = 0.0) -> Dict[str, Any]:
        """Get default metadata structure with encoding fields"""
        return ExtendedMetadata.ensure_encoding_structure({
            'file_name': file_name,
            'size_mb': size_mb,
            'titles': []
        })
    
    @staticmethod
    def ensure_encoding_structure(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure metadata has encoding structure"""
        if 'encoding' not in metadata:
            metadata['encoding'] = {
                'jobs': [],     # List of EncodingJob dictionaries
                'history': [],  # List of EncodingHistory dictionaries
                'settings': {
                    'output_directory': '',
                    'preset_name': '',
                    'testing_mode': False,
                    'test_duration_seconds': 60
                }
            }
            return metadata
        
        # Ensure all encoding sub-structures exist
        if 'jobs' not in metadata['encoding']:
            metadata['encoding']['jobs'] = []
        if 'history' not in metadata['encoding']:
            metadata['encoding']['history'] = []
        if 'settings' not in metadata['encoding']:
            metadata['encoding']['settings'] = {
                'output_directory': '',
                'preset_name': '',
                'testing_mode': False,
                'test_duration_seconds': 60
            }
        
        return metadata
    
    @staticmethod
    def get_encoding_jobs(metadata: Dict[str, Any]) -> List[EncodingJob]:
        """Get list of encoding jobs from metadata"""
        metadata = ExtendedMetadata.ensure_encoding_structure(metadata)
        jobs = []
        for job_data in metadata['encoding']['jobs']:
            try:
                jobs.append(EncodingJob.from_dict(job_data))
            except (KeyError, ValueError) as e:
                # Skip invalid job data
                continue
        return jobs
    
    @staticmethod
    def set_encoding_jobs(metadata: Dict[str, Any], jobs: List[EncodingJob]) -> Dict[str, Any]:
        """Set encoding jobs in metadata"""
        metadata = ExtendedMetadata.ensure_encoding_structure(metadata)
        metadata['encoding']['jobs'] = [job.to_dict() for job in jobs]
        return metadata
    
    @staticmethod
    def get_encoding_history(metadata: Dict[str, Any]) -> List[EncodingHistory]:
        """Get encoding history from metadata"""
        metadata = ExtendedMetadata.ensure_encoding_structure(metadata)
        history = []
        for history_data in metadata['encoding']['history']:
            try:
                history.append(EncodingHistory.from_dict(history_data))
            except (KeyError, ValueError) as e:
                # Skip invalid history data
                continue
        return history
    
    @staticmethod
    def add_encoding_history(metadata: Dict[str, Any], history_entry: EncodingHistory) -> Dict[str, Any]:
        """Add encoding history entry to metadata"""
        metadata = ExtendedMetadata.ensure_encoding_structure(metadata)
        metadata['encoding']['history'].append(history_entry.to_dict())
        
        # Keep only last 10 history entries to prevent file bloat
        if len(metadata['encoding']['history']) > 10:
            metadata['encoding']['history'] = metadata['encoding']['history'][-10:]
        
        return metadata
    
    @staticmethod
    def get_file_encoding_status(metadata: Dict[str, Any]) -> EncodingStatus:
        """Get overall encoding status for a file"""
        jobs = ExtendedMetadata.get_encoding_jobs(metadata)
        
        if not jobs:
            return EncodingStatus.NOT_QUEUED
        
        # Check if any job is currently encoding
        for job in jobs:
            if job.status == EncodingStatus.ENCODING:
                return EncodingStatus.ENCODING
        
        # Check if any job is queued
        for job in jobs:
            if job.status == EncodingStatus.QUEUED:
                return EncodingStatus.QUEUED
        
        # Check if all jobs are completed
        completed_jobs = [job for job in jobs if job.status == EncodingStatus.COMPLETED]
        if len(completed_jobs) == len(jobs):
            return EncodingStatus.COMPLETED
        
        # Check if any job failed
        for job in jobs:
            if job.status == EncodingStatus.FAILED:
                return EncodingStatus.FAILED
        
        return EncodingStatus.NOT_QUEUED
    
    @staticmethod
    def get_active_encoding_jobs(metadata: Dict[str, Any]) -> List[EncodingJob]:
        """Get currently active (encoding) jobs"""
        jobs = ExtendedMetadata.get_encoding_jobs(metadata)
        return [job for job in jobs if job.status == EncodingStatus.ENCODING]
    
    @staticmethod
    def get_queued_encoding_jobs(metadata: Dict[str, Any]) -> List[EncodingJob]:
        """Get queued encoding jobs"""
        jobs = ExtendedMetadata.get_encoding_jobs(metadata)
        return [job for job in jobs if job.status == EncodingStatus.QUEUED]


@dataclass
class EncodingSettings:
    """Global encoding settings"""
    max_concurrent_encodes: int = 2
    testing_mode: bool = False
    test_duration_seconds: int = 60
    output_directory: str = ""
    default_preset: str = "Fast 1080p30"
    auto_queue_new_files: bool = False
    progress_update_interval: int = 3  # seconds
    notification_settings: Dict[str, bool] = None
    stats_for_nerds: bool = False  # Show detailed system stats
    
    def __post_init__(self):
        """Initialize default values"""
        if self.notification_settings is None:
            self.notification_settings = {
                "on_completion": True,
                "on_failure": True,
                "on_queue_empty": True
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncodingSettings':
        """Create from dictionary"""
        return cls(**data)
    
    @classmethod
    def get_default(cls) -> 'EncodingSettings':
        """Get default encoding settings"""
        return cls()
