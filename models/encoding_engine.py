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
import select
import sys
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
from models.template_manager import TemplateManager
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
        self.template_manager = TemplateManager()
        self.settings = EncodingSettings.get_default()
        self.encoding_queue: Queue = Queue()
        self.active_jobs: Dict[str, EncodingJob] = {}  # job_id -> EncodingJob
        self.queued_jobs: Dict[str, EncodingJob] = {}  # job_id -> EncodingJob (for tracking queued jobs)
        self.job_processes: Dict[str, subprocess.Popen] = {}  # job_id -> process
        self.job_futures: Dict[str, Future] = {}  # job_id -> future
        self.executor: Optional[ThreadPoolExecutor] = None
        self.progress_callbacks: List[Callable[[str, EncodingProgress], None]] = []
        self.status_callbacks: List[Callable[[str, EncodingStatus], None]] = []
        self.running = False
        self.queue_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._queue_condition = threading.Condition(self._lock)  # For event-driven processing
        
        # Job cache to avoid frequent metadata file loading
        self._jobs_cache: Optional[List[EncodingJob]] = None
        self._jobs_cache_timestamp: float = 0
        self._jobs_cache_lock = threading.RLock()
        
        # Load settings
        self._load_settings()
        
        # Register for metadata change notifications if metadata_manager is available
        if self.metadata_manager:
            self.metadata_manager.add_change_callback(self._on_metadata_change)
        
        # Notification callbacks
        self._notification_callbacks = []
    
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
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get encoding jobs cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        with self._jobs_cache_lock:
            current_time = time.time()
            cache_age = current_time - self._jobs_cache_timestamp if self._jobs_cache_timestamp > 0 else 0
            
            return {
                'has_cache': self._jobs_cache is not None,
                'cache_size': len(self._jobs_cache) if self._jobs_cache else 0,
                'cache_age_seconds': round(cache_age, 2),
                'cache_ttl_seconds': Config.ENCODING_JOBS_CACHE_TTL,
                'cache_valid': (self._jobs_cache is not None and 
                               cache_age < Config.ENCODING_JOBS_CACHE_TTL)
            }
    
    def stop(self) -> None:
        """Stop the encoding engine and cancel all jobs"""
        with self._lock:
            if not self.running:
                return
            
            logger.info("Stopping encoding engine...")
            self.running = False
            
            # Wake up the queue processor so it can exit
            with self._queue_condition:
                self._queue_condition.notify()
            
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
        logger.debug(f"Notifying progress for {job_id}: {progress.percentage}% ({progress.phase})")
        for callback in self.progress_callbacks:
            try:
                callback(job_id, progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def _notify_status_change(self, job_id: str, status: EncodingStatus) -> None:
        """Notify all status callbacks"""
        logger.info(f"Encoding Job {job_id} -> {status}")
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
        
        # Track queued job
        with self._lock:
            self.queued_jobs[job_id] = job
        
        # Notify queue processor that a new job is available
        with self._queue_condition:
            self._queue_condition.notify()
        
        # Update metadata
        self._persist_job_status(job_id, job)
        
        # Invalidate jobs cache since we added a new job
        # FIXME: Do we really need to invalidate the chache or can we just update it?
        self._invalidate_jobs_cache()
        
        self._notify_status_change(job_id, job.status)
        
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
                self._persist_job_status(job_id, job)
                
                # Invalidate jobs cache since job status changed
                # FIXME: Do we really need to invalidate the cache or just update it?
                self._invalidate_jobs_cache()
                
                self._notify_status_change(job_id, job.status)
                
                return True
            
            # Check if job is queued
            if job_id in self.queued_jobs:
                job = self.queued_jobs[job_id]
                
                # Remove from queue tracking
                del self.queued_jobs[job_id]
                
                # Update job status
                job.status = EncodingStatus.CANCELLED
                job.completed_at = datetime.now().isoformat()
                
                # Update metadata
                self._persist_job_status(job_id, job)
                
                # Invalidate jobs cache since job status changed
                self._invalidate_jobs_cache()
                
                self._notify_status_change(job_id, job.status)
                
                logger.info(f"Cancelled queued job {job_id}")
                return True
            
            logger.warning(f"Job {job_id} not found in active or queued jobs")
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
    
    def _on_metadata_change(self, change_type: str, filename: Optional[str] = None) -> None:
        """Handle metadata changes to invalidate job cache"""
        with self._jobs_cache_lock:
            if self._jobs_cache is not None:
                logger.debug(f"Invalidating jobs cache due to metadata change: {change_type} - {filename}")
                self._jobs_cache = None
                self._jobs_cache_timestamp = 0
    
    def _invalidate_jobs_cache(self) -> None:
        """Manually invalidate the jobs cache"""
        with self._jobs_cache_lock:
            self._jobs_cache = None
            self._jobs_cache_timestamp = 0
            logger.debug("Jobs cache manually invalidated")
    
    def get_all_jobs(self) -> List[EncodingJob]:
        """Get all jobs (active and from metadata) with caching"""
        current_time = time.time()
        
        # Check if we have a valid cache
        with self._jobs_cache_lock:
            if (self._jobs_cache is not None and 
                current_time - self._jobs_cache_timestamp < Config.ENCODING_JOBS_CACHE_TTL):
                # NKW logger.debug(f"Returning {len(self._jobs_cache)} cached jobs")
                return self._jobs_cache.copy()
        
        # Cache miss or expired, rebuild the jobs list
        logger.debug("Rebuilding jobs cache")
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
        
        # Cache the results
        with self._jobs_cache_lock:
            self._jobs_cache = jobs.copy()
            self._jobs_cache_timestamp = current_time
            logger.debug(f"Cached {len(jobs)} jobs")
        
        return jobs
    
    def get_queued_job_ids(self) -> Dict[str, str]:
        """
        Get job IDs for all queued jobs
        
        Returns:
            Dictionary mapping job_key (file_name_title_number) to job_id
        """
        queued_job_ids = {}
        
        with self._lock:
            for job_id, job in self.queued_jobs.items():
                job_key = f"{job.file_name}_{job.title_number}"
                queued_job_ids[job_key] = job_id
        
        return queued_job_ids
    
    def _process_queue(self) -> None:
        """Main queue processing loop - event-driven, no polling"""
        logger.info("Queue processing thread started (event-driven)")
        
        while self.running:
            try:
                with self._queue_condition:
                    # Wait for either:
                    # 1. New job in queue AND available worker slot
                    # 2. Job completion (which frees up a slot)
                    # 3. Shutdown signal
                    while self.running:
                        active_count = len(self.active_jobs)
                        max_concurrent = self.settings.max_concurrent_encodes
                        
                        # Check if we can start a job
                        if active_count < max_concurrent and not self.encoding_queue.empty():
                            break
                        
                        # Wait for notification (job added, job completed, or shutdown)
                        logger.debug(f"Waiting for queue event ({active_count}/{max_concurrent} active)")
                        self._queue_condition.wait()
                    
                    if not self.running:
                        break
                
                # Get next job from queue (non-blocking since we know it's not empty)
                try:
                    job_id, job = self.encoding_queue.get_nowait()
                    logger.debug(f"Got job from queue: {job_id}")
                except:
                    # Queue became empty between check and get - continue loop
                    continue
                
                # Start the job
                self._start_encoding_job(job_id, job)
                
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
                time.sleep(10.0)  # Pause on error
        
        logger.info("Queue processing thread stopped")
    
    def _start_encoding_job(self, job_id: str, job: EncodingJob) -> None:
        """Start an individual encoding job"""
        with self._lock:
            logger.debug(f"Starting encode of {job_id}")
            if not self.running or not self.executor:
                return
            
            # Remove from queued jobs tracking
            self.queued_jobs.pop(job_id, None)
            
            # Add to active jobs
            self.active_jobs[job_id] = job
            job.status = EncodingStatus.ENCODING
            job.started_at = datetime.now().isoformat()
            
            # Submit to executor
            future = self.executor.submit(self._execute_encoding_job, job_id, job)
            self.job_futures[job_id] = future
            
            # Update metadata
            self._persist_job_status(job_id, job)
            
            # Invalidate cache since active jobs changed
            # FIXME: Do we really need to invalidate the cache or just update it?
            self._invalidate_jobs_cache()
            
            self._notify_status_change(job_id, job.status)
    
    def _execute_encoding_job(self, job_id: str, job: EncodingJob) -> None:
        """Execute the actual encoding job"""
        try:
            # Build HandBrake command
            cmd = self._build_handbrake_command(job)
            
            logger.info(f"Executing HandBrake command for {job_id}: {' '.join(cmd)}")
            
            # Start the process with stderr redirected to stdout
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                universal_newlines=False,  # Raw bytes mode
                bufsize=0                  # Unbuffered
            )
            
            # Store process reference
            with self._lock:
                self.job_processes[job_id] = process
            
            # Monitor progress and wait for completion in the same thread
            all_output = []
            output_buffer = b''  # Buffer for incomplete lines
            
            # Use select() to efficiently wait for output
            while process.poll() is None:
                if not self.running:
                    process.terminate()
                    break
                
                # Wait for data to be available on stdout (which includes stderr)
                # Use a short timeout to check process status periodically
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                
                if ready:
                    # Data is available, read it
                    chunk = process.stdout.read(4096)
                    if chunk:
                        output_buffer += chunk
                        
                        # Process all complete lines in the buffer
                        while True:
                            # Look for line terminators (prioritize \n over \r for proper line handling)
                            newline_pos = output_buffer.find(b'\n')
                            carriage_pos = output_buffer.find(b'\r')
                            
                            # Determine which terminator comes first
                            if newline_pos == -1 and carriage_pos == -1:
                                # No terminators found, break and wait for more data
                                break
                            elif newline_pos == -1:
                                # Only carriage return found
                                terminator_pos = carriage_pos
                                terminator = b'\r'
                            elif carriage_pos == -1:
                                # Only newline found
                                terminator_pos = newline_pos
                                terminator = b'\n'
                            else:
                                # Both found, use the one that comes first
                                if newline_pos < carriage_pos:
                                    terminator_pos = newline_pos
                                    terminator = b'\n'
                                else:
                                    terminator_pos = carriage_pos
                                    terminator = b'\r'
                            
                            # Extract the line (everything before the terminator)
                            line_bytes = output_buffer[:terminator_pos]
                            
                            # Remove the processed line and terminator from buffer
                            output_buffer = output_buffer[terminator_pos + 1:]
                            
                            # Handle \r\n sequences (Windows line endings)
                            if terminator == b'\r' and output_buffer.startswith(b'\n'):
                                output_buffer = output_buffer[1:]  # Remove the \n as well
                            
                            # Convert to string and process
                            try:
                                line_str = line_bytes.decode('utf-8', errors='ignore').strip()
                            except UnicodeDecodeError:
                                line_str = line_bytes.decode('latin-1', errors='ignore').strip()
                            
                            if line_str:  # Only process non-empty lines
                                logger.debug(f"{job_id} OUTPUT: {repr(line_str)}")
                                all_output.append(line_str)
                                
                                # Try to parse as progress (HandBrake progress comes via stderr)
                                progress = self._parse_handbrake_progress(line_str)
                                if progress:
                                    job.progress = progress
                                    self._notify_progress(job_id, progress)
                                    
                                    # Save progress periodically
                                    if (progress.percentage > 0 and 
                                        progress.percentage % 5 == 0 and 
                                        progress.percentage != getattr(job.progress, 'last_saved_percentage', -1)):
                                        job.progress.last_saved_percentage = progress.percentage
                                        self._persist_job_status(job_id, job)
            
            # Process any remaining data in the buffer
            if output_buffer:
                try:
                    remaining_str = output_buffer.decode('utf-8', errors='ignore').strip()
                except UnicodeDecodeError:
                    remaining_str = output_buffer.decode('latin-1', errors='ignore').strip()
                
                if remaining_str:
                    logger.debug(f"{job_id} FINAL OUTPUT: {repr(remaining_str)}")
                    all_output.append(remaining_str)
            
            # Get any final output from process termination
            try:
                final_output, _ = process.communicate(timeout=5)
                if final_output:
                    final_str = final_output.decode('utf-8', errors='ignore').strip()
                    if final_str:
                        # Split final output into lines and add them
                        final_lines = final_str.replace('\r\n', '\n').replace('\r', '\n').split('\n')
                        for line in final_lines:
                            line = line.strip()
                            if line:
                                all_output.append(line)
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout waiting for final output from {job_id}")
                process.kill()
                process.communicate()
            
            # Clean up process reference
            with self._lock:
                if job_id in self.job_processes:
                    del self.job_processes[job_id]
            
            # Handle completion
            if process.returncode == 0:
                logger.info(f"HandBrake completed successfully for {job_id}")
                self._handle_job_completion(job_id, job, True, "", all_output)
            else:
                error_msg = f"HandBrake failed with exit code {process.returncode}"
                logger.error(f"HandBrake failed for {job_id}: {error_msg}")
                self._handle_job_completion(job_id, job, False, error_msg, all_output)
                
        except Exception as e:
            error_msg = f"Encoding job failed: {str(e)}"
            logger.error(f"Error in encoding job {job_id}: {e}")
            self._handle_job_completion(job_id, job, False, error_msg, [])
    
    def _build_handbrake_command(self, job: EncodingJob) -> List[str]:
        """Build HandBrake CLI command using template manager"""
        if not self.metadata_manager or not self.metadata_manager.directory:
            raise ValueError("No metadata manager or directory set")
        
        input_path = self.metadata_manager.directory / job.file_name
        
        # Validate input file exists
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Generate output filename using template manager
        try:
            # Load metadata to get movie details
            metadata = self.metadata_manager.load_metadata(job.file_name)
            
            # Find the title data
            title_data = None
            for title in metadata.get('titles', []):
                if title.get('title_number') == job.title_number:
                    title_data = title
                    break
            
            # Get release date for filename generation
            release_date = title_data.get('release_date', '') if title_data else ''
            
            # Generate output filename
            output_filename = self.template_manager.generate_output_filename(
                job.movie_name, release_date, job.preset_name
            )
            
        except Exception as e:
            logger.warning(f"Error generating output filename: {e}")
            output_filename = self._generate_output_filename(job.movie_name, job.preset_name)
        
        # Handle output directory path
        output_dir = self.settings.output_directory.strip()
        if output_dir:
            # If output directory is specified, treat it as relative to movies directory
            if not output_dir.startswith('/'):
                output_dir = '/' + output_dir
            
            # Convert relative path to absolute path within movies directory
            if self.metadata_manager and self.metadata_manager.directory:
                movies_root = Path(self.metadata_manager.directory)
                if output_dir.startswith('/'):
                    # Remove leading slash and join with movies directory
                    rel_path = output_dir[1:] if output_dir != '/' else ''
                    output_path = movies_root / rel_path / output_filename
                else:
                    output_path = movies_root / output_dir / output_filename
            else:
                # Fallback to treating as absolute path
                output_path = Path(output_dir) / output_filename
        else:
            # Use same directory as source file
            if self.metadata_manager and self.metadata_manager.directory:
                source_path = Path(self.metadata_manager.directory) / job.file_name
                output_path = source_path.parent / output_filename
            else:
                # Fallback - this shouldn't happen in normal operation
                output_path = Path(output_filename)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Store output path in job
        job.output_path = str(output_path)
        
        # Get enhanced metadata for track selection
        enhanced_metadata = self.metadata_manager.get_enhanced_metadata(job.file_name)
        
        # Extract selected audio and subtitle tracks
        audio_tracks, subtitle_tracks = self.template_manager.extract_metadata_tracks(
            enhanced_metadata, job.title_number
        )
        
        # Build command using template manager
        cmd = self.template_manager.build_handbrake_command(
            input_file=input_path,
            output_file=output_path,
            template_name=job.preset_name,
            title_number=job.title_number,
            audio_tracks=audio_tracks,
            subtitle_tracks=subtitle_tracks,
            testing_mode=self.settings.testing_mode,
            test_duration=self.settings.test_duration_seconds
        )
        
        logger.info(f"Built HandBrake command with template: {job.preset_name}")
        return cmd
   

    def _parse_handbrake_progress(self, line: str) -> Optional[EncodingProgress]:
        """Parse HandBrake progress from stderr output"""
        try:
            # Log the line for debugging
            if "Encoding:" in line or "Scanning" in line or "%" in line:
                logger.debug(f"HandBrake output: {line}")
            
            # HandBrake progress formats:
            # "Encoding: task 1 of 1, 45.67 % (123.45 fps, avg 98.76 fps, ETA 01h23m45s)"
            # "Encoding: task 1 of 1, 45.67 %"
            # "Encoding: task 1 of 2, 9.60 % (0.00 fps, avg 0.00 fps, ETA 00h00m00s)"
            
            # First try to match the full format with fps and ETA
            progress_match = re.search(r'Encoding:.*?(\d+\.?\d*)\s*%.*?(\d+\.?\d*)\s*fps.*?ETA\s*(\d+h)?(\d+m)?(\d+s)?', line)
            
            if progress_match:
                percentage = float(progress_match.group(1))
                fps = float(progress_match.group(2))
                
                # Parse ETA
                eta_hours = int(progress_match.group(3)[:-1]) if progress_match.group(3) else 0
                eta_minutes = int(progress_match.group(4)[:-1]) if progress_match.group(4) else 0
                eta_seconds = int(progress_match.group(5)[:-1]) if progress_match.group(5) else 0
                
                time_remaining = eta_hours * 3600 + eta_minutes * 60 + eta_seconds
                
                progress = EncodingProgress(
                    percentage=percentage,
                    fps=fps,
                    time_remaining=time_remaining,
                    phase=EncodingPhase.ENCODING,
                    last_updated=datetime.now().isoformat()
                )
                
                logger.debug(f"Parsed progress (full): {percentage}% at {fps} fps, ETA {time_remaining}s")
                return progress
            
            # If that fails, try to match just the percentage
            simple_progress_match = re.search(r'Encoding:.*?(\d+\.?\d*)\s*%', line)
            
            if simple_progress_match:
                percentage = float(simple_progress_match.group(1))
                
                progress = EncodingProgress(
                    percentage=percentage,
                    fps=0.0,
                    time_remaining=0,
                    phase=EncodingPhase.ENCODING,
                    last_updated=datetime.now().isoformat()
                )
                
                logger.debug(f"Parsed progress (simple): {percentage}%")
                return progress
            
            # Check for scanning phase
            if "Scanning title" in line or "scan:" in line:
                progress = EncodingProgress(
                    percentage=0.0,
                    phase=EncodingPhase.SCANNING,
                    last_updated=datetime.now().isoformat()
                )
                logger.debug("Detected scanning phase")
                return progress
            
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
    
    def _handle_job_completion(self, job_id: str, job: EncodingJob, success: bool, error_msg: str = "", output_lines: List[str] = None) -> None:
        """Handle job completion"""
        with self._lock:
            # Update job status
            if success:
                job.status = EncodingStatus.COMPLETED
                job.progress.percentage = 100.0
                job.progress.phase = EncodingPhase.COMPLETED
                
                # Calculate output file size if file exists
                if job.output_path and os.path.exists(job.output_path):
                    try:
                        file_size = os.path.getsize(job.output_path)
                        # Store file size in job progress for easy access
                        job.progress.output_size_mb = file_size / (1024 * 1024)  # Convert to MB
                        logger.info(f"Output file size: {file_size} bytes ({job.progress.output_size_mb:.2f} MB)")
                    except Exception as e:
                        logger.warning(f"Could not get output file size for {job.output_path}: {e}")
                
                logger.info(f"Encoding job completed successfully: {job_id}")
                
                # Send completion notification
                self._send_notification(
                    'completion',
                    f"Encoding completed successfully: {job.movie_name or job.file_name}",
                    job
                )
            else:
                job.status = EncodingStatus.FAILED
                job.error_message = error_msg
                
                # Capture last 100 lines of output for failure analysis
                if output_lines:
                    # Get last 100 lines, clean them up
                    last_lines = output_lines[-100:] if len(output_lines) > 100 else output_lines
                    # Clean up the lines - remove empty lines and debug prefixes
                    cleaned_lines = []
                    for line in last_lines:
                        line = line.strip()
                        if line and not line.startswith(f"{job_id}:"):
                            # Remove any remaining newlines and clean up
                            cleaned_line = line.replace('\n', '').replace('\r', '')
                            if cleaned_line:
                                cleaned_lines.append(cleaned_line)
                    
                    job.failure_logs = cleaned_lines[-100:]  # Ensure we don't exceed 100 lines
                    logger.info(f"Captured {len(job.failure_logs)} lines of failure logs for {job_id}")
                else:
                    job.failure_logs = []
                
                logger.error(f"Encoding job failed: {job_id} - {error_msg}")
                
                # Send failure notification
                self._send_notification(
                    'failure',
                    f"Encoding failed: {job.file_name} - {error_msg}",
                    job
                )
                
                # Clean up failed output file
                self._cleanup_output_file(job)
            
            job.completed_at = datetime.now().isoformat()
            
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            # Notify queue processor that a worker slot is now available
            with self._queue_condition:
                self._queue_condition.notify()
            
            # Clean up future reference
            if job_id in self.job_futures:
                del self.job_futures[job_id]
            
            # Update metadata and add to history in a single operation
            self._complete_job_metadata_update(job_id, job)
            
            # Check if queue is empty and send notification
            self._check_queue_empty_notification()
            
            # Invalidate cache since active jobs changed
            # FIXME: Do we really need to invalidate the cache or just update it?
            self._invalidate_jobs_cache()
            
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


    def _persist_job_status(self, job_id: str, job: EncodingJob) -> None:
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
            
            # Invalidate jobs cache since metadata was updated
            self._invalidate_jobs_cache()
            
        except Exception as e:
            logger.error(f"Error updating job in metadata: {e}")
    
    def _complete_job_metadata_update(self, job_id: str, job: EncodingJob) -> None:
        """
        Complete job metadata update - combines job update and history addition
        to reduce file writes and prevent race conditions
        """
        if not self.metadata_manager:
            return
        
        try:
            metadata = self.metadata_manager.load_metadata(job.file_name)
            
            # Update job in encoding jobs list
            jobs = ExtendedMetadata.get_encoding_jobs(metadata)
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
            
            metadata = ExtendedMetadata.set_encoding_jobs(metadata, jobs)
            
            # Add to history if job is completed or failed
            if job.status in [EncodingStatus.COMPLETED, EncodingStatus.FAILED]:
                # Calculate encoding time
                encoding_time = 0
                if job.started_at and job.completed_at:
                    try:
                        start_time = datetime.fromisoformat(job.started_at)
                        end_time = datetime.fromisoformat(job.completed_at)
                        encoding_time = int((end_time - start_time).total_seconds())
                    except ValueError:
                        pass
                
                # Get output file size
                output_size_mb = 0.0
                if job.output_path and os.path.exists(job.output_path):
                    output_size_mb = os.path.getsize(job.output_path) / (1024 * 1024)
                
                # Create history entry
                from models.encoding_models import EncodingHistory
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
                metadata = ExtendedMetadata.add_encoding_history(metadata, history_entry)
            
            # Single atomic save operation
            self.metadata_manager.save_metadata(job.file_name, metadata)
            
            # Invalidate jobs cache since metadata was updated
            self._invalidate_jobs_cache()
            
        except Exception as e:
            logger.error(f"Error completing job metadata update: {e}")
    
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
        # Use settings directory for settings file
        app_dir = Path(__file__).parent.parent
        settings_path = app_dir / "settings" / "settings.json"
        
        # Ensure settings directory exists
        settings_path.parent.mkdir(exist_ok=True)
        
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
        # Use settings directory for settings file
        app_dir = Path(__file__).parent.parent
        settings_path = app_dir / "settings" / "settings.json"
        
        # Ensure settings directory exists
        settings_path.parent.mkdir(exist_ok=True)
        
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


    def add_notification_callback(self, callback) -> None:
        """Add a callback for notifications"""
        self._notification_callbacks.append(callback)


    def _send_notification(self, notification_type: str, message: str, job: EncodingJob = None) -> None:
        """Send a notification if enabled in settings"""
        try:
            # Check if this notification type is enabled
            notifications = self.settings.notification_settings or {}
            
            if notification_type == 'completion' and not notifications.get('on_completion', True):
                return
            elif notification_type == 'failure' and not notifications.get('on_failure', True):
                return
            elif notification_type == 'queue_empty' and not notifications.get('on_queue_empty', True):
                return
            
            # Send notification to all registered callbacks
            notification_data = {
                'type': notification_type,
                'message': message,
                'timestamp': time.time(),
                'job': job.to_dict() if job else None
            }
            
            for callback in self._notification_callbacks:
                try:
                    callback(notification_data)
                except Exception as e:
                    logger.error(f"Error in notification callback: {e}")
                    
            logger.info(f"Notification sent: {notification_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def _check_queue_empty_notification(self) -> None:
        """Check if queue is empty and send notification if needed"""
        try:
            # Check if both queue and active jobs are empty
            if (self.encoding_queue.empty() and 
                len(self.active_jobs) == 0 and 
                self.running):
                
                self._send_notification(
                    'queue_empty',
                    "All encoding jobs have been completed. Queue is empty.",
                    None
                )
        except Exception as e:
            logger.error(f"Error checking queue empty notification: {e}")
    
    def get_template_manager(self) -> TemplateManager:
        """Get the template manager instance"""
        return self.template_manager
    
    def get_settings(self) -> EncodingSettings:
        """Get current encoding settings"""
        return self.settings
