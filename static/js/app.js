// Global variables
let currentMovies = [];
let selectedFile = null;
let enhancedMetadata = null;

// Security: HTML escaping function to prevent XSS
function escapeHtml(text) {
    if (typeof text !== 'string') {
        return '';
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Security: Sanitize filename for display
function sanitizeFilename(filename) {
    if (typeof filename !== 'string') {
        return '';
    }
    // Remove any potentially dangerous characters and limit length
    return filename.replace(/[<>:"\/\\|?*\x00-\x1f]/g, '').substring(0, 255);
}

// Initialize the application
function initializeApp(movies) {
    currentMovies = movies;
    console.log('App initialized with', movies.length, 'movies');
    
    // Initialize resizer
    initializeResizer();
}

// Initialize resizer functionality
function initializeResizer() {
    const resizer = document.getElementById('resizer');
    const sidebar = document.querySelector('.sidebar');
    const container = document.querySelector('.container');
    
    if (!resizer || !sidebar || !container) {
        console.error('Resizer elements not found');
        return;
    }
    
    let isResizing = false;
    
    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        
        // Prevent text selection during resize
        e.preventDefault();
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        
        const containerRect = container.getBoundingClientRect();
        const newWidth = e.clientX - containerRect.left - 16; // Account for container padding
        
        // Enforce min/max width constraints
        const minWidth = 200;
        const maxWidth = Math.min(600, containerRect.width * 0.6); // Max 60% of container width
        
        if (newWidth >= minWidth && newWidth <= maxWidth) {
            sidebar.style.width = newWidth + 'px';
        }
    });
    
    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            
            // Save the width to localStorage for persistence
            const currentWidth = sidebar.style.width || '300px';
            localStorage.setItem('sidebarWidth', currentWidth);
        }
    });
    
    // Restore saved width on page load
    const savedWidth = localStorage.getItem('sidebarWidth');
    if (savedWidth) {
        sidebar.style.width = savedWidth;
    }
}

// Show loading indicator in titles container
function showTitlesLoading() {
    console.log('showTitlesLoading called');
    const titlesContainer = document.getElementById('titlesContainer');
    if (titlesContainer) {
        console.log('Setting loading indicator HTML');
        titlesContainer.innerHTML = `
            <div class="loading-indicator">
                <div class="loading-spinner"></div>
                <div class="loading-text">Loading movie titles...</div>
            </div>
        `;
        console.log('Loading indicator HTML set, current content:', titlesContainer.innerHTML);
    } else {
        console.error('titlesContainer element not found!');
    }
}

// Hide loading indicator (called when content is ready)
function hideTitlesLoading() {
    // This is handled by displayEnhancedMetadata() which clears the container
    // and populates it with actual content
}

// File selection
function selectFile(filename) {
    console.log('selectFile called for:', filename);
    
    // Sanitize filename for security
    const safeFilename = sanitizeFilename(filename);
    if (!safeFilename) {
        console.error('Invalid filename provided:', filename);
        return;
    }
    
    selectedFile = safeFilename;
    
    // Update UI
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const fileItem = document.querySelector(`[data-filename="${CSS.escape(safeFilename)}"]`);
    if (fileItem) {
        fileItem.classList.add('active');
    }
    
    // Find movie data
    const movie = currentMovies.find(m => m.file_name === safeFilename);
    if (!movie) {
        console.error('Movie not found:', safeFilename);
        return;
    }
    
    // Show basic file info (safely escaped)
    document.getElementById('currentFileName').textContent = movie.file_name;
    document.getElementById('currentFileSize').textContent = movie.size_mb ? `${movie.size_mb} MB` : '';
    
    // Show form
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('metadataForm').style.display = 'block';
    
    // IMPORTANT: Clear previous file's data and show enhanced metadata section
    enhancedMetadata = null;
    document.getElementById('enhancedMetadata').style.display = 'block'; // Show section so loading is visible
    document.getElementById('rawOutputButton').style.display = 'none';
    
    // Show loading indicator while fetching data
    console.log('Showing loading indicator for:', safeFilename);
    showTitlesLoading();
    
    // Update Add to Queue button (will be disabled initially, but visible if metadata exists)
    setTimeout(() => {
        if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
            window.EncodingUI.updateAddToQueueButton();
        }
    }, 50);
    
    // Try to load cached enhanced metadata for THIS specific file
    loadEnhancedMetadata(safeFilename);
}

// Load enhanced metadata
function loadEnhancedMetadata(filename) {
    console.log('loadEnhancedMetadata called for:', filename);
    
    // Make sure we're loading data for the currently selected file
    if (filename !== selectedFile) {
        console.log('File selection changed, aborting load for', filename);
        return;
    }
    
    console.log('Fetching enhanced metadata for:', filename);
    
    // Add a minimum loading time to make the indicator visible
    const startTime = Date.now();
    const minLoadingTime = 500; // 500ms minimum
    
    // Try to get enhanced metadata (this will use cached data if available)
    fetch(`/api/enhanced_metadata/${encodeURIComponent(filename)}`)
        .then(response => {
            console.log('Response received for', filename, 'status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Data received for', filename, ':', data);
            
            // Double-check we're still on the same file (user might have switched)
            if (filename !== selectedFile) {
                console.log('File selection changed during load, ignoring data for', filename);
                return;
            }
            
            // Calculate remaining time to show loading
            const elapsedTime = Date.now() - startTime;
            const remainingTime = Math.max(0, minLoadingTime - elapsedTime);
            
            // Wait for minimum loading time before showing results
            setTimeout(() => {
                if (filename !== selectedFile) {
                    console.log('File selection changed during delay, ignoring data for', filename);
                    return;
                }
                
                if (data.success && data.metadata) {
                    // Check if there's a scan error
                    if (data.metadata.scan_error) {
                        // Show scan error using the same UI as manual scans
                        console.log('Scan error detected for', filename, ':', data.metadata.scan_error);
                        showScanError(data.metadata.scan_error);
                        // Show raw output button if available
                        document.getElementById('rawOutputButton').style.display = 'inline-block';
                    } else if (data.metadata.titles && data.metadata.titles.length > 0) {
                        // We have valid HandBrake data - display it
                        console.log('Setting enhancedMetadata and calling displayEnhancedMetadata for', filename);
                        enhancedMetadata = data.metadata;
                        displayEnhancedMetadata();
                        document.getElementById('rawOutputButton').style.display = 'inline-block';
                        console.log('Loaded cached metadata for', filename, 'with', data.metadata.titles.length, 'titles');
                    } else {
                        // No titles found - clear loading and hide enhanced metadata
                        enhancedMetadata = null;
                        document.getElementById('enhancedMetadata').style.display = 'none';
                        document.getElementById('rawOutputButton').style.display = 'none';
                        document.getElementById('titlesContainer').innerHTML = '';
                        console.log('No titles found in metadata for', filename);
                    }
                } else {
                    // No cached data - clear loading and hide enhanced metadata
                    enhancedMetadata = null;
                    document.getElementById('enhancedMetadata').style.display = 'none';
                    document.getElementById('rawOutputButton').style.display = 'none';
                    document.getElementById('titlesContainer').innerHTML = '';
                    console.log('No cached metadata available for', filename);
                }
            }, remainingTime);
        })
        .catch(error => {
            // Only handle error if we're still on the same file
            if (filename === selectedFile) {
                console.error('Error loading metadata for', filename, ':', error);
                enhancedMetadata = null;
                document.getElementById('enhancedMetadata').style.display = 'none';
                document.getElementById('rawOutputButton').style.display = 'none';
                // Clear loading indicator and show error state
                document.getElementById('titlesContainer').innerHTML = `
                    <div class="loading-indicator">
                        <div style="color: #d32f2f; font-weight: 500;">⚠️ Error loading metadata</div>
                        <div style="font-size: 0.875rem; margin-top: 0.5rem;">Please try scanning the file</div>
                    </div>
                `;
            }
        });
}

// Scan file with HandBrake
function scanFile() {
    if (!selectedFile) return;
    
    const scanButton = document.getElementById('scanButton');
    const originalText = scanButton.innerHTML;
    
    // Show loading state
    scanButton.innerHTML = '⏳ Scanning...';
    scanButton.disabled = true;
    
    // Hide any existing enhanced metadata and show loading in titles container
    document.getElementById('enhancedMetadata').style.display = 'none';
    showTitlesLoading();
    
    fetch(`/api/scan_file/${encodeURIComponent(selectedFile)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Reload enhanced metadata
                loadEnhancedMetadata(selectedFile);
            } else {
                showScanError(data.error || 'Unknown error occurred');
            }
        })
        .catch(error => {
            showScanError('Network error: ' + error.message);
        })
        .finally(() => {
            // Restore button state
            scanButton.innerHTML = originalText;
            scanButton.disabled = false;
        });
}

// Show scan error
function showScanError(error) {
    // Convert line breaks to HTML <br> tags while escaping HTML characters
    const errorElement = document.getElementById('scanErrorMessage');
    
    // First escape HTML characters to prevent XSS
    const escapedError = error
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    
    // Then convert line breaks to <br> tags
    const formattedError = escapedError.replace(/\n/g, '<br>');
    
    // Use innerHTML since we've safely escaped everything except our <br> tags
    errorElement.innerHTML = formattedError;
    
    document.getElementById('scanError').style.display = 'block';
    document.getElementById('enhancedMetadata').style.display = 'block';
    document.getElementById('titlesContainer').innerHTML = '';
    // Show raw output button since errors should have raw output available
    document.getElementById('rawOutputButton').style.display = 'inline-block';
    
    // Update Add to Queue button to hide it when there's a scan error
    if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
        window.EncodingUI.updateAddToQueueButton();
    }
}

// Display enhanced metadata
function displayEnhancedMetadata() {
    console.log('displayEnhancedMetadata called, enhancedMetadata:', enhancedMetadata);
    
    if (!enhancedMetadata) {
        console.log('No enhancedMetadata available');
        return;
    }
    
    // Hide error if showing
    document.getElementById('scanError').style.display = 'none';
    
    // Update Add to Queue button since scan error is now cleared
    if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
        window.EncodingUI.updateAddToQueueButton();
    }
    
    // Show enhanced metadata section
    document.getElementById('enhancedMetadata').style.display = 'block';
    console.log('Enhanced metadata section shown');
    
    // Display titles
    const titlesContainer = document.getElementById('titlesContainer');
    if (!titlesContainer) {
        console.error('titlesContainer element not found!');
        return;
    }
    
    titlesContainer.innerHTML = '';
    console.log('Cleared titlesContainer');
    
    if (enhancedMetadata.scan_error) {
        console.log('Showing scan error:', enhancedMetadata.scan_error);
        showScanError(enhancedMetadata.scan_error);
        return;
    }
    
    console.log('Creating title elements for', enhancedMetadata.titles.length, 'titles');
    enhancedMetadata.titles.forEach((title, index) => {
        console.log('Creating title element for title', index + 1, ':', title);
        const titleElement = createTitleElement(title);
        titlesContainer.appendChild(titleElement);
    });
    
    console.log('All title elements created and appended');
    
    // Update Add to Queue button now that titles are loaded
    setTimeout(() => {
        if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
            window.EncodingUI.updateAddToQueueButton();
        }
    }, 50);
    
    // Check encoding status for all titles after they're created
    setTimeout(() => {
        checkEncodingStatusForAllTitles();
    }, 100);
    
    // Update title status icons after titles are created
    setTimeout(() => {
        updateAllTitleStatusIcons();
    }, 150);
}

// Create title element
function createTitleElement(title) {
    const titleDiv = document.createElement('div');
    titleDiv.className = 'title-section';
    titleDiv.dataset.titleNumber = title.title_number;
    titleDiv.dataset.duration = title.duration || '';
    
    
    // Helper function to get year from release date
    function getYear(dateString) {
        if (!dateString) return '';
        const year = dateString.split('-')[0];
        return year && year.length === 4 ? year : '';
    }
    
    // Helper function to parse duration and determine if title is too short
    function parseDuration(durationString) {
        if (!durationString) {
            console.log('parseDuration: no duration string provided');
            return 0;
        }
        
        // Parse duration like "1:23:45" or "0:05:30"
        const parts = durationString.split(':');
        console.log('parseDuration: parsing', durationString, 'parts:', parts);
        
        if (parts.length === 2) {
            // Handle MM:SS format
            const minutes = parseInt(parts[0]) || 0;
            const seconds = parseInt(parts[1]) || 0;
            const totalSeconds = minutes * 60 + seconds;
            console.log('parseDuration: MM:SS format -', minutes, 'min', seconds, 'sec =', totalSeconds, 'total seconds');
            return totalSeconds;
        } else if (parts.length === 3) {
            // Handle HH:MM:SS format
            const hours = parseInt(parts[0]) || 0;
            const minutes = parseInt(parts[1]) || 0;
            const seconds = parseInt(parts[2]) || 0;
            const totalSeconds = hours * 3600 + minutes * 60 + seconds;
            console.log('parseDuration: HH:MM:SS format -', hours, 'hr', minutes, 'min', seconds, 'sec =', totalSeconds, 'total seconds');
            return totalSeconds;
        }
        
        console.log('parseDuration: unrecognized format, returning 0');
        return 0;
    }
    
    // Determine if title should be collapsed by default
    // Collapse if: has movie name (sufficient content) OR (is short AND not selected)
    const durationInSeconds = parseDuration(title.duration);
    const isShortTitle = durationInSeconds > 0 && durationInSeconds < 1800; // 30 minutes = 1800 seconds
    const hasMovieName = title.movie_name && title.movie_name.trim();
    const shouldCollapseByDefault = hasMovieName || (isShortTitle && !title.selected);
    
    console.log(`Title ${title.title_number}: duration="${title.duration}", seconds=${durationInSeconds}, isShort=${isShortTitle}, hasMovieName=${hasMovieName}, selected=${title.selected}, shouldCollapse=${shouldCollapseByDefault}`);
    
    // Helper function to create title summary
    function createTitleSummary() {
        const movieName = escapeHtml(title.movie_name || '');
        const year = getYear(title.release_date);
        const audioCount = title.selected_audio_tracks.length;
        const subtitleCount = title.selected_subtitle_tracks.length;
        const duration = escapeHtml(title.duration || '');
        
        let summary = `Title ${title.title_number}`;
        if (movieName) {
            summary += `   ${movieName}`;
            if (year) {
                summary += ` (${escapeHtml(year)})`;
            }
        }
        
        return `
            <span>${escapeHtml(summary)}</span>
            ${audioCount > 0 ? `<span class="track-count">🔊 ${audioCount}</span>` : ''}
            ${subtitleCount > 0 ? `<span class="track-count">💬 ${subtitleCount}</span>` : ''}
            ${duration ? `<span>${duration}</span>` : ''}
        `;
    }
    
    // Safely escape values for HTML attributes and content
    const safeMovieName = escapeHtml(title.movie_name || '');
    const safeSynopsis = escapeHtml(title.synopsis || '');
    const safeYear = escapeHtml(getYear(title.release_date));
    const safeDuration = escapeHtml(title.duration || '');
    const titleSuggested = title.suggestions.title.suggested ? 'suggested' : 'not-suggested';
    
    titleDiv.innerHTML = `
        <div class="title-header ${shouldCollapseByDefault ? 'collapsed' : ''} ${titleSuggested}" onclick="toggleTitle(${title.title_number})">
            <div class="title-status-icon" id="title-status-${title.title_number}" 
                 onclick="event.stopPropagation(); handleTitleStatusClick(${title.title_number});"
                 onmouseover="handleTitleStatusHover(${title.title_number}, true)"
                 onmouseout="handleTitleStatusHover(${title.title_number}, false)"
                 title="Click to queue for encoding">
                <span class="status-icon">➕</span>
            </div>
            
            <div class="title-basic-info">
                <span class="title-number">Title ${title.title_number}</span>
                <span class="completion-icon" id="completion-icon-${title.title_number}" style="display: none;">✅</span>
                <span class="cancel-encoding-icon" id="cancel-encoding-${title.title_number}" style="display: none;" onclick="event.stopPropagation(); cancelTitleEncoding(${title.title_number});" title="Cancel encoding">❌</span>
            </div>
            
            <div class="movie-name-box" style="display: ${shouldCollapseByDefault && title.movie_name ? 'block' : 'none'};">
                ${safeMovieName}
            </div>
            
            <div class="title-spacer"></div>
            
            <div class="title-summary-info">
                ${shouldCollapseByDefault && title.selected_audio_tracks.length > 0 ? `<span class="track-count">🔊 ${title.selected_audio_tracks.length}</span>` : ''}
                ${shouldCollapseByDefault && title.selected_subtitle_tracks.length > 0 ? `<span class="track-count">💬 ${title.selected_subtitle_tracks.length}</span>` : ''}
                ${safeDuration ? `<span class="duration-display">${safeDuration}</span>` : ''}
            </div>
            
            <div class="expand-icon ${shouldCollapseByDefault ? 'collapsed' : ''}" id="title-${title.title_number}-icon">
                ${shouldCollapseByDefault ? '▶' : '▼'}
            </div>
        </div>
        
        <div class="title-content ${shouldCollapseByDefault ? 'collapsed' : ''}" id="title-${title.title_number}-content" style="display: ${shouldCollapseByDefault ? 'none' : 'block'};">
            <div class="form-group">
                <label for="title-${title.title_number}-name">Name:</label>
                <input type="text" 
                       id="title-${title.title_number}-name" 
                       value="${safeMovieName}"
                       oninput="updateQueueButtonsIfNeeded();"
                       onchange="saveMetadata(); updateTitleSummary(${title.title_number});"
                       onblur="saveMetadata();">
            </div>
            
            <div class="form-group">
                <label for="title-${title.title_number}-date">Release Year:</label>
                <input type="text" 
                       id="title-${title.title_number}-date" 
                       value="${safeYear}"
                       placeholder="YYYY"
                       maxlength="4"
                       onchange="saveMetadata(); updateTitleSummary(${title.title_number});">
            </div>
            
            <div class="form-group">
                <label for="title-${title.title_number}-synopsis">Synopsis:</label>
                <textarea id="title-${title.title_number}-synopsis" 
                          rows="3"
                          onchange="saveMetadata()">${safeSynopsis}</textarea>
            </div>
            
            <div class="tracks-container">
                <div class="tracks-section">
                    <h4>Audio Tracks</h4>
                    <div class="track-list">
                        ${title.audio_tracks.map((track, index) => {
                            const suggestion = title.suggestions.audio[index];
                            const suggestedClass = suggestion && suggestion.suggested ? 'suggested' : '';
                            const isChecked = title.selected_audio_tracks.includes(track.TrackNumber) ? 'checked' : '';
                            const safeLanguageName = escapeHtml(suggestion ? suggestion.language_name : 'Unknown');
                            const safeDescription = escapeHtml(track.Description || '');
                            return `
                                <div class="track-item ${suggestedClass}" onclick="toggleTrack('audio-${title.title_number}-${track.TrackNumber}')">
                                    <input type="checkbox" 
                                           id="audio-${title.title_number}-${track.TrackNumber}"
                                           ${isChecked}
                                           onclick="event.stopPropagation();"
                                           onchange="saveMetadata(); updateTitleSummary(${title.title_number});">
                                    <div class="track-info">
                                        <div class="track-language">${safeLanguageName}</div>
                                        <div class="track-details">${safeDescription}</div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                
                <div class="tracks-section">
                    <h4>Subtitle Tracks</h4>
                    <div class="track-list">
                        ${title.subtitle_tracks.map((track, index) => {
                            const suggestion = title.suggestions.subtitles[index];
                            const suggestedClass = suggestion && suggestion.suggested ? 'suggested' : '';
                            const isChecked = title.selected_subtitle_tracks.includes(track.TrackNumber) ? 'checked' : '';
                            const safeLanguageName = escapeHtml(suggestion ? suggestion.language_name : 'Unknown');
                            const safeName = escapeHtml(track.Name || '');
                            return `
                                <div class="track-item ${suggestedClass}" onclick="toggleTrack('subtitle-${title.title_number}-${track.TrackNumber}')">
                                    <input type="checkbox" 
                                           id="subtitle-${title.title_number}-${track.TrackNumber}"
                                           ${isChecked}
                                           onclick="event.stopPropagation();"
                                           onchange="saveMetadata(); updateTitleSummary(${title.title_number});">
                                    <div class="track-info">
                                        <div class="track-language">${safeLanguageName}</div>
                                        <div class="track-details">${safeName}</div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return titleDiv;
}

// Toggle title expand/collapse
function toggleTitle(titleNumber) {
    const content = document.getElementById(`title-${titleNumber}-content`);
    const icon = document.getElementById(`title-${titleNumber}-icon`);
    const titleSection = document.querySelector(`[data-title-number="${titleNumber}"]`);
    
    if (!content || !icon || !titleSection) {
        console.error('Could not find title elements for', titleNumber);
        return;
    }
    
    const header = titleSection.querySelector('.title-header');
    const movieNameBox = titleSection.querySelector('.movie-name-box');
    const summaryInfo = titleSection.querySelector('.title-summary-info');
    const basicInfo = titleSection.querySelector('.title-basic-info');
    const contentSuggestion = basicInfo.querySelector('.content-suggestion');
    
    if (content.style.display === 'none' || content.classList.contains('collapsed')) {
        // Expand
        content.style.display = 'block';
        content.classList.remove('collapsed');
        icon.textContent = '▼';
        icon.classList.remove('collapsed');
        if (header) header.classList.remove('collapsed');
        
        // Hide collapsed elements, show expanded elements
        if (movieNameBox) movieNameBox.style.display = 'none';
        if (contentSuggestion) contentSuggestion.style.display = 'inline-block';
        
        // Update summary info to show only duration (no track counts in expanded state)
        const duration = titleSection.dataset.duration || '';
        if (summaryInfo) {
            summaryInfo.innerHTML = duration ? `<span class="duration-display">${duration}</span>` : '';
        }
    } else {
        // Collapse
        content.style.display = 'none';
        content.classList.add('collapsed');
        icon.textContent = '▶';
        icon.classList.add('collapsed');
        if (header) header.classList.add('collapsed');
        
        // Show collapsed elements, hide expanded elements
        const movieName = document.getElementById(`title-${titleNumber}-name`).value;
        if (movieNameBox) {
            movieNameBox.textContent = movieName || '';
            movieNameBox.style.display = movieName ? 'block' : 'none';
        }
        if (contentSuggestion) {
            contentSuggestion.style.display = movieName ? 'none' : 'inline-block';
        }
        
        // Update track counts and duration for collapsed state
        updateCollapsedSummary(titleNumber);
    }
}

// Update collapsed summary information
function updateCollapsedSummary(titleNumber) {
    const summaryInfo = document.querySelector(`[data-title-number="${titleNumber}"] .title-summary-info`);
    if (!summaryInfo) return;
    
    // Count selected tracks
    const audioCheckboxes = document.querySelectorAll(`input[id^="audio-${titleNumber}-"]:checked`);
    const subtitleCheckboxes = document.querySelectorAll(`input[id^="subtitle-${titleNumber}-"]:checked`);
    const audioCount = audioCheckboxes.length;
    const subtitleCount = subtitleCheckboxes.length;
    
    // Get duration from the title data
    const titleSection = document.querySelector(`[data-title-number="${titleNumber}"]`);
    const duration = titleSection.dataset.duration || '';
    
    summaryInfo.innerHTML = `
        ${audioCount > 0 ? `<span class="track-count">🔊 ${audioCount}</span>` : ''}
        ${subtitleCount > 0 ? `<span class="track-count">💬 ${subtitleCount}</span>` : ''}
        ${duration ? `<span class="duration-display">${duration}</span>` : ''}
    `;
}

// Toggle track checkbox
function toggleTrack(trackId) {
    const checkbox = document.getElementById(trackId);
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        // Trigger the change event to save metadata and update summary
        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
    }
}

// Update title summary
function updateTitleSummary(titleNumber) {
    const titleSection = document.querySelector(`[data-title-number="${titleNumber}"]`);
    if (!titleSection) return;
    
    const movieNameBox = titleSection.querySelector('.movie-name-box');
    const movieNameInput = document.getElementById(`title-${titleNumber}-name`);
    const movieName = movieNameInput ? movieNameInput.value || '' : '';
    
    // Update movie name box if it exists (collapsed state) - safely escaped
    if (movieNameBox) {
        movieNameBox.textContent = movieName; // textContent automatically escapes
        movieNameBox.style.display = movieName ? 'block' : 'none';
    }
    
    // Update collapsed summary if in collapsed state
    const content = document.getElementById(`title-${titleNumber}-content`);
    if (content && content.classList.contains('collapsed')) {
        updateCollapsedSummary(titleNumber);
    }
    
    // Update file list status based on whether title is "filled in"
    updateFileListStatus();
}

// Update file list status
function updateFileListStatus() {
    if (!selectedFile) return;
    
    // Check if any title is "filled in" (has movie name and at least 1 audio track)
    let hasFilledTitle = false;
    
    document.querySelectorAll('.title-section').forEach(titleSection => {
        const titleNumber = titleSection.dataset.titleNumber;
        const movieName = document.getElementById(`title-${titleNumber}-name`)?.value || '';
        const audioCheckboxes = document.querySelectorAll(`input[id^="audio-${titleNumber}-"]:checked`);
        
        if (movieName.trim() && audioCheckboxes.length > 0) {
            hasFilledTitle = true;
        }
    });
    
    // Update the file list item
    const fileItem = document.querySelector(`[data-filename="${selectedFile}"]`);
    if (fileItem) {
        if (hasFilledTitle) {
            fileItem.classList.remove('no-metadata');
            fileItem.classList.add('has-metadata');
        } else {
            fileItem.classList.remove('has-metadata');
            fileItem.classList.add('no-metadata');
        }
    }
}

// Cancel encoding for a specific title
function cancelTitleEncoding(titleNumber) {
    if (!selectedFile) {
        console.error('No file selected for cancelling encoding');
        return;
    }
    
    if (window.EncodingUI && window.EncodingUI.cancelTitleEncoding) {
        window.EncodingUI.cancelTitleEncoding(selectedFile, titleNumber);
    } else {
        console.error('EncodingUI not available for cancelling encoding');
    }
}

// Update queue buttons and icons without saving metadata (for real-time updates)
function updateQueueButtonsIfNeeded() {
    // Update Add to Queue button since title selection or movie names may have changed
    if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
        window.EncodingUI.updateAddToQueueButton();
    } else {
        // Try again after a short delay if EncodingUI isn't ready
        setTimeout(() => {
            if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
                window.EncodingUI.updateAddToQueueButton();
            }
        }, 100);
    }
    
    // Also update title status icons since movie names may have changed
    // (icons might need to reflect whether titles are ready to queue)
    if (window.updateAllTitleStatusIcons) {
        window.updateAllTitleStatusIcons();
    }
}

// Save metadata
function saveMetadata() {
    if (!selectedFile || !enhancedMetadata) return;
    
    // Collect all title data (no longer using "selected" concept)
    const titles = enhancedMetadata.titles.map(title => {
        const titleNumber = title.title_number;
        
        // Get selected audio tracks
        const selectedAudioTracks = [];
        title.audio_tracks.forEach(track => {
            const checkbox = document.getElementById(`audio-${titleNumber}-${track.TrackNumber}`);
            if (checkbox && checkbox.checked) {
                selectedAudioTracks.push(track.TrackNumber);
            }
        });
        
        // Get selected subtitle tracks
        const selectedSubtitleTracks = [];
        title.subtitle_tracks.forEach(track => {
            const checkbox = document.getElementById(`subtitle-${titleNumber}-${track.TrackNumber}`);
            if (checkbox && checkbox.checked) {
                selectedSubtitleTracks.push(track.TrackNumber);
            }
        });
        
        // Convert year to full date format (YYYY-01-01)
        const yearValue = document.getElementById(`title-${titleNumber}-date`)?.value || '';
        const releaseDate = yearValue && yearValue.length === 4 ? `${yearValue}-01-01` : '';
        
        // Get form values with null checks
        const movieNameElement = document.getElementById(`title-${titleNumber}-name`);
        const synopsisElement = document.getElementById(`title-${titleNumber}-synopsis`);
        
        return {
            title_number: titleNumber,
            selected: false, // No longer using selected concept - using icon system instead
            movie_name: movieNameElement ? movieNameElement.value : '',
            release_date: releaseDate,
            synopsis: synopsisElement ? synopsisElement.value : '',
            selected_audio_tracks: selectedAudioTracks,
            selected_subtitle_tracks: selectedSubtitleTracks
        };
    });
    
    const metadata = {
        filename: selectedFile,
        file_name: selectedFile,
        size_mb: enhancedMetadata.size_mb,
        titles: titles
    };
    
    // Save to server
    fetch('/api/save_metadata', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(metadata)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the file list item to reflect metadata changes
            updateFileListStatus();
            
            // Trigger a refresh of the current movie metadata to update file list
            if (window.refreshCurrentMovieMetadata) {
                window.refreshCurrentMovieMetadata();
            }
        } else {
            console.error('Failed to save metadata:', data.error);
        }
    })
    .catch(error => {
        console.error('Error saving metadata:', error);
    });
    
    // Update Add to Queue button since title selection or movie names may have changed
    if (window.EncodingUI && window.EncodingUI.updateAddToQueueButton) {
        window.EncodingUI.updateAddToQueueButton();
    }
}

// Show raw output modal
function showRawOutput() {
    if (!selectedFile) return;
    
    fetch(`/api/raw_output/${encodeURIComponent(selectedFile)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.has_raw_data) {
                const modal = document.getElementById('rawOutputModal');
                const content = document.getElementById('rawOutputContent');
                
                // Safely escape all user-controlled content to prevent XSS
                const safeFilename = escapeHtml(data.filename || 'Unknown');
                const safeTimestamp = escapeHtml(data.raw_output.scan_timestamp || 'Unknown');
                const safeCommand = escapeHtml(data.raw_output.command || 'Unknown');
                const safeExitCode = escapeHtml(String(data.raw_output.exit_code !== undefined ? data.raw_output.exit_code : 'Unknown'));
                const safeStdout = escapeHtml(data.raw_output.stdout || 'No output');
                const safeStderr = escapeHtml(data.raw_output.stderr || 'No errors');
                
                content.innerHTML = `
                    <div class="raw-output-section">
                        <h3>File Information</h3>
                        <div class="file-info-content">
                            <div><strong>File:</strong> ${safeFilename}</div>
                            <div><strong>Scan Time:</strong> ${safeTimestamp}</div>
                            <div><strong>Command:</strong> ${safeCommand}</div>
                            <div><strong>Exit Code:</strong> ${safeExitCode}</div>
                        </div>
                    </div>
                    
                    <div class="raw-output-section">
                        <h3>Standard Output</h3>
                        <div class="raw-output-content">${safeStdout}</div>
                    </div>
                    
                    <div class="raw-output-section">
                        <h3>Standard Error</h3>
                        <div class="raw-output-content">${safeStderr}</div>
                    </div>
                `;
                
                modal.style.display = 'block';
            } else {
                // Safely display error message
                const safeMessage = escapeHtml(data.message || 'No raw output available');
                alert(safeMessage);
            }
        })
        .catch(error => {
            // Safely display error message
            const safeError = escapeHtml(error.message || 'Unknown error');
            alert('Error loading raw output: ' + safeError);
        });
}

// Close raw output modal
function closeRawOutputModal() {
    document.getElementById('rawOutputModal').style.display = 'none';
}

// Keyboard navigation
document.addEventListener('keydown', function(event) {
    // Arrow keys for file navigation when file list is focused
    if (event.target.closest('.sidebar')) {
        const fileItems = document.querySelectorAll('.file-item');
        const currentIndex = Array.from(fileItems).findIndex(item => item.classList.contains('active'));
        
        let newIndex;
        if (event.key === 'ArrowUp') {
            newIndex = currentIndex > 0 ? currentIndex - 1 : fileItems.length - 1;
        } else if (event.key === 'ArrowDown') {
            newIndex = currentIndex < fileItems.length - 1 ? currentIndex + 1 : 0;
        }
        
        if (newIndex !== undefined && fileItems[newIndex]) {
            const filename = fileItems[newIndex].dataset.filename;
            selectFile(filename);
        }
    }
});

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('rawOutputModal');
    if (event.target === modal) {
        closeRawOutputModal();
    }
}

// Stats for Nerds functionality
let statsUpdateInterval = null;
let statsEnabled = false;

function initializeStatsForNerds() {
    // Check if stats are enabled from settings
    checkStatsSettings();
}

async function checkStatsSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        
        if (data.success) {
            const enabled = data.settings.stats_for_nerds || false;
            toggleStatsForNerds(enabled);
        }
    } catch (error) {
        console.error('Error checking stats settings:', error);
    }
}

function toggleStatsForNerds(enabled) {
    statsEnabled = enabled;
    const statsSection = document.getElementById('statsForNerds');
    
    if (enabled) {
        statsSection.classList.remove('hidden');
        startStatsUpdates();
    } else {
        statsSection.classList.add('hidden');
        stopStatsUpdates();
        
        // Save the setting when toggled off
        saveStatsForNerdsSetting(false);
    }
}

// Function to save the stats for nerds setting
async function saveStatsForNerdsSetting(enabled) {
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                stats_for_nerds: enabled
            })
        });
        
        if (response.ok) {
            console.log(`📊 Stats for Nerds setting saved: ${enabled}`);
        } else {
            console.error('Failed to save Stats for Nerds setting');
        }
    } catch (error) {
        console.error('Error saving Stats for Nerds setting:', error);
    }
}

function startStatsUpdates() {
    // Update immediately
    updateStats();
    
    // Then update every 5 seconds
    if (statsUpdateInterval) {
        clearInterval(statsUpdateInterval);
    }
    statsUpdateInterval = setInterval(updateStats, 5000);
}

function stopStatsUpdates() {
    if (statsUpdateInterval) {
        clearInterval(statsUpdateInterval);
        statsUpdateInterval = null;
    }
}

async function updateStats() {
    if (!statsEnabled) return;
    
    try {
        // Fetch both health and encoding data in parallel
        const [healthResponse, encodingResponse] = await Promise.all([
            fetch('/health'),
            fetch('/api/encoding/status')
        ]);
        
        if (!healthResponse.ok) {
            throw new Error(`Health endpoint error: HTTP ${healthResponse.status}`);
        }
        
        if (!encodingResponse.ok) {
            throw new Error(`Encoding endpoint error: HTTP ${encodingResponse.status}`);
        }
        
        const healthData = await healthResponse.json();
        const encodingData = await encodingResponse.json();
        
        // Validate that we got some data
        if (!healthData || typeof healthData !== 'object') {
            throw new Error('Invalid health data received');
        }
        
        if (!encodingData || typeof encodingData !== 'object') {
            throw new Error('Invalid encoding data received');
        }
        
        displayStats(healthData, encodingData);
    } catch (error) {
        console.error('Error fetching stats:', error);
        displayStatsError(error.message);
    }
}

function displayStats(healthData, encodingData = null) {
    const statsContent = document.getElementById('statsContent');
    
    // Helper function to safely get nested properties
    const safeGet = (obj, path, defaultValue = 'N/A') => {
        try {
            return path.split('.').reduce((current, key) => current && current[key], obj) ?? defaultValue;
        } catch {
            return defaultValue;
        }
    };
    
    // Helper function to get status class
    const getStatusClass = (value, goodValues = [true, 'ok', 'available']) => {
        if (goodValues.includes(value)) return 'good';
        if (value === false || value === 'error' || value === 'unavailable') return 'error';
        if (typeof value === 'number' && value > 0) return 'warning';
        return '';
    };
    
    // Build encoding section if we have encoding data
    let encodingSection = '';
    if (encodingData && encodingData.success) {
        const summary = safeGet(encodingData, 'summary', {});
        encodingSection = `
            <div class="stats-section">
                <h5>Encoding Jobs</h5>
                <div class="stats-grid">
                    <div class="stats-item">
                        <span class="stats-label">Active:</span>
                        <span class="stats-value ${getStatusClass(summary.encoding_count, [0])}">${summary.encoding_count || 0}</span>
                    </div>
                    <div class="stats-item">
                        <span class="stats-label">Queued:</span>
                        <span class="stats-value ${getStatusClass(summary.queued_count, [0])}">${summary.queued_count || 0}</span>
                    </div>
                    <div class="stats-item">
                        <span class="stats-label">Completed:</span>
                        <span class="stats-value good">${summary.completed_count || 0}</span>
                    </div>
                    <div class="stats-item">
                        <span class="stats-label">Failed:</span>
                        <span class="stats-value ${summary.failed_count > 0 ? 'error' : 'good'}">${summary.failed_count || 0}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    const html = `
        <div class="stats-section">
            <h5>System</h5>
            <div class="stats-grid">
                <div class="stats-item">
                    <span class="stats-label">Status:</span>
                    <span class="stats-value ${getStatusClass(safeGet(healthData, 'status'), ['ok'])}">${safeGet(healthData, 'status', 'Unknown')}</span>
                </div>
                <div class="stats-item">
                    <span class="stats-label">Movies:</span>
                    <span class="stats-value">${safeGet(healthData, 'movie_count', 0)}</span>
                </div>
            </div>
        </div>
        
        <div class="stats-section">
            <h5>HandBrake</h5>
            <div class="stats-grid">
                <div class="stats-item">
                    <span class="stats-label">Status:</span>
                    <span class="stats-value ${getStatusClass(safeGet(healthData, 'handbrake'), ['available'])}">${safeGet(healthData, 'handbrake', 'Unknown')}</span>
                </div>
                <div class="stats-item">
                    <span class="stats-label">Timeout:</span>
                    <span class="stats-value">${safeGet(healthData, 'config.handbrake_timeout', 'N/A')}s</span>
                </div>
            </div>
        </div>
        
        ${encodingSection}
        
        <div class="stats-section">
            <h5>Cache & Watcher</h5>
            <div class="stats-grid">
                <div class="stats-item">
                    <span class="stats-label">Cache:</span>
                    <span class="stats-value">${safeGet(healthData, 'cache_stats.size', 0)}/${safeGet(healthData, 'cache_stats.max_size', 0)}</span>
                </div>
                <div class="stats-item">
                    <span class="stats-label">Enc Cache:</span>
                    <span class="stats-value ${getStatusClass(safeGet(healthData, 'encoding_cache_stats.cache_valid'), [true])}">${safeGet(healthData, 'encoding_cache_stats.cache_size', 0)}</span>
                </div>
                <div class="stats-item">
                    <span class="stats-label">Watching:</span>
                    <span class="stats-value ${getStatusClass(safeGet(healthData, 'file_watcher.is_watching'), [true])}">${safeGet(healthData, 'file_watcher.is_watching') === true ? 'Yes' : 'No'}</span>
                </div>
                <div class="stats-item">
                    <span class="stats-label">Observer:</span>
                    <span class="stats-value ${getStatusClass(safeGet(healthData, 'file_watcher.observer_alive'), [true])}">${safeGet(healthData, 'file_watcher.observer_alive') === true ? 'OK' : 'Dead'}</span>
                </div>
            </div>
        </div>
        
        <div class="stats-timestamp">
            Last updated: ${new Date().toLocaleTimeString()}
        </div>
    `;
    
    statsContent.innerHTML = html;
}

function displayStatsError(errorMessage = 'Unknown error') {
    const statsContent = document.getElementById('statsContent');
    statsContent.innerHTML = `
        <div class="stats-loading" style="color: #dc3545;">
            ❌ Error loading stats
        </div>
        <div class="stats-section">
            <div style="font-size: 0.65rem; color: #6c757d; text-align: center; margin-top: 0.5rem;">
                ${errorMessage}
            </div>
        </div>
        <div class="stats-timestamp">
            Last updated: ${new Date().toLocaleTimeString()}
        </div>
    `;
}

function formatUptime(seconds) {
    if (!seconds || typeof seconds !== 'number' || seconds < 0) {
        return 'Unknown';
    }
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 24) {
        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;
        return `${days}d ${remainingHours}h`;
    } else if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Initialize stats when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeStatsForNerds();
});

// Encoding progress and status update functions
function updateEncodingProgress(jobId, progress) {
    console.log(`Updating progress for job ${jobId}:`, progress);
    
    // If we're on the encoding page, let encoding.js handle it
    if (typeof updateJobProgress === 'function') {
        updateJobProgress(jobId, progress);
    }
    
    // Update file list indicators using the mapping from encoding.js
    if (typeof window.jobToFileMapping !== 'undefined') {
        const fileName = window.jobToFileMapping[jobId];
        if (fileName) {
            updateFileEncodingIndicator(fileName, progress);
        }
    }
}

function updateEncodingStatus(jobId, status) {
    console.log(`Updating status for job ${jobId}:`, status);
    
    // If we're on the encoding page, let encoding.js handle it
    if (typeof updateJobStatus === 'function') {
        updateJobStatus(jobId, status);
    }
    
    // Update file list indicators using the mapping from encoding.js
    if (typeof window.jobToFileMapping !== 'undefined') {
        const fileName = window.jobToFileMapping[jobId];
        if (fileName) {
            updateFileEncodingStatus(fileName, status);
        }
    }
    
    // Update "Add to Queue" buttons based on status
    updateAddToQueueButtons();
}

function updateFileEncodingIndicator(fileName, progress) {
    // Find the file item that corresponds to this filename
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
            
            // Add encoding class
            item.classList.add('encoding');
        }
    });
}

function updateFileEncodingStatus(fileName, status) {
    // Update file indicators based on encoding status
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

function updateAddToQueueButtons() {
    // Update "Add to Queue" buttons based on current encoding status
    const addButtons = document.querySelectorAll('[data-action="add-to-queue"]');
    addButtons.forEach(button => {
        // You might want to disable buttons for files already in queue
        // or update button text based on status
        // This depends on your specific UI requirements
    });
}

// Listen for settings changes via WebSocket
if (typeof socket !== 'undefined') {
    socket.on('settings_updated', function(data) {
        if (data.settings && 'stats_for_nerds' in data.settings) {
            toggleStatsForNerds(data.settings.stats_for_nerds);
        }
    });
    
    // Listen for encoding notifications
    socket.on('notification', function(data) {
        handleEncodingNotification(data);
    });
}

// Handle encoding notifications from WebSocket
function handleEncodingNotification(data) {
    if (!data || !data.type) return;
    
    switch (data.type) {
        case 'completion':
            showCompletionNotification(data);
            break;
        case 'failure':
            showFailureNotification(data);
            break;
        case 'queue_empty':
            showAlert(data.message, 'info');
            break;
        default:
            showAlert(data.message, 'info');
    }
}

// Show completion notification with delete button
function showCompletionNotification(data) {
    if (!data.job) {
        showAlert(data.message, 'success');
        return;
    }
    
    const job = data.job;
    const movieName = job.movie_name || job.file_name;
    const outputPath = job.output_path;
    const outputFilename = job.output_filename;
    
    // Create enhanced notification HTML
    const notificationHTML = `
        <div class="completion-notification">
            <div class="notification-content">
                <div class="notification-icon">✅</div>
                <div class="notification-details">
                    <div class="notification-title">Encoding Completed</div>
                    <div class="notification-subtitle">${escapeHtml(movieName)}</div>
                    <div class="notification-filename">${escapeHtml(outputFilename)}</div>
                </div>
                <div class="notification-actions">
                    <button class="notification-btn delete-btn" onclick="deleteEncodedFile('${escapeHtml(outputPath)}', '${escapeHtml(outputFilename)}')">
                        🗑️ Delete
                    </button>
                    <button class="notification-btn close-btn" onclick="closeNotification(this)">
                        ✕
                    </button>
                </div>
            </div>
        </div>
    `;
    
    showEnhancedNotification(notificationHTML, 'success', 10000); // Show for 10 seconds
}

// Show failure notification
function showFailureNotification(data) {
    if (!data.job) {
        showAlert(data.message, 'error');
        return;
    }
    
    const job = data.job;
    const movieName = job.movie_name || job.file_name;
    
    // Create enhanced notification HTML
    const notificationHTML = `
        <div class="failure-notification">
            <div class="notification-content">
                <div class="notification-icon">❌</div>
                <div class="notification-details">
                    <div class="notification-title">Encoding Failed</div>
                    <div class="notification-subtitle">${escapeHtml(movieName)}</div>
                    <div class="notification-error">${escapeHtml(job.error_message || 'Unknown error')}</div>
                </div>
                <div class="notification-actions">
                    <button class="notification-btn view-logs-btn" onclick="viewFailureLogs('${escapeHtml(job.file_name)}', ${job.title_number})">
                        📄 View Logs
                    </button>
                    <button class="notification-btn close-btn" onclick="closeNotification(this)">
                        ✕
                    </button>
                </div>
            </div>
        </div>
    `;
    
    showEnhancedNotification(notificationHTML, 'error', 15000); // Show for 15 seconds
}

// Show enhanced notification with custom HTML
function showEnhancedNotification(html, type = 'info', duration = 5000) {
    // Create notification container if it doesn't exist
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'notification-container';
        document.body.appendChild(container);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `enhanced-notification ${type}`;
    notification.innerHTML = html;
    
    // Add to container
    container.appendChild(notification);
    
    // Auto-remove after duration
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('fade-out');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }, duration);
}

// Close notification
function closeNotification(button) {
    const notification = button.closest('.enhanced-notification');
    if (notification) {
        notification.classList.add('fade-out');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }
}

// Delete encoded file
async function deleteEncodedFile(filePath, fileName) {
    if (!confirm(`Are you sure you want to delete "${fileName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/encoding/delete-file', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_path: filePath
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`Successfully deleted ${data.file_name}`, 'success');
            // Close the notification that contained the delete button
            const deleteBtn = event.target;
            closeNotification(deleteBtn);
        } else {
            showAlert(`Error deleting file: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting file:', error);
        showAlert('Error deleting file: ' + error.message, 'error');
    }
}

// Check encoding status for all titles and update UI
async function checkEncodingStatusForAllTitles() {
    if (!selectedFile) return;
    
    try {
        const response = await fetch('/api/encoding/status');
        const data = await response.json();
        
        if (data.success) {
            // Check each title for encoding status
            const titleSections = document.querySelectorAll('.title-section');
            titleSections.forEach(titleSection => {
                const titleNumber = parseInt(titleSection.dataset.titleNumber);
                updateTitleEncodingStatus(titleNumber, data.jobs);
            });
        }
    } catch (error) {
        console.error('Error checking encoding status:', error);
    }
}

// Update encoding status for a specific title
function updateTitleEncodingStatus(titleNumber, allJobs) {
    if (!selectedFile) return;
    
    const statusSection = document.getElementById(`encoding-status-${titleNumber}`);
    const completionIcon = document.getElementById(`completion-icon-${titleNumber}`);
    if (!statusSection) return;
    
    // Find jobs for this file and title
    const relevantJobs = [];
    
    // Check all job categories
    ['encoding', 'queued', 'completed', 'failed'].forEach(category => {
        if (allJobs[category]) {
            allJobs[category].forEach(job => {
                if (job.file_name === selectedFile && job.title_number === titleNumber) {
                    relevantJobs.push({...job, category});
                }
            });
        }
    });
    
    if (relevantJobs.length === 0) {
        statusSection.innerHTML = '';
        if (completionIcon) completionIcon.style.display = 'none';
        return;
    }
    
    // Show the most recent/relevant job
    const job = relevantJobs[0];
    let statusHTML = '';
    
    switch (job.category) {
        case 'encoding':
            if (completionIcon) completionIcon.style.display = 'none';
            statusHTML = `
                <div class="encoding-status encoding">
                    <span class="status-icon">🔄</span>
                    <span class="status-text">Encoding in progress...</span>
                    <div class="progress-info">
                        ${job.progress ? `${job.progress.percentage.toFixed(1)}% at ${job.progress.fps.toFixed(1)} fps` : ''}
                    </div>
                </div>
            `;
            break;
            
        case 'queued':
            if (completionIcon) completionIcon.style.display = 'none';
            statusHTML = `
                <div class="encoding-status queued">
                    <span class="status-icon">⏳</span>
                    <span class="status-text">Queued for encoding</span>
                </div>
            `;
            break;
            
        case 'completed':
            // Show completion icon in title header
            if (completionIcon) completionIcon.style.display = 'inline';
            
            // Get file info for the completed encoding - use correct property names
            const outputFileName = job.output_filename || `${job.movie_name || 'output'}.mp4`;
            const outputPath = job.output_path || '';
            
            // Try to get file size from job progress data first, then from server if needed
            let fileSizeInfo = 'Unknown size';
            if (job.progress && job.progress.output_size_mb) {
                // File size is stored in MB in progress data
                fileSizeInfo = formatFileSize(job.progress.output_size_mb * 1024 * 1024);
            } else if (outputPath) {
                // File size not in job data, we'll need to get it from the server
                fileSizeInfo = 'Calculating...';
                // Request file size asynchronously
                getOutputFileSize(outputPath).then(size => {
                    if (size) {
                        const sizeElement = document.querySelector(`#encoding-status-${titleNumber} .file-size-info`);
                        if (sizeElement) {
                            sizeElement.textContent = formatFileSize(size);
                        }
                    }
                });
            }
            
            statusHTML = `
                <div class="encoding-status completed">
                    <span class="status-icon">✅</span>
                    <span class="status-text">Encoding completed</span>
                    <span class="completion-time">${formatRelativeTime(job.completed_at)}</span>
                    <div class="completion-details">
                        <div class="output-file-info">
                            <strong>Output:</strong> ${escapeHtml(outputFileName)} (<span class="file-size-info">${fileSizeInfo}</span>)
                        </div>
                        <div class="completion-actions">
                            <button class="completion-btn delete-output-btn" onclick="deleteEncodedFile('${escapeHtml(selectedFile)}', ${titleNumber}, '${escapeHtml(outputFileName)}', '${escapeHtml(outputPath)}')">
                                🗑️ Delete Output
                            </button>
                        </div>
                    </div>
                </div>
            `;
            break;
            
        case 'failed':
            if (completionIcon) completionIcon.style.display = 'none';
            statusHTML = `
                <div class="encoding-status failed">
                    <span class="status-icon">❌</span>
                    <span class="status-text">Encoding failed</span>
                    <span class="failure-time">${formatRelativeTime(job.completed_at)}</span>
                    <div class="failure-actions">
                        <button class="failure-btn view-logs-btn" onclick="viewFailureLogs('${escapeHtml(selectedFile)}', ${titleNumber})">
                            📄 View Logs
                        </button>
                        <button class="failure-btn clear-failure-btn" onclick="clearFailure('${escapeHtml(selectedFile)}', ${titleNumber})">
                            🔄 Clear & Retry
                        </button>
                    </div>
                    ${job.error_message ? `<div class="error-message">${escapeHtml(job.error_message)}</div>` : ''}
                </div>
            `;
            break;
    }
    
    statusSection.innerHTML = statusHTML;
}

// Get output file size from server
async function getOutputFileSize(outputPath) {
    try {
        const response = await fetch('/api/encoding/output-file-size', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                output_path: outputPath
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.file_size) {
            return data.file_size;
        } else {
            console.warn('Could not get output file size:', data.error);
            return null;
        }
    } catch (error) {
        console.error('Error getting output file size:', error);
        return null;
    }
}

// Format file size in human readable format
function formatFileSize(bytes) {
    if (!bytes) return 'Unknown size';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Delete encoded file and reset status
async function deleteEncodedFile(fileName, titleNumber, outputFileName, outputPath) {
    const confirmed = confirm(`Are you sure you want to delete the encoded file "${outputFileName}"?\n\nThis will also reset the encoding status so you can re-encode this title.`);
    
    if (!confirmed) return;
    
    try {
        const response = await fetch('/api/encoding/delete-file', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_path: outputPath || `${outputFileName}` // Use full path if available, fallback to filename
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Backend now handles both file deletion and job status clearing
            showAlert(data.message || 'Encoded file deleted successfully. You can now re-encode this title.', 'success');
            // Refresh the encoding status
            checkEncodingStatusForAllTitles();
        } else {
            showAlert('Error deleting file: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('Error deleting file: ' + error.message, 'error');
    }
}

// View failure logs for a specific title
async function viewFailureLogs(fileName, titleNumber) {
    try {
        const response = await fetch(`/api/encoding/failure-logs/${encodeURIComponent(fileName)}/${titleNumber}`);
        const data = await response.json();
        
        if (data.success) {
            showFailureLogsModal(data.job);
        } else {
            showAlert('Error loading failure logs: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error loading failure logs:', error);
        showAlert('Error loading failure logs: ' + error.message, 'error');
    }
}

// Clear a failed job so it can be retried
async function clearFailure(fileName, titleNumber) {
    if (!confirm('Clear this failed job? This will allow you to retry encoding this title.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/encoding/clear-failure/${encodeURIComponent(fileName)}/${titleNumber}`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showAlert('Failed job cleared. You can now retry encoding this title.', 'success');
            // Refresh the encoding status
            checkEncodingStatusForAllTitles();
        } else {
            showAlert('Error clearing failure: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error clearing failure:', error);
        showAlert('Error clearing failure: ' + error.message, 'error');
    }
}

// Show failure logs in a modal
function showFailureLogsModal(job) {
    // Store logs globally for the copy function
    window.currentFailureLogs = job.failure_logs;
    
    // Create modal HTML
    const modalHTML = `
        <div class="modal-overlay" id="failureLogsModal" onclick="closeFailureLogsModal()">
            <div class="modal-content failure-logs-modal" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h2>Encoding Failure Logs</h2>
                    <button class="modal-close" onclick="closeFailureLogsModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="failure-info">
                        <div class="failure-details">
                            <strong>File:</strong> ${escapeHtml(job.file_name)}<br>
                            <strong>Title:</strong> ${job.title_number} - ${escapeHtml(job.movie_name)}<br>
                            <strong>Preset:</strong> ${escapeHtml(job.preset_name)}<br>
                            <strong>Failed:</strong> ${formatRelativeTime(job.failed_at)}<br>
                            ${job.error_message ? `<strong>Error:</strong> ${escapeHtml(job.error_message)}<br>` : ''}
                        </div>
                    </div>
                    <div class="logs-container">
                        <h3>Last ${job.failure_logs.length} lines of output:</h3>
                        <div class="logs-content">
                            ${job.failure_logs.length > 0 ? 
                                job.failure_logs.map(line => `<div class="log-line">${escapeHtml(line)}</div>`).join('') :
                                '<div class="no-logs">No logs available</div>'
                            }
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="closeFailureLogsModal()">Close</button>
                    <button class="btn btn-primary" onclick="copyLogsToClipboard()">Copy Logs</button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Focus on modal for accessibility
    document.getElementById('failureLogsModal').focus();
}

// Close failure logs modal
function closeFailureLogsModal() {
    const modal = document.getElementById('failureLogsModal');
    if (modal) {
        modal.remove();
    }
    
    // Clean up global variable
    if (window.currentFailureLogs) {
        delete window.currentFailureLogs;
    }
}

// Copy logs to clipboard
async function copyLogsToClipboard() {
    try {
        if (!window.currentFailureLogs || !Array.isArray(window.currentFailureLogs)) {
            showAlert('No logs available to copy', 'error');
            return;
        }
        
        const logsText = window.currentFailureLogs.join('\n');
        await navigator.clipboard.writeText(logsText);
        showAlert('Logs copied to clipboard', 'success');
    } catch (error) {
        console.error('Error copying logs:', error);
        showAlert('Error copying logs to clipboard', 'error');
    }
}

// Format relative time (e.g., "2 hours ago")
function formatRelativeTime(isoString) {
    if (!isoString) return '';
    
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMinutes = Math.floor(diffMs / 60000);
        
        if (diffMinutes < 1) return 'just now';
        if (diffMinutes < 60) return `${diffMinutes} min ago`;
        
        const diffHours = Math.floor(diffMinutes / 60);
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        
        const diffDays = Math.floor(diffHours / 24);
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } catch (error) {
        return '';
    }
}

// Show alert message
function showAlert(message, type = 'info') {
    // Use existing notification system if available
    if (window.showNotification) {
        window.showNotification(message, type);
    } else {
        // Fallback to alert
        alert(message);
    }
}

// Note: Encoding progress and status events are handled by encoding.js
// to avoid conflicts and ensure proper handling

// Title Status Icon Management
function handleTitleStatusClick(titleNumber) {
    const iconElement = document.getElementById(`title-status-${titleNumber}`);
    const statusIcon = iconElement.querySelector('.status-icon');
    const currentIcon = statusIcon.textContent;
    
    switch (currentIcon) {
        case '➕': // Plus - Queue title
            queueTitleForEncoding(titleNumber);
            break;
        case '❌': // Cross - Retry failed encoding
            retryFailedEncoding(titleNumber);
            break;
        case '➖': // Minus - Remove from queue (shown on hover over hourglass)
            removeFromQueue(titleNumber);
            break;
    }
}

function handleTitleStatusHover(titleNumber, isHovering) {
    const iconElement = document.getElementById(`title-status-${titleNumber}`);
    const statusIcon = iconElement.querySelector('.status-icon');
    const currentIcon = statusIcon.textContent;
    
    if (isHovering) {
        switch (currentIcon) {
            case '❌': // Cross - Show retry icon on hover
                statusIcon.textContent = '🔄';
                iconElement.title = 'Click to retry encoding';
                break;
            case '⏳': // Hourglass - Show minus icon on hover
                statusIcon.textContent = '➖';
                iconElement.title = 'Click to remove from queue';
                break;
        }
    } else {
        // Restore original icon when not hovering
        updateTitleStatusIcon(titleNumber);
    }
}

function updateTitleStatusIcon(titleNumber) {
    if (!selectedFile) return;
    
    const iconElement = document.getElementById(`title-status-${titleNumber}`);
    if (!iconElement) return;
    
    const statusIcon = iconElement.querySelector('.status-icon');
    
    // Get the current encoding status for this title
    const status = getTitleEncodingStatus(selectedFile, titleNumber);
    
    switch (status) {
        case 'completed':
            statusIcon.textContent = '✅';
            iconElement.title = 'Encoding completed successfully';
            iconElement.className = 'title-status-icon status-completed';
            break;
        case 'failed':
            statusIcon.textContent = '❌';
            iconElement.title = 'Encoding failed - hover to retry';
            iconElement.className = 'title-status-icon status-failed';
            break;
        case 'queued':
            statusIcon.textContent = '⏳';
            iconElement.title = 'Queued for encoding - hover to remove';
            iconElement.className = 'title-status-icon status-queued';
            break;
        case 'encoding':
            statusIcon.textContent = '🔄';
            iconElement.title = 'Currently encoding';
            iconElement.className = 'title-status-icon status-encoding';
            break;
        default: // not_queued
            statusIcon.textContent = '➕';
            iconElement.title = 'Click to queue for encoding';
            iconElement.className = 'title-status-icon status-not-queued';
            break;
    }
}

function getTitleEncodingStatus(fileName, titleNumber) {
    // This function should integrate with the existing encoding system
    // For now, return a default status - this will be updated when integrated with encoding.js
    if (window.EncodingUI && typeof window.EncodingUI.getJobStatus === 'function') {
        return window.EncodingUI.getJobStatus(fileName, titleNumber);
    }
    return 'not_queued';
}

function queueTitleForEncoding(titleNumber) {
    if (!selectedFile) return;
    
    // Validate that the title has required data
    const movieName = document.getElementById(`title-${titleNumber}-name`)?.value || '';
    const audioCheckboxes = document.querySelectorAll(`input[id^="audio-${titleNumber}-"]:checked`);
    
    if (!movieName.trim()) {
        showAlert('Please enter a movie name before queuing for encoding', 'error');
        return;
    }
    
    if (audioCheckboxes.length === 0) {
        showAlert('Please select at least one audio track before queuing for encoding', 'error');
        return;
    }
    
    // Call the existing encoding system to queue the title
    if (window.EncodingUI && typeof window.EncodingUI.queueTitle === 'function') {
        window.EncodingUI.queueTitle(selectedFile, titleNumber);
    } else {
        console.warn('EncodingUI not available for queuing title');
        // Fallback: emit socket event directly
        if (window.socket) {
            window.socket.emit('queue_title', {
                file_name: selectedFile,
                title_number: titleNumber
            });
        }
    }
    
    // Update icon immediately to show queued state
    updateTitleStatusIcon(titleNumber);
}

function retryFailedEncoding(titleNumber) {
    if (!selectedFile) return;
    
    // Call the existing encoding system to retry the failed encoding
    if (window.EncodingUI && typeof window.EncodingUI.retryTitle === 'function') {
        window.EncodingUI.retryTitle(selectedFile, titleNumber);
    } else {
        console.warn('EncodingUI not available for retrying title');
        // Fallback: emit socket event directly
        if (window.socket) {
            window.socket.emit('retry_title', {
                file_name: selectedFile,
                title_number: titleNumber
            });
        }
    }
    
    // Update icon immediately to show queued state
    updateTitleStatusIcon(titleNumber);
}

function removeFromQueue(titleNumber) {
    if (!selectedFile) return;
    
    // Call the existing encoding system to remove from queue
    if (window.EncodingUI && typeof window.EncodingUI.removeFromQueue === 'function') {
        window.EncodingUI.removeFromQueue(selectedFile, titleNumber);
    } else {
        console.warn('EncodingUI not available for removing from queue');
        // Fallback: emit socket event directly
        if (window.socket) {
            window.socket.emit('remove_from_queue', {
                file_name: selectedFile,
                title_number: titleNumber
            });
        }
    }
    
    // Update icon immediately to show not queued state
    updateTitleStatusIcon(titleNumber);
}

// Update all title status icons when file is selected or status changes
function updateAllTitleStatusIcons() {
    if (!selectedFile) return;
    
    document.querySelectorAll('.title-section').forEach(titleSection => {
        const titleNumber = parseInt(titleSection.dataset.titleNumber);
        if (titleNumber) {
            updateTitleStatusIcon(titleNumber);
        }
    });
}

// Hook into existing file selection to update icons
const originalSelectFile = window.selectFile;
if (originalSelectFile) {
    window.selectFile = function(fileName) {
        originalSelectFile(fileName);
        // Update icons after file selection
        setTimeout(updateAllTitleStatusIcons, 100);
    };
}
