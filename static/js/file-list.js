// File List Management and Formatting
(function() {
    'use strict';

    // Centralized file list item formatter
    function formatFileListItem(movie, encodingStatus = null) {
        // Determine CSS classes
        const classes = ['file-item'];
        
        if (movie.has_metadata) {
            classes.push('has-metadata');
        } else {
            classes.push('no-metadata');
        }
        
        if (encodingStatus && encodingStatus !== 'not_queued') {
            classes.push(encodingStatus);
        }
        
        // Build info text
        let infoText = '';
        if (movie.size_mb) {
            infoText = `${movie.size_mb} MB`;
        }
        
        if (encodingStatus && encodingStatus !== 'not_queued') {
            const statusMap = {
                'queued': 'Queued',
                'encoding': 'Encoding',
                'completed': 'Completed',
                'failed': 'Failed'
            };
            infoText += ` • ${statusMap[encodingStatus] || encodingStatus}`;
        }
        
        return {
            classes: classes.join(' '),
            fileName: movie.file_name,
            infoText: infoText,
            statusIndicatorClass: movie.has_metadata ? 'has-metadata' : 'no-metadata'
        };
    }

    // Populate a single file list item
    function populateFileListItem(listItem, movie, encodingStatus = null) {
        const format = formatFileListItem(movie, encodingStatus);
        
        // Set classes
        listItem.className = format.classes;
        listItem.onclick = () => selectFile(format.fileName);
        
        // Set content
        listItem.innerHTML = `
            <div class="file-name">
                <span class="status-indicator ${format.statusIndicatorClass}"></span>
                ${format.fileName}
            </div>
            <div class="file-info">
                ${format.infoText}
            </div>
        `;
        
        // Add progress display for encoding files
        if (encodingStatus === 'encoding') {
            const progressDiv = createProgressDisplay(movie.file_name);
            listItem.appendChild(progressDiv);
        }
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

    // Update file list with new data
    function updateFileList(movies) {
        if (typeof currentMovies !== 'undefined') {
            currentMovies = movies;
        }
        
        const fileList = document.getElementById('fileList');
        const currentSelection = document.querySelector('.file-item.active')?.dataset.filename;
        
        // Clear and rebuild list
        fileList.innerHTML = '';
        movies.forEach(movie => {
            const li = document.createElement('li');
            li.dataset.filename = movie.file_name;
            
            // Use centralized formatting
            populateFileListItem(li, movie);
            
            // Restore selection if needed
            if (movie.file_name === currentSelection) {
                li.classList.add('active');
            }
            
            fileList.appendChild(li);
        });
    }

    // Make functions globally available
    window.formatFileListItem = formatFileListItem;
    window.populateFileListItem = populateFileListItem;
    window.createProgressDisplay = createProgressDisplay;
    window.updateFileList = updateFileList;

})();
