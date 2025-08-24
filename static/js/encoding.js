// Cleaned up Encoding UI Components
(function() {
    'use strict';
    
    // Simplified global state - single source of truth from backend
    let jobsState = {
        encoding: [],    // Currently encoding jobs
        queued: [],      // Queued jobs
        completed: [],   // Completed jobs
        failed: []       // Failed jobs
    };
    
    let selectedFile = null;
    
    // Job key utilities - use filename_titleNumber as consistent identifier
    function createJobKey(fileName, titleNumber) {
        return `${fileName}_${titleNumber}`;
    }
    
    function parseJobKey(jobKey) {
        const lastUnderscore = jobKey.lastIndexOf('_');
        if (lastUnderscore === -1) return { fileName: jobKey, titleNumber: null };
        
        const fileName = jobKey.substring(0, lastUnderscore);
        const titleNumber = parseInt(jobKey.substring(lastUnderscore + 1));
        return { fileName, titleNumber };
    }
    
    // Find job by filename and title number
    function findJobByFileAndTitle(fileName, titleNumber) {
        const allJobs = [
            ...jobsState.encoding,
            ...jobsState.queued,
            ...jobsState.completed,
            ...jobsState.failed
        ];
        
        return allJobs.find(job => 
            job.file_name === fileName && job.title_number === titleNumber
        );
    }
    
    // Get job status for a specific file and title
    function getJobStatus(fileName, titleNumber) {
        const job = findJobByFileAndTitle(fileName, titleNumber);
        return job ? job.status : 'not_queued';
    }
    
    // Get file's overall encoding status (for file list display)
    function getFileEncodingStatus(fileName) {
        // Check if file has any jobs in different states (priority order)
        if (jobsState.encoding.some(job => job.file_name === fileName)) {
            return 'encoding';
        }
        if (jobsState.queued.some(job => job.file_name === fileName)) {
            return 'queued';
        }
        if (jobsState.completed.some(job => job.file_name === fileName)) {
            return 'completed';
        }
        if (jobsState.failed.some(job => job.file_name === fileName)) {
            return 'failed';
        }
        return 'not_queued';
    }
    
    // Initialize encoding UI
    function initializeEncodingUI() {
        console.log('Initializing Encoding UI...');
        
        // Request initial encoding status
        if (window.socket) {
            console.log('Requesting initial encoding status...');
            window.socket.emit('request_encoding_status');
        } else {
            console.warn('Socket not available for encoding status request');
        }
        
        // Set up periodic status updates
        setInterval(requestEncodingStatus, 60000);
        console.log('Encoding UI initialized');
    }
    
    // Handle encoding status updates from backend
    function handleEncodingStatusUpdate(data) {
        console.log('Handling encoding status update:', data);
        
        // Update our simplified state directly from backend
        if (data.jobs) {
            jobsState = {
                encoding: data.jobs.encoding || [],
                queued: data.jobs.queued || [],
                completed: data.jobs.completed || [],
                failed: data.jobs.failed || []
            };
        }
        
        // Update UI
        updateFileListWithEncodingStatus();
        updateAddToQueueButton();
        updateTitleEncodingStatusDisplay();
        
        // Update title status icons if the function is available
        if (window.updateAllTitleStatusIcons) {
            window.updateAllTitleStatusIcons();
        }
    }
    
    // Handle individual job progress updates
    function handleEncodingProgress(data) {
        console.log('🎯 Progress update:', data);
        const { job_id, progress } = data;
        
        // Find the job in our state and update its progress
        const allJobs = [...jobsState.encoding, ...jobsState.queued];
        const job = allJobs.find(j => j.job_id === job_id);
        
        if (job) {
            job.progress = progress;
            console.log(`📊 Updated progress for ${job.file_name} title ${job.title_number}: ${progress.percentage}%`);
            
            // Update progress display
            updateProgressDisplay(job.file_name, job.title_number, progress);
        }
    }
    
    // Handle individual job status changes
    function handleEncodingStatusChange(data) {
        const { job_id, status } = data;
        console.log(`Status change for job ${job_id}: ${status}`);
        
        // Find and update the job in our state
        let jobFound = false;
        for (const statusType of ['encoding', 'queued', 'completed', 'failed']) {
            const jobIndex = jobsState[statusType].findIndex(j => j.job_id === job_id);
            if (jobIndex !== -1) {
                const job = jobsState[statusType][jobIndex];
                
                // Remove from current status array
                jobsState[statusType].splice(jobIndex, 1);
                
                // Update job status and add to appropriate array
                job.status = status;
                if (jobsState[status]) {
                    jobsState[status].push(job);
                }
                
                console.log(`Moved job ${job_id} from ${statusType} to ${status}`);
                jobFound = true;
                break;
            }
        }
        
        if (!jobFound) {
            console.warn(`Job ${job_id} not found in current state for status update`);
        }
        
        // Refresh UI
        updateFileListWithEncodingStatus();
        updateAddToQueueButton();
        updateTitleEncodingStatusDisplay();
        
        // Update title status icons if the function is available
        if (window.updateAllTitleStatusIcons) {
            window.updateAllTitleStatusIcons();
        }
    }
    
    // Request encoding status from server
    function requestEncodingStatus() {
        if (window.socket && window.socket.connected) {
            window.socket.emit('request_encoding_status');
        }
    }
    
    // Update file list with encoding status
    // FIME: This updated the while file list every time.  It should skip updates if not needed and/or update in place.
    function updateFileListWithEncodingStatus() {
        const fileList = document.getElementById('fileList');
        if (!fileList) return;
        
        // Get current movies data
        const movies = window.moviesData || [];
        
        // Clear and rebuild file list
        fileList.innerHTML = '';
        
        // Group movies by encoding status
        const groupedMovies = {
            encoding: [],
            queued: [],
            other: []
        };
        
        movies.forEach(movie => {
            const status = getFileEncodingStatus(movie.file_name);
            
            if (status === 'encoding') {
                groupedMovies.encoding.push(movie);
            } else if (status === 'queued') {
                groupedMovies.queued.push(movie);
            } else {
                groupedMovies.other.push(movie);
            }
        });
        
        // Add movies to list in priority order
        [...groupedMovies.encoding, ...groupedMovies.queued, ...groupedMovies.other].forEach(movie => {
            const status = getFileEncodingStatus(movie.file_name);
            const li = createFileListItem(movie, status);
            fileList.appendChild(li);
        });
    }
    
    // Create file list item with encoding status
    function createFileListItem(movie, encodingStatus = null) {
        const li = document.createElement('li');
        li.dataset.filename = movie.file_name;
        
        // Use centralized formatting if available
        if (window.populateFileListItem) {
            window.populateFileListItem(li, movie, encodingStatus);
        } else {
            // Fallback formatting
            li.className = 'file-item';
            if (encodingStatus && encodingStatus !== 'not_queued') {
                li.classList.add(encodingStatus);
            }
            li.innerHTML = `
                <div class="file-info">
                    <strong>${movie.movie_name || movie.file_name}</strong>
                    <span class="file-details">${movie.file_name}</span>
                </div>
            `;
        }
        
        // Add progress display for encoding files
        if (encodingStatus === 'encoding') {
            const progressDiv = createProgressDisplay(movie.file_name);
            li.appendChild(progressDiv);
        }
        
        return li;
    }
    
    // Create progress display for a file
    function createProgressDisplay(fileName) {
        const progressDiv = document.createElement('div');
        progressDiv.className = 'encoding-progress';
        progressDiv.id = `progress-${fileName}`;
        
        // Find encoding jobs for this file
        const encodingJobs = jobsState.encoding.filter(job => job.file_name === fileName);
        
        encodingJobs.forEach(job => {
            const jobProgress = document.createElement('div');
            jobProgress.className = 'job-progress';
            jobProgress.innerHTML = `
                <div class="job-info">Title ${job.title_number}: ${job.movie_name}</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${job.progress?.percentage || 0}%">
                        ${Math.round(job.progress?.percentage || 0)}%
                    </div>
                </div>
            `;
            progressDiv.appendChild(jobProgress);
        });
        
        return progressDiv;
    }
    
    // Update progress display for specific job
    function updateProgressDisplay(fileName, titleNumber, progress) {
        const progressDiv = document.getElementById(`progress-${fileName}`);
        if (!progressDiv) return;
        
        // Find the specific job progress element
        const jobProgressElements = progressDiv.querySelectorAll('.job-progress');
        jobProgressElements.forEach(element => {
            const titleText = element.querySelector('.job-info').textContent;
            if (titleText.includes(`Title ${titleNumber}`)) {
                const progressBar = element.querySelector('.progress-bar');
                if (progressBar) {
                    progressBar.style.width = `${progress.percentage}%`;
                    progressBar.textContent = `${Math.round(progress.percentage)}%`;
                }
            }
        });
    }
    
    // Queue encoding job for specific title
    function queueEncodingJob(fileName, titleNumber, movieName, presetName = null) {
        console.log(`Queuing encoding job: ${fileName} title ${titleNumber}`);
        
        // Check if already queued or encoding
        const existingStatus = getJobStatus(fileName, titleNumber);
        if (existingStatus === 'queued' || existingStatus === 'encoding') {
            showAlert(`Title ${titleNumber} is already ${existingStatus}`, 'warning');
            return;
        }
        
        const requestData = {
            file_name: fileName,
            title_number: titleNumber,
            movie_name: movieName,
            preset_name: presetName
        };
        
        fetch('/api/encoding/queue', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Job queued successfully: ${data.job_id}`);
                showAlert(`Queued encoding job for "${movieName}" title ${titleNumber}`, 'success');
                requestEncodingStatus(); // Refresh status
            } else {
                showAlert('Error queuing encoding job: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showAlert('Error queuing encoding job: ' + error.message, 'error');
        });
    }
    
    // Cancel encoding job by job ID (reliable backend ID)
    function cancelEncodingJob(jobId) {
        console.log(`Cancelling job: ${jobId}`);
        
        // URL encode the job ID to handle special characters like dots
        const encodedJobId = encodeURIComponent(jobId);
        
        fetch(`/api/encoding/cancel/${encodedJobId}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Encoding job cancelled', 'success');
                requestEncodingStatus();
            } else {
                showAlert('Error cancelling job: ' + data.error, 'error');
            }
        })
        .catch(error => {
            showAlert('Error cancelling job: ' + error.message, 'error');
        });
    }
    
    // Cancel encoding for specific title (finds job by file/title, uses backend job ID)
    function cancelTitleEncoding(fileName, titleNumber) {
        console.log(`Cancelling encoding for: ${fileName} title ${titleNumber}`);
        
        // Find the job in our state
        const job = findJobByFileAndTitle(fileName, titleNumber);
        
        if (!job) {
            showAlert(`No job found for ${fileName} title ${titleNumber}`, 'warning');
            return;
        }
        
        if (!job.job_id) {
            showAlert('Cannot cancel: job ID not available', 'error');
            return;
        }
        
        // Use the backend's job ID for cancellation
        cancelEncodingJob(job.job_id);
    }
    
    // Check if title is currently encoding
    function isTitleCurrentlyEncoding(fileName, titleNumber) {
        return jobsState.encoding.some(job => 
            job.file_name === fileName && job.title_number === titleNumber
        );
    }
    
    // Check if title is currently queued
    function isTitleCurrentlyQueued(fileName, titleNumber) {
        return jobsState.queued.some(job => 
            job.file_name === fileName && job.title_number === titleNumber
        );
    }
    
    // Update add to queue button state
    function updateAddToQueueButton() {
        const addButton = document.getElementById('addToQueueButton');
        if (!addButton || !selectedFile) return;
        
        // Check if any titles are selected and valid for queuing
        const hasValidSelections = checkForValidSelectedTitles();
        addButton.disabled = !hasValidSelections;
    }
    
    // Check for valid selected titles (updated for icon system)
    function checkForValidSelectedTitles() {
        if (!selectedFile) return false;
        
        // Since we removed the checkbox system, check if there are any titles
        // that are not already queued/encoding and have required data
        const titleSections = document.querySelectorAll('.title-section');
        
        for (const section of titleSections) {
            const titleNumber = parseInt(section.dataset.titleNumber);
            if (isNaN(titleNumber)) continue;
            
            const status = getJobStatus(selectedFile, titleNumber);
            const movieName = document.getElementById(`title-${titleNumber}-name`)?.value || '';
            const audioCheckboxes = document.querySelectorAll(`input[id^="audio-${titleNumber}-"]:checked`);
            
            // Check if this title can be queued
            if ((status === 'not_queued' || status === 'failed') && 
                movieName.trim() && audioCheckboxes.length > 0) {
                return true;
            }
        }
        
        return false;
    }
    
    // Add selected titles to queue (updated for icon system)
    function addSelectedTitlesToQueue() {
        if (!selectedFile) return;
        
        const movieNameElement = document.querySelector(`[data-filename="${selectedFile}"] .movie-name`);
        const movieName = movieNameElement ? movieNameElement.textContent : selectedFile;
        
        let addedCount = 0;
        let errorCount = 0;
        
        // Process all title sections instead of checkboxes
        const titleSections = document.querySelectorAll('.title-section');
        
        titleSections.forEach(section => {
            const titleNumber = parseInt(section.dataset.titleNumber);
            if (isNaN(titleNumber)) return;
            
            const status = getJobStatus(selectedFile, titleNumber);
            const titleMovieName = document.getElementById(`title-${titleNumber}-name`)?.value || '';
            const audioCheckboxes = document.querySelectorAll(`input[id^="audio-${titleNumber}-"]:checked`);
            
            // Only queue titles that have required data and are not already queued
            if ((status === 'not_queued' || status === 'failed') && 
                titleMovieName.trim() && audioCheckboxes.length > 0) {
                queueEncodingJob(selectedFile, titleNumber, titleMovieName);
                addedCount++;
            } else if (status !== 'not_queued' && status !== 'failed') {
                console.log(`Skipping title ${titleNumber}: already ${status}`);
                errorCount++;
            }
        });
        
        if (addedCount > 0) {
            showAlert(`Added ${addedCount} title${addedCount > 1 ? 's' : ''} to encoding queue`, 'success');
        }
        if (errorCount > 0) {
            showAlert(`${errorCount} title${errorCount > 1 ? 's were' : ' was'} already queued or encoding`, 'warning');
        }
    }
    
    // Update title encoding status display
    function updateTitleEncodingStatusDisplay() {
        if (!selectedFile) return;
        
        // Get all title sections for the current file
        const titleSections = document.querySelectorAll('.title-section');
        
        titleSections.forEach(section => {
            const titleNumber = parseInt(section.dataset.titleNumber);
            if (isNaN(titleNumber)) return;
            
            // Check job status
            const isEncoding = isTitleCurrentlyEncoding(selectedFile, titleNumber);
            const isQueued = isTitleCurrentlyQueued(selectedFile, titleNumber);
            const job = findJobByFileAndTitle(selectedFile, titleNumber);
            const isCompleted = job && job.status === 'completed';
            
            // Update cancel button visibility
            const cancelIcon = document.getElementById(`cancel-encoding-${titleNumber}`);
            if (cancelIcon) {
                cancelIcon.style.display = (isEncoding || isQueued) ? 'inline' : 'none';
            }
            
            // Update completion icon
            const completionIcon = document.getElementById(`completion-${titleNumber}`);
            if (completionIcon) {
                completionIcon.style.display = isCompleted ? 'inline' : 'none';
            }
            
            // Update section classes
            section.classList.toggle('encoding', isEncoding);
            section.classList.toggle('queued', isQueued);
            section.classList.toggle('completed', isCompleted);
        });
    }
    
    // Format encoding status for display
    function formatEncodingStatus(status) {
        const statusMap = {
            'queued': 'Queued',
            'encoding': 'Encoding',
            'completed': 'Completed',
            'failed': 'Failed',
            'cancelled': 'Cancelled'
        };
        return statusMap[status] || status;
    }
    
    // Show alert message
    function showAlert(message, type = 'info') {
        // Use existing alert system if available
        if (window.showAlert) {
            window.showAlert(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
    
    // Queue a single title for encoding
    function queueSingleTitle(fileName, titleNumber) {
        console.log(`Queuing single title: ${fileName} - Title ${titleNumber}`);
        
        // Check if already queued or encoding
        const status = getJobStatus(fileName, titleNumber);
        if (status !== 'not_queued' && status !== 'failed') {
            showAlert(`Title ${titleNumber} is already ${status}`, 'warning');
            return;
        }
        
        // Get movie name for the title
        const movieNameInput = document.getElementById(`title-${titleNumber}-name`);
        const movieName = movieNameInput ? movieNameInput.value.trim() : '';
        
        if (!movieName) {
            showAlert('Please enter a movie name before queuing', 'error');
            return;
        }
        
        // Queue the job
        queueEncodingJob(fileName, titleNumber, movieName);
        showAlert(`Title ${titleNumber} queued for encoding`, 'success');
    }
    
    // Retry a failed title
    function retrySingleTitle(fileName, titleNumber) {
        console.log(`Retrying failed title: ${fileName} - Title ${titleNumber}`);
        
        // Remove from failed state and re-queue
        const failedJobIndex = jobsState.failed.findIndex(job => 
            job.file_name === fileName && job.title_number === titleNumber
        );
        
        if (failedJobIndex !== -1) {
            jobsState.failed.splice(failedJobIndex, 1);
        }
        
        // Queue the title again
        queueSingleTitle(fileName, titleNumber);
    }
    
    // Remove a single title from queue
    function removeFromQueueSingle(fileName, titleNumber) {
        console.log(`Removing from queue: ${fileName} - Title ${titleNumber}`);
        
        // Find and remove from queued jobs
        const queuedJobIndex = jobsState.queued.findIndex(job => 
            job.file_name === fileName && job.title_number === titleNumber
        );
        
        if (queuedJobIndex !== -1) {
            const job = jobsState.queued[queuedJobIndex];
            jobsState.queued.splice(queuedJobIndex, 1);
            
            // Emit cancel event to backend
            if (window.socket) {
                window.socket.emit('cancel_encoding', { job_id: job.job_id });
            }
            
            showAlert(`Title ${titleNumber} removed from queue`, 'success');
            
            // Update UI
            updateTitleEncodingStatusDisplay();
            if (window.updateAllTitleStatusIcons) {
                window.updateAllTitleStatusIcons();
            }
        } else {
            showAlert(`Title ${titleNumber} not found in queue`, 'warning');
        }
    }
    
    // Export public interface
    window.EncodingUI = {
        initialize: initializeEncodingUI,
        handleEncodingStatusUpdate: handleEncodingStatusUpdate,
        handleEncodingProgress: handleEncodingProgress,
        handleEncodingStatusChange: handleEncodingStatusChange,
        updateFileListWithEncodingStatus: updateFileListWithEncodingStatus,
        updateAddToQueueButton: updateAddToQueueButton,
        checkForValidSelectedTitles: checkForValidSelectedTitles,
        addSelectedTitlesToQueue: addSelectedTitlesToQueue,
        cancelTitleEncoding: cancelTitleEncoding,
        getFileEncodingStatus: getFileEncodingStatus,
        getJobStatus: getJobStatus,
        queueTitle: queueSingleTitle,
        retryTitle: retrySingleTitle,
        removeFromQueue: removeFromQueueSingle,
        setSelectedFile: function(fileName) {
            selectedFile = fileName;
            updateAddToQueueButton();
            updateTitleEncodingStatusDisplay();
        }
    };
    
})();
