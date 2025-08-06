// Enhanced Encoding UI Components
(function() {
    'use strict';
    
    // Global state
    let encodingJobs = {};
    let encodingStatus = {};
    let selectedFile = null;
    
    // Initialize encoding UI
    function initializeEncodingUI() {
        // Request initial encoding status
        if (window.socket) {
            window.socket.emit('request_encoding_status');
        }
        
        // Set up periodic status updates
        setInterval(requestEncodingStatus, 5000);
    }
    
    // Request encoding status from server
    function requestEncodingStatus() {
        if (window.socket && window.socket.connected) {
            window.socket.emit('request_encoding_status');
        }
    }
    
    // Handle encoding status updates
    function handleEncodingStatusUpdate(data) {
        encodingStatus = data;
        updateFileListWithEncodingStatus();
        updateQueueManagementButtons();
    }
    
    // Handle encoding progress updates
    function handleEncodingProgress(data) {
        const { job_id, progress } = data;
        
        // Update progress display for the specific job
        updateProgressDisplay(job_id, progress);
        
        // Update file list if needed
        const fileName = job_id.split('_')[0];
        updateFileEncodingStatus(fileName);
    }
    
    // Handle encoding status changes
    function handleEncodingStatusChange(data) {
        const { job_id, status } = data;
        const fileName = job_id.split('_')[0];
        
        // Update file status
        updateFileEncodingStatus(fileName, status);
        
        // Update queue buttons
        updateQueueManagementButtons();
        
        // Show notification if needed
        showEncodingNotification(job_id, status);
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
        
        // Set classes based on metadata and encoding status
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
        li.dataset.filename = movie.file_name;
        li.onclick = () => selectFile(movie.file_name);
        
        // Create file info content
        const fileNameDiv = document.createElement('div');
        fileNameDiv.className = 'file-name';
        
        const statusIndicator = document.createElement('span');
        statusIndicator.className = `status-indicator ${encodingStatus || (movie.has_metadata ? 'has-metadata' : 'no-metadata')}`;
        
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
        } else {
            infoText += infoText ? ' • No metadata' : 'No metadata';
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
            const progressDiv = createProgressDisplay(movie.file_name);
            li.appendChild(progressDiv);
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
        const fileName = jobId.split('_')[0];
        const progressDiv = document.getElementById(`progress-${fileName}`);
        
        if (!progressDiv) return;
        
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
        
        // Update FPS
        const rightMetrics = progressDiv.querySelector('.progress-metrics > div:last-child');
        if (rightMetrics) {
            const fpsValue = rightMetrics.querySelector('.progress-metric:first-child .metric-value');
            if (fpsValue) {
                fpsValue.textContent = progress.fps.toFixed(1);
            }
        }
        
        // Update ETA
        if (rightMetrics) {
            const etaValue = rightMetrics.querySelector('.progress-metric:last-child .metric-value');
            if (etaValue) {
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
            
            activeJobs.forEach(job => {
                const jobId = `${job.file_name}_${job.title_number}`;
                cancelEncodingJob(jobId);
            });
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
            if (data.success) {
                showAlert(`Queued encoding job for "${movieName}"`, 'success');
                requestEncodingStatus();
            } else {
                showAlert('Error queuing encoding job: ' + data.error, 'error');
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
        
        // Add appropriate button based on status
        if (status === 'not_queued') {
            const addButton = document.createElement('button');
            addButton.className = 'queue-button add-to-queue';
            addButton.textContent = 'Add to Queue';
            addButton.onclick = () => addToQueue(selectedFile);
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
        setSelectedFile: function(fileName) {
            selectedFile = fileName;
            updateQueueManagementButtons();
        }
    };
    
    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', initializeEncodingUI);
})();
