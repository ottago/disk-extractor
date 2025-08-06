"""
Encoding Engine for Disk Extractor

Manages HandBrake encoding jobs, queue processing, and progress tracking.
"""

import os
import json
import logging
import subprocess
import threading
import time
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future

from config import Config
from models.encoding_models import (
    EncodingJob, EncodingProgress, EncodingHistory, EncodingStatus, 
    EncodingPhase, EncodingSettings, ExtendedMetadata
)
from utils.validation import validate_filename

logger = logging.getLogger(__name__)


class EncodingEngine:
    """Main encoding engine for managing HandBrake jobs"""
    
    def __init__(self, metadata_manager=None):
        """
        Initialize the encoding engine
        
        Args:
            metadata_manager: Reference to MovieMetadataManager
        """
        self.metadata_manager = metadata_manager
        self.settings = EncodingSettings.get_default()
        self.encoding_queue: Queue = Queue()
        self.active_jobs: Dict[str, EncodingJob] = {}  # job_id -> EncodingJob
        self.job_processes: Dict[str, subprocess.Popen] = {}  # job_id -> process
        self.job_futures: Dict[str, Future] = {}  # job_id -> future
        self.executor: Optional[ThreadPoolExecutor] = None
        self.progress_callbacks: List[Callable[[str, EncodingProgress], None]] = []
        self.status_callbacks: List[Callable[[str, EncodingStatus], None]] = []
        self.running = False
        self.queue_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Load settings
        self._load_settings()
    
    def start(self) -> None:
        """Start the encoding engine"""
        with self._lock:
            if self.running:
                return
            
            self.running = True
            self.executor = ThreadPoolExecutor(
                max_workers=self.settings.max_concurrent_encodes,
                thread_name_prefix="encoding"
            )
            
            # Start queue processing thread
            self.queue_thread = threading.Thread(
                target=self._process_queue,
                name="encoding_queue",
                daemon=True
            )
            self.queue_thread.start()
            
            logger.info(f"Encoding engine started with {self.settings.max_concurrent_encodes} workers")
    
    def stop(self) -> None:
        """Stop the encoding engine and cancel all jobs"""
        with self._lock:
            if not self.running:
                return
            
            logger.info("Stopping encoding engine...")
            self.running = False
            
            # Cancel all active jobs
            for job_id in list(self.active_jobs.keys()):
                self.cancel_job(job_id)
            
            # Shutdown executor
            if self.executor:
                self.executor.shutdown(wait=True)
                self.executor = None
            
            # Wait for queue thread to finish
            if self.queue_thread and self.queue_thread.is_alive():
                self.queue_thread.join(timeout=5.0)
            
            logger.info("Encoding engine stopped")
    
    def add_progress_callback(self, callback: Callable[[str, EncodingProgress], None]) -> None:
        """Add progress update callback"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[str, EncodingStatus], None]) -> None:
        """Add status change callback"""
        self.status_callbacks.append(callback)
    
    def _notify_progress(self, job_id: str, progress: EncodingProgress) -> None:
        """Notify all progress callbacks"""
        for callback in self.progress_callbacks:
            try:
                callback(job_id, progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def _notify_status_change(self, job_id: str, status: EncodingStatus) -> None:
        """Notify all status callbacks"""
        for callback in self.status_callbacks:
            try:
                callback(job_id, status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    def queue_encoding_job(self, file_name: str, title_number: int, movie_name: str, 
                          preset_name: str = None) -> str:
        """
        Queue an encoding job
        
        Args:
            file_name: Source .img file name
            title_number: Title number to encode
            movie_name: Movie name for output filename
            preset_name: HandBrake preset to use
            
        Returns:
            Job ID
        """
        # Validate inputs
        file_name = validate_filename(file_name)
        
        if not preset_name:
            preset_name = self.settings.default_preset
        
        # Generate job ID
        job_id = f"{file_name}_{title_number}_{uuid.uuid4().hex[:8]}"
        
        # Generate output filename
        output_filename = self._generate_output_filename(movie_name, preset_name)
        
        # Create encoding job
        job = EncodingJob(
            file_name=file_name,
            title_number=title_number,
            movie_name=movie_name,
            output_filename=output_filename,
            preset_name=preset_name,
            status=EncodingStatus.QUEUED,
            queue_position=self.encoding_queue.qsize() + 1
        )
        
        # Add to queue
        self.encoding_queue.put((job_id, job))
        
        # Update metadata
        self._update_job_in_metadata(job_id, job)
        
        logger.info(f"Queued encoding job: {job_id} - {movie_name}")
        self._notify_status_change(job_id, EncodingStatus.QUEUED)
        
        return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel an encoding job
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        with self._lock:
            # Check if job is active
            if job_id in self.active_jobs:
                job = self.active_jobs[job_id]
                
                # Kill the process if running
                if job_id in self.job_processes:
                    try:
                        process = self.job_processes[job_id]
                        process.terminate()
                        
                        # Wait a bit for graceful termination
                        try:
                            process.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        
                        del self.job_processes[job_id]
                    except Exception as e:
                        logger.error(f"Error killing process for job {job_id}: {e}")
                
                # Cancel the future
                if job_id in self.job_futures:
                    future = self.job_futures[job_id]
                    future.cancel()
                    del self.job_futures[job_id]
                
                # Update job status
                job.status = EncodingStatus.CANCELLED
                job.completed_at = datetime.now().isoformat()
                
                # Clean up output file if it exists
                self._cleanup_output_file(job)
                
                # Remove from active jobs
                del self.active_jobs[job_id]
                
                # Update metadata
                self._update_job_in_metadata(job_id, job)
                
                logger.info(f"Cancelled encoding job: {job_id}")
                self._notify_status_change(job_id, EncodingStatus.CANCELLED)
                
                return True
            
            # TODO: Remove from queue if not yet started
            logger.warning(f"Job {job_id} not found in active jobs")
            return False
    
    def get_job_status(self, job_id: str) -> Optional[EncodingJob]:
        """Get current status of a job"""
        with self._lock:
            if job_id in self.active_jobs:
                return self.active_jobs[job_id]
            
            # Check in metadata for completed/failed jobs
            if self.metadata_manager:
                for movie in self.metadata_manager.movies:
                    metadata = self.metadata_manager.load_metadata(movie['file_name'])
                    jobs = ExtendedMetadata.get_encoding_jobs(metadata)
                    for job in jobs:
                        if f"{job.file_name}_{job.title_number}" in job_id:
                            return job
            
            return None
    
    def get_all_jobs(self) -> List[EncodingJob]:
        """Get all jobs (active and from metadata)"""
        jobs = []
        
        # Add active jobs
        with self._lock:
            jobs.extend(self.active_jobs.values())
        
        # Add jobs from metadata
        if self.metadata_manager:
            for movie in self.metadata_manager.movies:
                try:
                    metadata = self.metadata_manager.load_metadata(movie['file_name'])
                    metadata_jobs = ExtendedMetadata.get_encoding_jobs(metadata)
                    
                    # Only add jobs not already in active jobs
                    for job in metadata_jobs:
                        job_key = f"{job.file_name}_{job.title_number}"
                        if not any(job_key in active_id for active_id in self.active_jobs.keys()):
                            jobs.append(job)
                except Exception as e:
                    logger.error(f"Error loading jobs from {movie['file_name']}: {e}")
        
        return jobs
    
    def _process_queue(self) -> None:
        """Main queue processing loop"""
        logger.info("Queue processing thread started")
        
        while self.running:
            try:
                # Check if we can start more jobs
                with self._lock:
                    active_count = len(self.active_jobs)
                    max_concurrent = self.settings.max_concurrent_encodes
                
                if active_count >= max_concurrent:
                    time.sleep(1.0)
                    continue
                
                # Get next job from queue
                try:
                    job_id, job = self.encoding_queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # Start the job
                self._start_encoding_job(job_id, job)
                
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
                time.sleep(1.0)
        
        logger.info("Queue processing thread stopped")
    
    def _start_encoding_job(self, job_id: str, job: EncodingJob) -> None:
        """Start an individual encoding job"""
        with self._lock:
            if not self.running or not self.executor:
                return
            
            # Add to active jobs
            self.active_jobs[job_id] = job
            job.status = EncodingStatus.ENCODING
            job.started_at = datetime.now().isoformat()
            
            # Submit to executor
            future = self.executor.submit(self._execute_encoding_job, job_id, job)
            self.job_futures[job_id] = future
            
            # Update metadata
            self._update_job_in_metadata(job_id, job)
            
            logger.info(f"Started encoding job: {job_id}")
            self._notify_status_change(job_id, EncodingStatus.ENCODING)
    
    def _execute_encoding_job(self, job_id: str, job: EncodingJob) -> None:
        """Execute the actual encoding job"""
        try:
            # Build HandBrake command
            cmd = self._build_handbrake_command(job)
            
            logger.info(f"Executing HandBrake command for {job_id}: {' '.join(cmd)}")
            
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Store process reference
            with self._lock:
                self.job_processes[job_id] = process
            
            # Monitor progress
            self._monitor_encoding_progress(job_id, job, process)
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            # Clean up process reference
            with self._lock:
                if job_id in self.job_processes:
                    del self.job_processes[job_id]
            
            # Handle completion
            if process.returncode == 0:
                self._handle_job_completion(job_id, job, True)
            else:
                error_msg = f"HandBrake failed with exit code {process.returncode}: {stderr}"
                self._handle_job_completion(job_id, job, False, error_msg)
                
        except Exception as e:
            error_msg = f"Encoding job failed: {str(e)}"
            logger.error(f"Error in encoding job {job_id}: {e}")
            self._handle_job_completion(job_id, job, False, error_msg)
    
    def _build_handbrake_command(self, job: EncodingJob) -> List[str]:
        """Build HandBrake CLI command"""
        if not self.metadata_manager or not self.metadata_manager.directory:
            raise ValueError("No metadata manager or directory set")
        
        input_path = self.metadata_manager.directory / job.file_name
        output_path = Path(self.settings.output_directory) / job.output_filename
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Store output path in job
        job.output_path = str(output_path)
        
        # Base command
        cmd = [
            Config.HANDBRAKE_CLI_PATH,
            '--input', str(input_path),
            '--output', str(output_path),
            '--title', str(job.title_number)
        ]
        
        # Add preset if available
        if job.preset_name:
            cmd.extend(['--preset', job.preset_name])
        
        # Add testing mode parameters if enabled
        if self.settings.testing_mode:
            cmd.extend([
                '--start-at', 'seconds:0',
                '--stop-at', f'seconds:{self.settings.test_duration_seconds}'
            ])
        
        # TODO: Add audio/subtitle track selection from metadata
        # TODO: Add custom preset parameters from uploaded template
        
        return cmd
    
    def _monitor_encoding_progress(self, job_id: str, job: EncodingJob, process: subprocess.Popen) -> None:
        """Monitor encoding progress in a separate thread"""
        def monitor():
            try:
                while process.poll() is None:
                    if not self.running:
                        break
                    
                    # Read stderr for progress information
                    if process.stderr:
                        line = process.stderr.readline()
                        if line:
                            progress = self._parse_handbrake_progress(line.strip())
                            if progress:
                                job.progress = progress
                                self._notify_progress(job_id, progress)
                                
                                # Update metadata periodically
                                if progress.percentage % 5 == 0:  # Every 5%
                                    self._update_job_in_metadata(job_id, job)
                    
                    time.sleep(self.settings.progress_update_interval)
                    
            except Exception as e:
                logger.error(f"Error monitoring progress for {job_id}: {e}")
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def _parse_handbrake_progress(self, line: str) -> Optional[EncodingProgress]:
        """Parse HandBrake progress from stderr output"""
        try:
            # HandBrake progress format: "Encoding: task 1 of 1, 45.67 % (123.45 fps, avg 98.76 fps, ETA 01h23m45s)"
            progress_match = re.search(r'Encoding:.*?(\d+\.?\d*)\s*%.*?(\d+\.?\d*)\s*fps.*?ETA\s*(\d+h)?(\d+m)?(\d+s)?', line)
            
            if progress_match:
                percentage = float(progress_match.group(1))
                fps = float(progress_match.group(2))
                
                # Parse ETA
                eta_hours = int(progress_match.group(3)[:-1]) if progress_match.group(3) else 0
                eta_minutes = int(progress_match.group(4)[:-1]) if progress_match.group(4) else 0
                eta_seconds = int(progress_match.group(5)[:-1]) if progress_match.group(5) else 0
                
                time_remaining = eta_hours * 3600 + eta_minutes * 60 + eta_seconds
                
                return EncodingProgress(
                    percentage=percentage,
                    fps=fps,
                    time_remaining=time_remaining,
                    phase=EncodingPhase.ENCODING,
                    last_updated=datetime.now().isoformat()
                )
            
            # Check for scanning phase
            if "Scanning title" in line:
                return EncodingProgress(
                    percentage=0.0,
                    phase=EncodingPhase.SCANNING,
                    last_updated=datetime.now().isoformat()
                )
            
            # Check for muxing phase
            if "Muxing" in line:
                return EncodingProgress(
                    percentage=99.0,
                    phase=EncodingPhase.MUXING,
                    last_updated=datetime.now().isoformat()
                )
                
        except Exception as e:
            logger.debug(f"Error parsing progress line '{line}': {e}")
        
        return None
    
    def _handle_job_completion(self, job_id: str, job: EncodingJob, success: bool, error_msg: str = "") -> None:
        """Handle job completion"""
        with self._lock:
            # Update job status
            if success:
                job.status = EncodingStatus.COMPLETED
                job.progress.percentage = 100.0
                job.progress.phase = EncodingPhase.COMPLETED
                logger.info(f"Encoding job completed successfully: {job_id}")
            else:
                job.status = EncodingStatus.FAILED
                job.error_message = error_msg
                logger.error(f"Encoding job failed: {job_id} - {error_msg}")
                
                # Clean up failed output file
                self._cleanup_output_file(job)
            
            job.completed_at = datetime.now().isoformat()
            
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            # Clean up future reference
            if job_id in self.job_futures:
                del self.job_futures[job_id]
            
            # Update metadata and add to history
            self._update_job_in_metadata(job_id, job)
            self._add_job_to_history(job)
            
            # Notify status change
            self._notify_status_change(job_id, job.status)
    
    def _cleanup_output_file(self, job: EncodingJob) -> None:
        """Clean up output file on failure/cancellation"""
        if job.output_path and os.path.exists(job.output_path):
            try:
                os.remove(job.output_path)
                logger.info(f"Cleaned up output file: {job.output_path}")
            except Exception as e:
                logger.error(f"Error cleaning up output file {job.output_path}: {e}")
    
    def _generate_output_filename(self, movie_name: str, preset_name: str) -> str:
        """Generate output filename based on movie name and preset"""
        # Sanitize movie name for filename
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', movie_name)
        
        # Get file extension from preset (default to mp4)
        extension = "mp4"  # TODO: Extract from preset
        
        return f"{safe_name}.{extension}"
    
    def _update_job_in_metadata(self, job_id: str, job: EncodingJob) -> None:
        """Update job in metadata file"""
        if not self.metadata_manager:
            return
        
        try:
            metadata = self.metadata_manager.load_metadata(job.file_name)
            jobs = ExtendedMetadata.get_encoding_jobs(metadata)
            
            # Find and update existing job or add new one
            job_updated = False
            for i, existing_job in enumerate(jobs):
                if (existing_job.file_name == job.file_name and 
                    existing_job.title_number == job.title_number and
                    existing_job.movie_name == job.movie_name):
                    jobs[i] = job
                    job_updated = True
                    break
            
            if not job_updated:
                jobs.append(job)
            
            # Update metadata
            metadata = ExtendedMetadata.set_encoding_jobs(metadata, jobs)
            self.metadata_manager.save_metadata(job.file_name, metadata)
            
        except Exception as e:
            logger.error(f"Error updating job in metadata: {e}")
    
    def _add_job_to_history(self, job: EncodingJob) -> None:
        """Add completed job to encoding history"""
        if not self.metadata_manager:
            return
        
        try:
            # Calculate encoding time
            encoding_time = 0
            if job.started_at and job.completed_at:
                start_time = datetime.fromisoformat(job.started_at)
                end_time = datetime.fromisoformat(job.completed_at)
                encoding_time = int((end_time - start_time).total_seconds())
            
            # Get output file size
            output_size_mb = 0.0
            if job.output_path and os.path.exists(job.output_path):
                output_size_mb = os.path.getsize(job.output_path) / (1024 * 1024)
            
            # Create history entry
            history_entry = EncodingHistory(
                attempt_id=f"{job.file_name}_{job.title_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                started_at=job.started_at,
                completed_at=job.completed_at,
                status=job.status,
                output_size_mb=output_size_mb,
                encoding_time_seconds=encoding_time,
                error_message=job.error_message,
                preset_used=job.preset_name
            )
            
            # Add to metadata
            metadata = self.metadata_manager.load_metadata(job.file_name)
            metadata = ExtendedMetadata.add_encoding_history(metadata, history_entry)
            self.metadata_manager.save_metadata(job.file_name, metadata)
            
        except Exception as e:
            logger.error(f"Error adding job to history: {e}")
    
    def _load_settings(self) -> None:
        """Load encoding settings from file"""
        settings_path = Path("encoding_settings.json")
        
        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    settings_data = json.load(f)
                    self.settings = EncodingSettings.from_dict(settings_data)
                logger.info("Loaded encoding settings from file")
            except Exception as e:
                logger.error(f"Error loading encoding settings: {e}")
                self.settings = EncodingSettings.get_default()
        else:
            self.settings = EncodingSettings.get_default()
            self._save_settings()
    
    def _save_settings(self) -> None:
        """Save encoding settings to file"""
        settings_path = Path("encoding_settings.json")
        
        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
            logger.info("Saved encoding settings to file")
        except Exception as e:
            logger.error(f"Error saving encoding settings: {e}")
    
    def update_settings(self, new_settings: EncodingSettings) -> None:
        """Update encoding settings"""
        old_max_concurrent = self.settings.max_concurrent_encodes
        self.settings = new_settings
        self._save_settings()
        
        # Restart executor if max concurrent changed
        if (old_max_concurrent != new_settings.max_concurrent_encodes and 
            self.running and self.executor):
            
            logger.info(f"Restarting executor with {new_settings.max_concurrent_encodes} workers")
            
            # Don't interrupt running jobs, just change the executor
            old_executor = self.executor
            self.executor = ThreadPoolExecutor(
                max_workers=new_settings.max_concurrent_encodes,
                thread_name_prefix="encoding"
            )
            
            # Shutdown old executor (will wait for current jobs to finish)
            threading.Thread(target=lambda: old_executor.shutdown(wait=True), daemon=True).start()
    
    def get_settings(self) -> EncodingSettings:
        """Get current encoding settings"""
        return self.settings
