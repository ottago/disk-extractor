// Enhanced Encoding UI Components
(function() {
    'use strict';
    
    // Global state
    let encodingJobs = {};
    let encodingStatus = {};
    let selectedFile = null;
    let jobToFileMapping = {}; // Maps job_id to filename
    let fileToJobsMapping = {}; // Maps filename to array of job_ids
    
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
        setInterval(requestEncodingStatus, 5000);
        console.log('Encoding UI initialized');
    }
    
    // Update job progress (called from WebSocket events)
    function updateJobProgress(jobId, progress) {
        console.log(`Updating job progress: ${jobId}`, progress);
        
        // Update global state
        if (encodingJobs[jobId]) {
            encodingJobs[jobId].progress = progress;
        }
        
        // Get the filename for this job
        const fileName = jobToFileMapping[jobId];
        if (fileName) {
            console.log(`Job ${jobId} belongs to file ${fileName}`);
            // Update file-specific UI elements
            updateFileEncodingProgress(fileName, progress);
        }
        
        // Update UI elements in encoding page
        const progressBar = document.querySelector(`[data-job-id="${jobId}"] .progress-bar`);
        if (progressBar) {
            progressBar.style.width = `${progress.percentage}%`;
            progressBar.textContent = `${Math.round(progress.percentage)}%`;
        }
        
        const statusText = document.querySelector(`[data-job-id="${jobId}"] .status-text`);
        if (statusText) {
            statusText.textContent = `${progress.phase} - ${Math.round(progress.percentage)}%`;
        }
        
        // Update FPS and time remaining if available
        const fpsText = document.querySelector(`[data-job-id="${jobId}"] .fps-text`);
        if (fpsText && progress.fps) {
            fpsText.textContent = `${progress.fps.toFixed(1)} fps`;
        }
        
        const etaText = document.querySelector(`[data-job-id="${jobId}"] .eta-text`);
        if (etaText && progress.time_remaining) {
            const minutes = Math.floor(progress.time_remaining / 60);
            const seconds = progress.time_remaining % 60;
            etaText.textContent = `ETA: ${minutes}m ${seconds}s`;
        }
    }
    
    // Update job status (called from WebSocket events)
    function updateJobStatus(jobId, status) {
        console.log(`Updating job status: ${jobId} -> ${status}`);
        
        // Update global state
        encodingStatus[jobId] = status;
        if (encodingJobs[jobId]) {
            encodingJobs[jobId].status = status;
        }
        
        // Get the filename for this job
        const fileName = jobToFileMapping[jobId];
        if (fileName) {
            console.log(`Job ${jobId} belongs to file ${fileName}`);
            // Update file-specific UI elements
            updateFileEncodingStatusByName(fileName, status);
        }
        
        // Update UI elements in encoding page
        const jobElement = document.querySelector(`[data-job-id="${jobId}"]`);
        if (jobElement) {
            // Remove old status classes
            jobElement.classList.remove('status-queued', 'status-encoding', 'status-completed', 'status-failed', 'status-cancelled');
            
            // Add new status class
            jobElement.classList.add(`status-${status}`);
            
            // Update status text
            const statusText = jobElement.querySelector('.status-text');
            if (statusText) {
                statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            }
        }
        
        // Refresh the encoding status display
        requestEncodingStatus();
    }
    
    // Update file encoding progress in the main file list
    function updateFileEncodingProgress(fileName, progress) {
        const fileItems = document.querySelectorAll('.file-item');
        fileItems.forEach(item => {
            if (item.dataset.filename === fileName) {
                // Update progress indicator for this file
                let progressIndicator = item.querySelector('.encoding-progress');
                if (!progressIndicator) {
                    progressIndicator = document.createElement('div');
                    progressIndicator.className = 'encoding-progress';
                    item.appendChild(progressIndicator);
                }
                progressIndicator.textContent = `${Math.round(progress.percentage)}%`;
                progressIndicator.style.display = 'block';
                
                // Add encoding class if not already present
                if (!item.classList.contains('encoding')) {
                    item.classList.add('encoding');
                }
            }
        });
    }
    
    // Update file encoding status in the main file list
    function updateFileEncodingStatusByName(fileName, status) {
        const fileItems = document.querySelectorAll('.file-item');
        fileItems.forEach(item => {
            if (item.dataset.filename === fileName) {
                // Remove any existing status classes
                item.classList.remove('encoding', 'encoding-complete', 'encoding-failed', 'queued');
                
                // Add appropriate status class
                switch (status) {
                    case 'queued':
                        item.classList.add('queued');
                        break;
                    case 'encoding':
                        item.classList.add('encoding');
                        break;
                    case 'completed':
                        item.classList.add('encoding-complete');
                        // Hide progress indicator
                        const progressIndicator = item.querySelector('.encoding-progress');
                        if (progressIndicator) {
                            progressIndicator.style.display = 'none';
                        }
                        break;
                    case 'failed':
                        item.classList.add('encoding-failed');
                        // Hide progress indicator
                        const failedProgressIndicator = item.querySelector('.encoding-progress');
                        if (failedProgressIndicator) {
                            failedProgressIndicator.style.display = 'none';
                        }
                        break;
                }
            }
        });
    }
    
    // Make functions and mappings globally available
    window.updateJobProgress = updateJobProgress;
    window.updateJobStatus = updateJobStatus;
    window.jobToFileMapping = jobToFileMapping;
    window.fileToJobsMapping = fileToJobsMapping;
    window.queueEncodingJob = queueEncodingJob;
    
    // Request encoding status from server
    function requestEncodingStatus() {
        if (window.socket && window.socket.connected) {
            window.socket.emit('request_encoding_status');
        }
    }
    
    // Handle encoding status updates
    function handleEncodingStatusUpdate(data) {
        console.log('Handling encoding status update:', data);
        encodingStatus = data;
        updateFileListWithEncodingStatus();
        updateQueueManagementButtons();
    }
    
    // Handle encoding progress updates
    function handleEncodingProgress(data) {
        console.log('🎯 EncodingUI.handleEncodingProgress called with:', data);
        const { job_id, progress } = data;
        
        // Extract filename from job ID
        const fileName = extractFileNameFromJobId(job_id);
        console.log(`📊 Progress update for job ${job_id} -> file ${fileName}: ${progress.percentage}%`);
        
        // Update the job-to-file mapping if not already present
        if (!jobToFileMapping[job_id]) {
            jobToFileMapping[job_id] = fileName;
            console.log(`✅ Added job-to-file mapping: ${job_id} -> ${fileName}`);
        }
        
        // Update progress display for the specific job
        updateProgressDisplay(job_id, progress);
        
        // Update file list status
        updateFileEncodingStatus(fileName, 'encoding');
    }
    
    // Handle encoding status changes
    function handleEncodingStatusChange(data) {
        const { job_id, status } = data;
        const fileName = extractFileNameFromJobId(job_id);
        
        console.log(`Status change for job ${job_id} -> file ${fileName}: ${status}`);
        
        // Update the job-to-file mapping if not already present
        if (!jobToFileMapping[job_id]) {
            jobToFileMapping[job_id] = fileName;
            console.log(`Added job-to-file mapping: ${job_id} -> ${fileName}`);
        }
        
        // Update file status
        updateFileEncodingStatus(fileName, status);
        
        // Update queue buttons
        updateQueueManagementButtons();
        
        // Show notification if needed
        showEncodingNotification(job_id, status);
    }
    
    // Extract filename from job ID (format: filename_titleNumber_uuid)
    function extractFileNameFromJobId(job_id) {
        // Split by underscore and remove the last two parts (title number and UUID)
        const parts = job_id.split('_');
        if (parts.length >= 3) {
            // Remove the last two parts and rejoin
            return parts.slice(0, -2).join('_');
        }
        return job_id; // Fallback
    }
    
    // Update file list with encoding status sections
    function updateFileListWithEncodingStatus() {
        const fileList = document.getElementById('fileList');
        if (!fileList) return;
        
        // Get current movies data
        const movies = window.moviesData || [];
        
        // Group movies by encoding status
        const groupedMovies = {
            encoding: [],
            queued: [],
            regular: []
        };
        
        movies.forEach(movie => {
            const status = getFileEncodingStatus(movie.file_name);
            
            if (status === 'encoding') {
                groupedMovies.encoding.push(movie);
            } else if (status === 'queued') {
                groupedMovies.queued.push(movie);
            } else {
                groupedMovies.regular.push(movie);
            }
        });
        
        // Clear and rebuild file list
        fileList.innerHTML = '';
        
        // Add encoding section
        if (groupedMovies.encoding.length > 0) {
            addFileSection(fileList, 'Currently Encoding', 'encoding', groupedMovies.encoding);
        }
        
        // Add queued section
        if (groupedMovies.queued.length > 0) {
            addFileSection(fileList, 'Queued for Encoding', 'queued', groupedMovies.queued);
        }
        
        // Add regular files section
        if (groupedMovies.regular.length > 0) {
            addFileSection(fileList, 'Movie Files', 'regular', groupedMovies.regular);
        }
    }
    
    // Add a file section to the list
    function addFileSection(container, title, sectionType, movies) {
        // Create section header
        const header = document.createElement('div');
        header.className = `file-section-header ${sectionType}`;
        header.textContent = `${title} (${movies.length})`;
        container.appendChild(header);
        
        // Create section container
        const section = document.createElement('div');
        section.className = 'file-section';
        
        // Add movies to section
        movies.forEach(movie => {
            const listItem = createFileListItem(movie);
            section.appendChild(listItem);
        });
        
        container.appendChild(section);
    }
    
    // Create enhanced file list item
    function createFileListItem(movie) {
        const li = document.createElement('li');
        const encodingStatus = getFileEncodingStatus(movie.file_name);
        
        li.dataset.filename = movie.file_name;
        
        // Use centralized formatting if available, otherwise fallback
        if (window.populateFileListItem) {
            window.populateFileListItem(li, movie, encodingStatus);
        } else {
            // Fallback formatting (should not be needed if main page loads first)
            let classes = ['file-item'];
            if (movie.has_metadata) {
                classes.push('has-metadata');
            } else {
                classes.push('no-metadata');
            }
            
            if (encodingStatus && encodingStatus !== 'not_queued') {
                classes.push(encodingStatus);
            }
            
            li.className = classes.join(' ');
            li.onclick = () => selectFile(movie.file_name);
            
            // Create file info content
            const fileNameDiv = document.createElement('div');
            fileNameDiv.className = 'file-name';
            
            const statusIndicator = document.createElement('span');
            statusIndicator.className = `status-indicator ${movie.has_metadata ? 'has-metadata' : 'no-metadata'}`;
            
            fileNameDiv.appendChild(statusIndicator);
            fileNameDiv.appendChild(document.createTextNode(movie.file_name));
            
            const fileInfoDiv = document.createElement('div');
            fileInfoDiv.className = 'file-info';
            
            let infoText = '';
            if (movie.size_mb) {
                infoText += `${movie.size_mb} MB`;
            }
            
            if (movie.has_metadata) {
                infoText += infoText ? ' • Has metadata' : 'Has metadata';
            }
            
            // Add encoding status info
            if (encodingStatus && encodingStatus !== 'not_queued') {
                infoText += ` • ${formatEncodingStatus(encodingStatus)}`;
            }
            
            fileInfoDiv.textContent = infoText;
            
            li.appendChild(fileNameDiv);
            li.appendChild(fileInfoDiv);
            
            // Add progress display for encoding files
            if (encodingStatus === 'encoding') {
                const progressDiv = window.createProgressDisplay ? 
                    window.createProgressDisplay(movie.file_name) : 
                    createProgressDisplay(movie.file_name);
                li.appendChild(progressDiv);
            }
        }
        
        return li;
    }
    
    // Create progress display for encoding files
    function createProgressDisplay(fileName) {
        const progressDiv = document.createElement('div');
        progressDiv.className = 'encoding-progress';
        progressDiv.id = `progress-${fileName}`;
        
        // Progress bar
        const progressBarContainer = document.createElement('div');
        progressBarContainer.className = 'progress-bar-container';
        
        const progressBar = document.createElement('div');
        progressBar.className = 'progress-bar encoding';
        progressBar.style.width = '0%';
        
        progressBarContainer.appendChild(progressBar);
        progressDiv.appendChild(progressBarContainer);
        
        // Progress metrics
        const metricsDiv = document.createElement('div');
        metricsDiv.className = 'progress-metrics';
        
        // Percentage and phase
        const leftMetrics = document.createElement('div');
        leftMetrics.style.display = 'flex';
        leftMetrics.style.alignItems = 'center';
        leftMetrics.style.gap = '0.5rem';
        
        const percentageSpan = document.createElement('span');
        percentageSpan.className = 'progress-metric';
        percentageSpan.innerHTML = '<span class="metric-value">0%</span>';
        
        const phaseSpan = document.createElement('span');
        phaseSpan.className = 'encoding-phase scanning';
        phaseSpan.textContent = 'Scanning';
        
        leftMetrics.appendChild(percentageSpan);
        leftMetrics.appendChild(phaseSpan);
        
        // FPS and time metrics
        const rightMetrics = document.createElement('div');
        rightMetrics.style.display = 'flex';
        rightMetrics.style.gap = '1rem';
        
        const fpsSpan = document.createElement('span');
        fpsSpan.className = 'progress-metric';
        fpsSpan.innerHTML = '<span class="metric-label">FPS:</span> <span class="metric-value">0</span>';
        
        const timeSpan = document.createElement('span');
        timeSpan.className = 'progress-metric';
        timeSpan.innerHTML = '<span class="metric-label">ETA:</span> <span class="metric-value">--:--</span>';
        
        rightMetrics.appendChild(fpsSpan);
        rightMetrics.appendChild(timeSpan);
        
        metricsDiv.appendChild(leftMetrics);
        metricsDiv.appendChild(rightMetrics);
        progressDiv.appendChild(metricsDiv);
        
        return progressDiv;
    }
    
    // Update progress display for a specific job
    function updateProgressDisplay(jobId, progress) {
        // Extract filename from job ID
        const fileName = extractFileNameFromJobId(jobId);
        const progressDiv = document.getElementById(`progress-${fileName}`);
        
        console.log(`🎯 updateProgressDisplay called for job ${jobId} -> file ${fileName}`);
        console.log(`🔍 Looking for progress div: progress-${fileName}`);
        console.log(`📍 Progress div found:`, progressDiv);
        
        if (!progressDiv) {
            console.log(`⚠️ Progress div not found for ${fileName}, creating one`);
            // Try to find the file item and add progress display
            const fileItem = document.querySelector(`[data-filename="${CSS.escape(fileName)}"]`);
            console.log(`🔍 File item found:`, fileItem);
            if (fileItem) {
                const newProgressDiv = createProgressDisplay(fileName);
                fileItem.appendChild(newProgressDiv);
                console.log(`✅ Created new progress display for ${fileName}`);
                // Update the newly created progress display
                updateProgressDisplayElements(newProgressDiv, progress);
            } else {
                console.warn(`❌ File item not found for ${fileName}`);
            }
            return;
        }
        
        console.log(`✅ Updating existing progress display for ${fileName}`);
        updateProgressDisplayElements(progressDiv, progress);
    }
    
    // Helper function to update progress display elements
    function updateProgressDisplayElements(progressDiv, progress) {
        // Update progress bar
        const progressBar = progressDiv.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress.percentage}%`;
        }
        
        // Update percentage
        const percentageSpan = progressDiv.querySelector('.progress-metric .metric-value');
        if (percentageSpan) {
            percentageSpan.textContent = `${progress.percentage.toFixed(1)}%`;
        }
        
        // Update phase
        const phaseSpan = progressDiv.querySelector('.encoding-phase');
        if (phaseSpan) {
            phaseSpan.className = `encoding-phase ${progress.phase}`;
            phaseSpan.textContent = formatEncodingPhase(progress.phase);
        }
        
        // Update FPS and ETA
        const rightMetrics = progressDiv.querySelector('.progress-metrics > div:last-child');
        if (rightMetrics) {
            const fpsValue = rightMetrics.querySelector('.progress-metric:first-child .metric-value');
            if (fpsValue && progress.fps) {
                fpsValue.textContent = progress.fps.toFixed(1);
            }
            
            const etaValue = rightMetrics.querySelector('.progress-metric:last-child .metric-value');
            if (etaValue && progress.time_remaining) {
                etaValue.textContent = formatTime(progress.time_remaining);
            }
        }
    }
    
    // Get encoding status for a file
    function getFileEncodingStatus(fileName) {
        if (!encodingStatus.jobs) return 'not_queued';
        
        // Check if file has any encoding jobs
        for (const statusType of ['encoding', 'queued', 'completed', 'failed']) {
            const jobs = encodingStatus.jobs[statusType] || [];
            for (const job of jobs) {
                if (job.file_name === fileName) {
                    return statusType;
                }
            }
        }
        
        return 'not_queued';
    }
    
    // Update file encoding status
    function updateFileEncodingStatus(fileName, status = null) {
        const fileItem = document.querySelector(`[data-filename="${fileName}"]`);
        if (!fileItem) return;
        
        const currentStatus = status || getFileEncodingStatus(fileName);
        
        // Update classes
        fileItem.classList.remove('queued', 'encoding', 'completed', 'failed');
        if (currentStatus && currentStatus !== 'not_queued') {
            fileItem.classList.add(currentStatus);
        }
        
        // Update status indicator
        const statusIndicator = fileItem.querySelector('.status-indicator');
        if (statusIndicator) {
            statusIndicator.className = `status-indicator ${currentStatus}`;
        }
        
        // Update file info text
        const fileInfo = fileItem.querySelector('.file-info');
        if (fileInfo) {
            let infoText = fileInfo.textContent;
            
            // Remove existing encoding status
            infoText = infoText.replace(/ • (Queued|Encoding|Completed|Failed)/g, '');
            
            // Add new encoding status
            if (currentStatus && currentStatus !== 'not_queued') {
                infoText += ` • ${formatEncodingStatus(currentStatus)}`;
            }
            
            fileInfo.textContent = infoText;
        }
    }
    
    // Queue management functions
    function addToQueue(fileName) {
        // Get selected titles from metadata
        fetch(`/api/enhanced_metadata/${fileName}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.metadata.titles) {
                    const selectedTitles = data.metadata.titles.filter(title => title.selected && title.movie_name.trim());
                    
                    if (selectedTitles.length === 0) {
                        showAlert('No titles selected for encoding. Please select titles and add movie names first.', 'warning');
                        return;
                    }
                    
                    // Queue each selected title
                    selectedTitles.forEach(title => {
                        queueEncodingJob(fileName, title.title_number, title.movie_name);
                    });
                } else {
                    showAlert('Error loading file metadata', 'error');
                }
            })
            .catch(error => {
                showAlert('Error queuing encoding job: ' + error.message, 'error');
            });
    }
    
    function removeFromQueue(fileName) {
        // Find and cancel queued jobs for this file
        if (encodingStatus.jobs && encodingStatus.jobs.queued) {
            const queuedJobs = encodingStatus.jobs.queued.filter(job => job.file_name === fileName);
            
            queuedJobs.forEach(job => {
                const jobId = `${job.file_name}_${job.title_number}`;
                cancelEncodingJob(jobId);
            });
        }
    }
    
    function cancelEncoding(fileName) {
        // Find and cancel active encoding jobs for this file
        if (encodingStatus.jobs && encodingStatus.jobs.encoding) {
            const activeJobs = encodingStatus.jobs.encoding.filter(job => job.file_name === fileName);
            console.log(`Found ${activeJobs.length} active encoding jobs for ${fileName}`);
            
            activeJobs.forEach(job => {
                if (job.job_id) {
                    console.log(`Cancelling encoding job: ${job.job_id}`);
                    cancelEncodingJob(job.job_id);
                } else {
                    console.error(`No job_id found for ${fileName} title ${job.title_number}`);
                    showAlert(`Could not find job ID for cancellation. Please try refreshing the page.`, 'error');
                }
            });
            
            if (activeJobs.length === 0) {
                console.log(`No active encoding jobs found for ${fileName}`);
                showAlert(`No active encoding jobs found for this file.`, 'warning');
            }
        } else {
            console.log(`No encoding jobs in status or no encoding jobs at all`);
            showAlert(`No encoding jobs found.`, 'warning');
        }
    }
    
    // API calls
    function queueEncodingJob(fileName, titleNumber, movieName) {
        fetch('/api/encoding/queue', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_name: fileName,
                title_number: titleNumber,
                movie_name: movieName
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.job_id) {
                // Store the job-to-file mapping
                jobToFileMapping[data.job_id] = fileName;
                
                // Store the file-to-jobs mapping
                if (!fileToJobsMapping[fileName]) {
                    fileToJobsMapping[fileName] = [];
                }
                fileToJobsMapping[fileName].push(data.job_id);
                
                console.log(`Job ${data.job_id} queued for file ${fileName}`);
                showAlert(`Queued encoding job for "${movieName}"`, 'success');
                requestEncodingStatus();
                
                // Update UI immediately to show job is queued
                updateFileEncodingStatus(fileName, 'queued');
            } else {
                showAlert('Error queuing encoding job: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showAlert('Error queuing encoding job: ' + error.message, 'error');
        });
    }
    
    function cancelEncodingJob(jobId) {
        fetch(`/api/encoding/cancel/${jobId}`, {
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
    
    // Update queue management buttons in the details pane
    function updateQueueManagementButtons() {
        if (!selectedFile) return;
        
        const queueActions = document.getElementById('queueActions');
        if (!queueActions) return;
        
        const status = getFileEncodingStatus(selectedFile);
        
        // Clear existing buttons
        queueActions.innerHTML = '';
        
        // Check if there's a scan error - if so, don't show queue buttons
        // The scan error check should look at the current enhancedMetadata or scan error state
        const scanErrorElement = document.getElementById('scanError');
        const hasScanError = scanErrorElement && scanErrorElement.style.display !== 'none';
        
        if (hasScanError) {
            // Don't show any queue management buttons when there's a scan error
            // The "Show logs" button is handled separately by the scan error logic
            return;
        }
        
        // Add appropriate button based on status
        if (status === 'not_queued') {
            const addButton = document.createElement('button');
            addButton.className = 'queue-button add-to-queue';
            addButton.textContent = 'Add to Queue';
            addButton.onclick = () => addToQueue(selectedFile);
            
            // Check if button should be enabled (has valid selected titles)
            const hasValidTitles = checkForValidSelectedTitles();
            addButton.disabled = !hasValidTitles;
            if (!hasValidTitles) {
                addButton.title = 'Select titles with movie names to enable';
            }
            
            queueActions.appendChild(addButton);
        } else if (status === 'queued') {
            const removeButton = document.createElement('button');
            removeButton.className = 'queue-button remove-from-queue';
            removeButton.textContent = 'Remove from Queue';
            removeButton.onclick = () => removeFromQueue(selectedFile);
            queueActions.appendChild(removeButton);
        } else if (status === 'encoding') {
            const cancelButton = document.createElement('button');
            cancelButton.className = 'queue-button cancel-encoding';
            cancelButton.textContent = 'Cancel Encoding';
            cancelButton.onclick = () => cancelEncoding(selectedFile);
            queueActions.appendChild(cancelButton);
        }
    }
    
    // Check if there are valid selected titles (selected + has movie name)
    function checkForValidSelectedTitles() {
        // Check the current DOM state for selected titles with movie names
        const titleSections = document.querySelectorAll('.title-section');
        
        for (const titleSection of titleSections) {
            const titleNumber = titleSection.dataset.titleNumber;
            const checkbox = document.getElementById(`title-${titleNumber}-selected`);
            const movieNameInput = document.getElementById(`title-${titleNumber}-name`);
            
            if (checkbox && checkbox.checked && movieNameInput && movieNameInput.value.trim()) {
                return true;
            }
        }
        
        return false;
    }
    
    // Utility functions
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
    
    function formatEncodingPhase(phase) {
        const phaseMap = {
            'scanning': 'Scanning',
            'encoding': 'Encoding',
            'muxing': 'Muxing',
            'completed': 'Completed'
        };
        return phaseMap[phase] || phase;
    }
    
    function formatTime(seconds) {
        if (!seconds || seconds <= 0) return '--:--';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    function showAlert(message, type) {
        // Use existing alert system or create a simple one
        console.log(`${type.toUpperCase()}: ${message}`);
        
        // You can integrate with existing notification system here
        if (window.showNotification) {
            window.showNotification(message, type);
        }
    }
    
    function showEncodingNotification(jobId, status) {
        const fileName = jobId.split('_')[0];
        const statusMessages = {
            'completed': `Encoding completed for ${fileName}`,
            'failed': `Encoding failed for ${fileName}`,
            'cancelled': `Encoding cancelled for ${fileName}`
        };
        
        if (statusMessages[status]) {
            showAlert(statusMessages[status], status === 'completed' ? 'success' : 'warning');
        }
    }
    
    // Public API
    window.EncodingUI = {
        initialize: initializeEncodingUI,
        handleEncodingStatusUpdate: handleEncodingStatusUpdate,
        handleEncodingProgress: handleEncodingProgress,
        handleEncodingStatusChange: handleEncodingStatusChange,
        updateFileListWithEncodingStatus: updateFileListWithEncodingStatus,
        updateQueueManagementButtons: updateQueueManagementButtons,
        checkForValidSelectedTitles: checkForValidSelectedTitles,
        setSelectedFile: function(fileName) {
            selectedFile = fileName;
            updateQueueManagementButtons();
        }
    };
    
    // Initialize when DOM is loaded or immediately if already loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeEncodingUI);
    } else {
        // DOM is already loaded
        initializeEncodingUI();
    }
    
    // Also initialize if WebSocket is already connected
    if (window.socket && window.socket.connected) {
        console.log('WebSocket already connected, initializing EncodingUI');
        initializeEncodingUI();
    }
})();
