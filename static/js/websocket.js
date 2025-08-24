// WebSocket Connection and Event Handling
(function() {
    'use strict';

    let socket = null;

    // Initialize WebSocket connection
    function initializeWebSocket() {
        // Initialize WebSocket connection for file watching
        socket = io();
        
        // Make socket available globally for encoding UI
        window.socket = socket;
        
        // Connection status handling
        socket.on('connect', function() {
            console.log('Connected to server');
            hideDisconnectionOverlay();
            
            // Initialize encoding UI after connection
            if (window.EncodingUI && typeof window.EncodingUI.initialize === 'function') {
                window.EncodingUI.initialize();
                console.log('Encoding UI initialized');
            } else {
                console.log('EncodingUI not available yet, will initialize when loaded');
            }
            
            // Request initial encoding status
            socket.emit('request_encoding_status');
        });
        
        socket.on('disconnect', function() {
            console.log('Disconnected from server');
            showDisconnectionOverlay();
        });
        
        // Encoding WebSocket event listeners
        socket.on('encoding_status_update', function(data) {
            console.log('🔄 Encoding status update received:', data);
            if (window.EncodingUI) {
                window.EncodingUI.handleEncodingStatusUpdate(data);
            }
        });
        
        socket.on('encoding_progress', function(data) {
            console.log('📊 Encoding progress update received:', data);
            console.log('📊 Job ID:', data.job_id, 'Progress:', data.progress.percentage + '%');
            if (window.EncodingUI) {
                window.EncodingUI.handleEncodingProgress(data);
            } else {
                // Fallback if EncodingUI not loaded yet
                console.log('⚠️ EncodingUI not available, using fallback progress handler');
                handleEncodingProgressFallback(data);
            }
        });
        
        socket.on('encoding_status_change', function(data) {
            console.log('🔄 Encoding status change received:', data);
            console.log('🔄 Job ID:', data.job_id, 'Status:', data.status);
            if (window.EncodingUI) {
                window.EncodingUI.handleEncodingStatusChange(data);
            } else {
                // Fallback if EncodingUI not loaded yet
                console.log('⚠️ EncodingUI not available, using fallback status handler');
                handleEncodingStatusChangeFallback(data);
            }
        });

        // File list updates
        socket.on('file_list_update', function(data) {
            console.log('File list updated:', data.change_type, data.filename);
            updateFileList(data.movies);
            
            if (data.change_type && data.filename) {
                const messages = {
                    'added': `New movie file: ${data.filename}`,
                    'removed': `Movie file removed: ${data.filename}`,
                    'modified': `Movie file updated: ${data.filename}`,
                    'metadata_updated': `Metadata updated: ${data.filename}`
                };
                showNotification(messages[data.change_type] || 'Files updated', 'info');
            }
        });
        
        // Specific metadata updates for currently viewed movie
        socket.on('metadata_updated', function(data) {
            console.log('Metadata updated for:', data.filename);
            
            // Check if this is the currently selected/viewed movie
            if (typeof selectedFile !== 'undefined' && selectedFile === data.filename) {
                console.log('Refreshing current movie metadata');
                
                // Update the current movie data
                if (typeof currentMovies !== 'undefined') {
                    const movieIndex = currentMovies.findIndex(m => m.file_name === data.filename);
                    if (movieIndex !== -1) {
                        currentMovies[movieIndex] = data.movie_data;
                    }
                }
                
                // Refresh the metadata display for the current movie
                refreshCurrentMovieMetadata(data.movie_data);
                
                showNotification(`Metadata refreshed for ${data.filename}`, 'success');
            }
        });
    }

    // Fallback handlers for when EncodingUI is not loaded
    function handleEncodingProgressFallback(data) {
        const { job_id, progress } = data;
        const fileName = extractFileNameFromJobIdFallback(job_id);
        console.log(`Fallback: Progress update for ${fileName}: ${progress.percentage}%`);
        
        // Update progress display if it exists
        const progressDiv = document.getElementById(`progress-${fileName}`);
        if (progressDiv) {
            updateProgressDisplayFallback(progressDiv, progress);
        }
    }
    
    function handleEncodingStatusChangeFallback(data) {
        const { job_id, status } = data;
        const fileName = extractFileNameFromJobIdFallback(job_id);
        console.log(`Fallback: Status change for ${fileName}: ${status}`);
        
        // Update file list item status
        const fileItem = document.querySelector(`[data-filename="${CSS.escape(fileName)}"]`);
        if (fileItem) {
            updateFileItemStatusFallback(fileItem, status);
        }
    }
    
    function extractFileNameFromJobIdFallback(job_id) {
        const parts = job_id.split('_');
        if (parts.length >= 3) {
            return parts.slice(0, -2).join('_');
        }
        return job_id;
    }
    
    function updateProgressDisplayFallback(progressDiv, progress) {
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
            phaseSpan.textContent = progress.phase.charAt(0).toUpperCase() + progress.phase.slice(1);
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
                const minutes = Math.floor(progress.time_remaining / 60);
                const seconds = progress.time_remaining % 60;
                etaValue.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
        }
    }
    
    function updateFileItemStatusFallback(fileItem, status) {
        // Use the new class-based approach
        if (window.updateFileItemStatus) {
            window.updateFileItemStatus(fileItem, status);
        } else {
            // Fallback implementation using class-based approach
            const encodingClasses = ['queued', 'encoding', 'completed', 'failed'];
            fileItem.classList.remove(...encodingClasses);
            
            // Add new status class
            if (status && status !== 'not_queued') {
                fileItem.classList.add(status);
            }
            
            // Update file info text
            const fileInfo = fileItem.querySelector('.file-info');
            if (fileInfo) {
                let infoText = fileInfo.textContent;
                
                // Remove existing encoding status
                infoText = infoText.replace(/ • (Queued|Encoding|Completed|Failed)/g, '');
                
                // Add new encoding status
                if (status && status !== 'not_queued') {
                    const statusMap = {
                        'queued': 'Queued',
                        'encoding': 'Encoding',
                        'completed': 'Completed',
                        'failed': 'Failed'
                    };
                    infoText += ` • ${statusMap[status] || status}`;
                }
                
                fileInfo.textContent = infoText;
            }
        }
    }

    // Show/hide disconnection overlay
    function showDisconnectionOverlay() {
        const overlay = document.getElementById('disconnectionOverlay');
        if (overlay) {
            overlay.classList.remove('hidden');
            // Disable all interactive elements
            document.body.style.pointerEvents = 'none';
            overlay.style.pointerEvents = 'auto'; // Keep overlay interactive
        }
    }
    
    function hideDisconnectionOverlay() {
        const overlay = document.getElementById('disconnectionOverlay');
        if (overlay) {
            overlay.classList.add('hidden');
            // Re-enable all interactive elements
            document.body.style.pointerEvents = 'auto';
        }
    }

    // Make functions globally available
    window.initializeWebSocket = initializeWebSocket;
    window.showDisconnectionOverlay = showDisconnectionOverlay;
    window.hideDisconnectionOverlay = hideDisconnectionOverlay;

    // Initialize with disconnection overlay shown
    showDisconnectionOverlay();

})();
