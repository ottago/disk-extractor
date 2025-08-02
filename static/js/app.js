// Global variables
let currentMovies = [];
let selectedFile = null;
let enhancedMetadata = null;

// Initialize the application
function initializeApp(movies) {
    currentMovies = movies;
    console.log('App initialized with', movies.length, 'movies');
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
    selectedFile = filename;
    
    // Update UI
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-filename="${filename}"]`).classList.add('active');
    
    // Find movie data
    const movie = currentMovies.find(m => m.file_name === filename);
    if (!movie) {
        console.error('Movie not found:', filename);
        return;
    }
    
    // Show basic file info
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
    console.log('Showing loading indicator for:', filename);
    showTitlesLoading();
    
    // Try to load cached enhanced metadata for THIS specific file
    loadEnhancedMetadata(filename);
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
                
                if (data.success && data.metadata && data.metadata.titles && data.metadata.titles.length > 0) {
                    // We have cached HandBrake data - display it
                    console.log('Setting enhancedMetadata and calling displayEnhancedMetadata for', filename);
                    enhancedMetadata = data.metadata;
                    displayEnhancedMetadata();
                    document.getElementById('rawOutputButton').style.display = 'inline-block';
                    console.log('Loaded cached metadata for', filename, 'with', data.metadata.titles.length, 'titles');
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
    document.getElementById('scanErrorMessage').textContent = error;
    document.getElementById('scanError').style.display = 'block';
    document.getElementById('enhancedMetadata').style.display = 'block';
    document.getElementById('titlesContainer').innerHTML = '';
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
}

// Create title element
function createTitleElement(title) {
    const titleDiv = document.createElement('div');
    titleDiv.className = 'title-section';
    titleDiv.dataset.titleNumber = title.title_number;
    
    const suggested = title.suggestions.title.suggested ? 'suggested' : 'not-suggested';
    const suggestedText = title.suggestions.title.reason || 'Unknown';
    
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
    
    // Determine if title should be collapsed by default (less than 30 minutes)
    const durationInSeconds = parseDuration(title.duration);
    const isShortTitle = durationInSeconds > 0 && durationInSeconds < 1800; // 30 minutes = 1800 seconds
    const shouldCollapseByDefault = isShortTitle && !title.selected;
    
    console.log(`Title ${title.title_number}: duration="${title.duration}", seconds=${durationInSeconds}, isShort=${isShortTitle}, selected=${title.selected}, shouldCollapse=${shouldCollapseByDefault}`);
    
    // Helper function to create title summary
    function createTitleSummary() {
        const movieName = title.movie_name || '';
        const year = getYear(title.release_date);
        const audioCount = title.selected_audio_tracks.length;
        const subtitleCount = title.selected_subtitle_tracks.length;
        const duration = title.duration || '';
        
        let summary = `Title ${title.title_number}`;
        if (movieName) {
            summary += `   ${movieName}`;
            if (year) {
                summary += ` (${year})`;
            }
        }
        
        return `
            <span>${summary}</span>
            ${audioCount > 0 ? `<span class="track-count">🔊 ${audioCount}</span>` : ''}
            ${subtitleCount > 0 ? `<span class="track-count">💬 ${subtitleCount}</span>` : ''}
            ${duration ? `<span>${duration}</span>` : ''}
        `;
    }
    
    titleDiv.innerHTML = `
        <div class="title-header ${shouldCollapseByDefault ? 'collapsed' : ''}" onclick="toggleTitle(${title.title_number})">
            <div class="title-checkbox">
                <input type="checkbox" 
                       id="title-${title.title_number}-selected"
                       ${title.selected ? 'checked' : ''}
                       onclick="event.stopPropagation(); saveMetadata();">
            </div>
            <div class="title-info" style="display: ${shouldCollapseByDefault ? 'none' : 'flex'};">
                <span>Title ${title.title_number}</span>
                <span class="suggestion-badge ${suggested}">${suggestedText}</span>
            </div>
            <div id="title-${title.title_number}-summary" class="title-summary" style="display: ${shouldCollapseByDefault ? 'flex' : 'none'};">
                ${createTitleSummary()}
            </div>
            <div class="expand-icon ${shouldCollapseByDefault ? 'collapsed' : ''}" id="title-${title.title_number}-icon">${shouldCollapseByDefault ? '▶' : '▼'}</div>
        </div>
        
        <div class="title-content ${shouldCollapseByDefault ? 'collapsed' : ''}" id="title-${title.title_number}-content" style="display: ${shouldCollapseByDefault ? 'none' : 'block'};">
            <div class="form-group">
                <label for="title-${title.title_number}-name">Movie Name:</label>
                <input type="text" 
                       id="title-${title.title_number}-name" 
                       value="${title.movie_name || ''}"
                       onchange="saveMetadata(); updateTitleSummary(${title.title_number});">
            </div>
            
            <div class="form-group">
                <label for="title-${title.title_number}-date">Release Year:</label>
                <input type="text" 
                       id="title-${title.title_number}-date" 
                       value="${getYear(title.release_date)}"
                       placeholder="YYYY"
                       maxlength="4"
                       onchange="saveMetadata(); updateTitleSummary(${title.title_number});">
            </div>
            
            <div class="form-group">
                <label for="title-${title.title_number}-synopsis">Synopsis:</label>
                <textarea id="title-${title.title_number}-synopsis" 
                          rows="3"
                          onchange="saveMetadata()">${title.synopsis || ''}</textarea>
            </div>
            
            <div class="tracks-section">
                <h4>Audio Tracks</h4>
                <div class="track-list">
                    ${title.audio_tracks.map((track, index) => {
                        const suggestion = title.suggestions.audio[index];
                        const suggestedClass = suggestion && suggestion.suggested ? 'suggested' : '';
                        const isChecked = title.selected_audio_tracks.includes(track.TrackNumber) ? 'checked' : '';
                        return `
                            <div class="track-item ${suggestedClass}" onclick="toggleTrack('audio-${title.title_number}-${track.TrackNumber}')">
                                <input type="checkbox" 
                                       id="audio-${title.title_number}-${track.TrackNumber}"
                                       ${isChecked}
                                       onchange="saveMetadata(); updateTitleSummary(${title.title_number}); event.stopPropagation();">
                                <div class="track-info">
                                    <div class="track-language">${suggestion ? suggestion.language_name : 'Unknown'}</div>
                                    <div class="track-details">${track.Description || ''}</div>
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
                        return `
                            <div class="track-item ${suggestedClass}" onclick="toggleTrack('subtitle-${title.title_number}-${track.TrackNumber}')">
                                <input type="checkbox" 
                                       id="subtitle-${title.title_number}-${track.TrackNumber}"
                                       ${isChecked}
                                       onchange="saveMetadata(); updateTitleSummary(${title.title_number}); event.stopPropagation();">
                                <div class="track-info">
                                    <div class="track-language">${suggestion ? suggestion.language_name : 'Unknown'}</div>
                                    <div class="track-details">${track.Name || ''}</div>
                                </div>
                            </div>
                        `;
                    }).join('')}
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
    const summary = document.getElementById(`title-${titleNumber}-summary`);
    const titleSection = document.querySelector(`[data-title-number="${titleNumber}"]`);
    
    if (!content || !icon || !summary || !titleSection) {
        console.error('Could not find title elements for', titleNumber);
        return;
    }
    
    const header = titleSection.querySelector('.title-header');
    const titleInfo = titleSection.querySelector('.title-info');
    
    if (content.style.display === 'none' || content.classList.contains('collapsed')) {
        // Expand
        content.style.display = 'block';
        content.classList.remove('collapsed');
        icon.textContent = '▼';
        icon.classList.remove('collapsed');
        if (header) header.classList.remove('collapsed');
        summary.style.display = 'none';
        if (titleInfo) titleInfo.style.display = 'flex';
    } else {
        // Collapse
        content.style.display = 'none';
        content.classList.add('collapsed');
        icon.textContent = '▶';
        icon.classList.add('collapsed');
        if (header) header.classList.add('collapsed');
        summary.style.display = 'flex';
        if (titleInfo) titleInfo.style.display = 'none';
    }
}

// Toggle track checkbox
function toggleTrack(trackId) {
    const checkbox = document.getElementById(trackId);
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        // Trigger the change event to save metadata and update summary
        checkbox.dispatchEvent(new Event('change'));
    }
}

// Update title summary
function updateTitleSummary(titleNumber) {
    const summaryElement = document.getElementById(`title-${titleNumber}-summary`);
    if (!summaryElement) return;
    
    // Get current values
    const movieName = document.getElementById(`title-${titleNumber}-name`).value || '';
    const year = document.getElementById(`title-${titleNumber}-date`).value || '';
    const duration = summaryElement.closest('.title-section').querySelector('.duration')?.textContent || '';
    
    // Count selected tracks
    const audioCheckboxes = document.querySelectorAll(`input[id^="audio-${titleNumber}-"]:checked`);
    const subtitleCheckboxes = document.querySelectorAll(`input[id^="subtitle-${titleNumber}-"]:checked`);
    const audioCount = audioCheckboxes.length;
    const subtitleCount = subtitleCheckboxes.length;
    
    // Build summary
    let summary = `Title ${titleNumber}`;
    if (movieName) {
        summary += `   ${movieName}`;
        if (year) {
            summary += ` (${year})`;
        }
    }
    
    summaryElement.innerHTML = `
        <span>${summary}</span>
        ${audioCount > 0 ? `<span class="track-count">🔊 ${audioCount}</span>` : ''}
        ${subtitleCount > 0 ? `<span class="track-count">💬 ${subtitleCount}</span>` : ''}
        ${duration ? `<span>${duration}</span>` : ''}
    `;
    
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

// Save metadata
function saveMetadata() {
    if (!selectedFile || !enhancedMetadata) return;
    
    // Collect all title data
    const titles = enhancedMetadata.titles.map(title => {
        const titleNumber = title.title_number;
        const selected = document.getElementById(`title-${titleNumber}-selected`).checked;
        
        if (!selected) {
            return {
                title_number: titleNumber,
                selected: false,
                movie_name: '',
                release_date: '',
                synopsis: '',
                selected_audio_tracks: [],
                selected_subtitle_tracks: []
            };
        }
        
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
        const yearValue = document.getElementById(`title-${titleNumber}-date`).value;
        const releaseDate = yearValue && yearValue.length === 4 ? `${yearValue}-01-01` : '';
        
        return {
            title_number: titleNumber,
            selected: true,
            movie_name: document.getElementById(`title-${titleNumber}-name`).value,
            release_date: releaseDate,
            synopsis: document.getElementById(`title-${titleNumber}-synopsis`).value,
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
        if (!data.success) {
            console.error('Failed to save metadata:', data.error);
        }
    })
    .catch(error => {
        console.error('Error saving metadata:', error);
    });
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
                
                content.innerHTML = `
                    <div class="raw-output-section">
                        <strong>File:</strong> ${data.filename}<br>
                        <strong>Scan Time:</strong> ${data.raw_output.scan_timestamp || 'Unknown'}<br>
                        <strong>Command:</strong> ${data.raw_output.command || 'Unknown'}<br>
                        <strong>Exit Code:</strong> ${data.raw_output.exit_code !== undefined ? data.raw_output.exit_code : 'Unknown'}
                    </div>
                    
                    <div class="raw-output-section">
                        <h3>Standard Output:</h3>
                        <div class="raw-output-content">${data.raw_output.stdout || 'No output'}</div>
                    </div>
                    
                    <div class="raw-output-section">
                        <h3>Standard Error:</h3>
                        <div class="raw-output-content">${data.raw_output.stderr || 'No errors'}</div>
                    </div>
                `;
                
                modal.style.display = 'block';
            } else {
                alert(data.message || 'No raw output available');
            }
        })
        .catch(error => {
            alert('Error loading raw output: ' + error.message);
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
