// Application Initialization and UI Utilities
(function() {
    'use strict';

    // Initialize the application with movie data
    function initializeApplication(movies) {
        console.log('Initializing application with', movies.length, 'movies');
        
        // Call the original initializeApp from app.js
        if (typeof initializeApp === 'function') {
            initializeApp(movies);
        }
        
        // After initialization, populate the file list with centralized formatting
        setTimeout(function() {
            console.log('Populating file list with centralized formatting for', movies.length, 'movies');
            
            const fileListItems = document.querySelectorAll('#fileList .file-item');
            console.log('Found', fileListItems.length, 'file list items');
            
            fileListItems.forEach((item, index) => {
                const movieIndex = parseInt(item.dataset.movieIndex);
                const movie = movies[movieIndex];
                if (movie) {
                    console.log('Populating item', index, 'with movie:', movie.file_name);
                    populateFileListItem(item, movie);
                } else {
                    console.warn('No movie data for item', index);
                }
            });
            
            // Store movies data globally
            window.moviesData = movies;
        }, 50); // Small delay to let original initialization complete
    }

    // Show notification
    function showNotification(message, type = 'info') {
        const notifications = document.getElementById('notifications');
        if (!notifications) {
            console.log(`[${type.toUpperCase()}] ${message}`);
            return;
        }
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        notifications.appendChild(notification);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            notification.remove();
        }, 4000);
    }

    // Refresh the metadata display for the currently viewed movie
    function refreshCurrentMovieMetadata(movieData) {
        try {
            // Update basic file info
            const fileNameElement = document.getElementById('currentFileName');
            const fileSizeElement = document.getElementById('currentFileSize');
            
            if (fileNameElement) {
                fileNameElement.textContent = movieData.file_name;
            }
            
            if (fileSizeElement) {
                fileSizeElement.textContent = movieData.size_mb ? `${movieData.size_mb} MB` : '';
            }
            
            // If there's a loadEnhancedMetadata function, call it to refresh the full metadata
            if (typeof loadEnhancedMetadata === 'function') {
                console.log('Reloading enhanced metadata for updated file');
                loadEnhancedMetadata(movieData.file_name);
            } else {
                console.log('Enhanced metadata function not available, basic info updated');
            }
            
            // Update the file list item using centralized formatting
            const fileItem = document.querySelector(`[data-filename="${CSS.escape(movieData.file_name)}"]`);
            if (fileItem) {
                const wasSelected = fileItem.classList.contains('active');
                
                // Re-populate the item with centralized formatting
                populateFileListItem(fileItem, movieData);
                
                // Restore selection if needed
                if (wasSelected) {
                    fileItem.classList.add('active');
                }
            }
            
        } catch (error) {
            console.error('Error refreshing current movie metadata:', error);
        }
    }

    // Setup encoding UI integration
    function setupEncodingIntegration() {
        // Override selectFile to integrate with encoding UI
        const originalSelectFile = window.selectFile;
        window.selectFile = function(filename) {
            if (originalSelectFile) {
                originalSelectFile(filename);
            }
            
            // Update encoding UI
            if (window.EncodingUI) {
                window.EncodingUI.setSelectedFile(filename);
            }
        };
        
        // Override updateFileList to use encoding-aware version
        const originalUpdateFileList = window.updateFileList;
        window.updateFileList = function(movies) {
            // Store movies data for encoding UI
            window.moviesData = movies;
            
            // Use encoding-aware file list update
            if (window.EncodingUI) {
                window.EncodingUI.updateFileListWithEncodingStatus();
            } else {
                // Fallback to original if encoding UI not loaded
                if (originalUpdateFileList) {
                    originalUpdateFileList(movies);
                }
            }
        };
        
        // Make addSelectedTitlesToQueue available globally
        window.addSelectedTitlesToQueue = function() {
            if (window.EncodingUI && window.EncodingUI.addSelectedTitlesToQueue) {
                window.EncodingUI.addSelectedTitlesToQueue();
            } else {
                console.error('EncodingUI not available');
            }
        };
    }

    // Initialize everything when DOM is ready
    function initialize() {
        console.log('Initializing application components...');
        
        // Setup encoding integration
        setupEncodingIntegration();
        
        // Initialize WebSocket connection
        if (typeof initializeWebSocket === 'function') {
            initializeWebSocket();
        }
        
        console.log('Application initialization complete');
    }

    // Make functions globally available
    window.initializeApplication = initializeApplication;
    window.showNotification = showNotification;
    window.refreshCurrentMovieMetadata = refreshCurrentMovieMetadata;
    window.setupEncodingIntegration = setupEncodingIntegration;

    // Auto-initialize when this script loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

})();
