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
        
        // Note: Individual title progress bars are now handled by encoding.js
        // via addProgressBarsForEncodingTitles() function
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

    // Update file item status using class-based approach
    function updateFileItemStatus(fileItem, encodingStatus) {
        // Remove existing encoding status classes
        const encodingClasses = ['queued', 'encoding', 'completed', 'failed'];
        fileItem.classList.remove(...encodingClasses);
        
        // Add new status class if not default
        if (encodingStatus && encodingStatus !== 'not_queued') {
            fileItem.classList.add(encodingStatus);
        }
        
        // Update file info text
        const fileInfo = fileItem.querySelector('.file-info');
        if (fileInfo) {
            let infoText = fileInfo.textContent;
            
            // Remove existing encoding status text
            infoText = infoText.replace(/ • (Queued|Encoding|Completed|Failed)/g, '');
            
            // Add new encoding status text
            if (encodingStatus && encodingStatus !== 'not_queued') {
                const statusMap = {
                    'queued': 'Queued',
                    'encoding': 'Encoding',
                    'completed': 'Completed',
                    'failed': 'Failed'
                };
                infoText += ` • ${statusMap[encodingStatus] || encodingStatus}`;
            }
            
            fileInfo.textContent = infoText;
        }
    }

    // Make functions globally available
    window.formatFileListItem = formatFileListItem;
    window.populateFileListItem = populateFileListItem;
    window.updateFileList = updateFileList;
    window.updateFileItemStatus = updateFileItemStatus;

})();
