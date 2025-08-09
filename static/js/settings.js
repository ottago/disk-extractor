// Settings page JavaScript
(function() {
    'use strict';
    
    // Settings management
    let currentSettings = {};
    
    // Load current settings and templates
    async function loadSettings() {
        try {
            // Load templates first so the preset dropdown is populated
            await loadTemplates();
            
            // Then load and populate settings
            const response = await fetch('/api/settings');
            const data = await response.json();
            
            if (data.success) {
                currentSettings = data.settings;
                populateForm(currentSettings);
            } else {
                showAlert('Error loading settings: ' + data.error, 'error');
            }
        } catch (error) {
            showAlert('Error loading settings: ' + error.message, 'error');
        }
    }
    
    // Load available templates
    async function loadTemplates() {
        try {
            const response = await fetch('/api/templates');
            const data = await response.json();
            
            if (data.success) {
                updateTemplatesList(data.templates);
                populatePresetDropdown(data.templates);
                
                // If we have current settings, reapply the preset selection
                if (currentSettings && currentSettings.default_preset) {
                    setPresetSelection(currentSettings.default_preset);
                }
            } else {
                console.error('Error loading templates:', data.error);
            }
        } catch (error) {
            console.error('Error loading templates:', error.message);
        }
    }
    
    // Set preset selection (helper function)
    function setPresetSelection(presetValue) {
        const presetSelect = document.getElementById('defaultPreset');
        const optionExists = Array.from(presetSelect.options).some(option => option.value === presetValue);
        
        if (optionExists) {
            presetSelect.value = presetValue;
            console.log(`Set preset selection to: ${presetValue}`);
        } else if (presetValue && presetValue !== '') {
            console.warn(`Preset "${presetValue}" not available in dropdown`);
            showAlert(`Warning: Saved preset "${presetValue}" is no longer available. Please select a new default preset.`, 'warning');
        }
    }
    
    // Update templates list display
    function updateTemplatesList(templates) {
        const templatesContainer = document.getElementById('templatesContainer');
        if (!templatesContainer) return;
        
        if (templates.length === 0) {
            templatesContainer.innerHTML = '<p class="no-templates">No templates uploaded yet.</p>';
            return;
        }
        
        const templatesList = templates.map(template => `
            <div class="template-item">
                <div class="template-info">
                    <strong>${escapeHtml(template.name)}</strong>
                    <div class="template-details">
                        ${template.description ? escapeHtml(template.description) : 'No description'}
                    </div>
                    <div class="template-specs">
                        Video: ${escapeHtml(template.video_encoder)} | 
                        Audio: ${escapeHtml(template.audio_encoder)} | 
                        Container: ${escapeHtml(template.container)}
                    </div>
                </div>
                <div class="template-actions">
                    <button type="button" class="btn btn-secondary template-delete" 
                            data-template="${escapeHtml(template.name)}">Delete</button>
                </div>
            </div>
        `).join('');
        
        templatesContainer.innerHTML = templatesList;
        
        // Add delete event listeners
        templatesContainer.querySelectorAll('.template-delete').forEach(button => {
            button.addEventListener('click', (e) => {
                const templateName = e.target.dataset.template;
                deleteTemplate(templateName);
            });
        });
    }
    
    // Delete a template
    async function deleteTemplate(templateName) {
        if (!confirm(`Delete template "${templateName}"? This cannot be undone.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/templates/${encodeURIComponent(templateName)}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showAlert(`Template "${templateName}" deleted successfully`, 'success');
                await loadTemplates(); // Refresh templates list and preset dropdown
            } else {
                showAlert('Error deleting template: ' + data.error, 'error');
            }
        } catch (error) {
            showAlert('Error deleting template: ' + error.message, 'error');
        }
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Populate the preset dropdown with available templates
    function populatePresetDropdown(templates) {
        const presetSelect = document.getElementById('defaultPreset');
        const currentValue = presetSelect.value; // Preserve current selection
        
        // Clear existing options
        presetSelect.innerHTML = '<option value="">Select a preset...</option>';
        
        // Add built-in HandBrake presets
        const builtInPresets = [
            'Very Fast 1080p30',
            'Very Fast 720p30', 
            'Very Fast 480p30',
            'Fast 1080p30',
            'Fast 720p30',
            'Fast 480p30',
            'HQ 1080p30 Surround',
            'HQ 720p30 Surround',
            'Super HQ 1080p30 Surround'
        ];
        
        builtInPresets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset;
            option.textContent = preset + ' (Built-in)';
            presetSelect.appendChild(option);
        });
        
        // Add separator if we have custom templates
        if (templates && templates.length > 0) {
            const separator = document.createElement('option');
            separator.disabled = true;
            separator.textContent = '--- Custom Templates ---';
            presetSelect.appendChild(separator);
            
            // Add custom templates
            templates.forEach(template => {
                const option = document.createElement('option');
                option.value = template.name;
                option.textContent = template.name + ' (Custom)';
                presetSelect.appendChild(option);
            });
        }
        
        // Restore previous selection if it still exists
        if (currentValue) {
            setPresetSelection(currentValue);
        }
        
        console.log('Preset dropdown populated with', presetSelect.options.length - 1, 'options');
    }
    
    // Handle folder browser for output directory
    async function browseOutputDirectory() {
        try {
            const currentPath = document.getElementById('outputDirectory').value || '';
            
            // Create modal dialog for directory browser
            const modal = createDirectoryBrowserModal(currentPath);
            document.body.appendChild(modal);
            
        } catch (error) {
            showAlert('Error browsing directory: ' + error.message, 'error');
        }
    }
    
    // Create directory browser modal
    function createDirectoryBrowserModal(initialPath) {
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white;
            border-radius: 8px;
            width: 90%;
            max-width: 600px;
            max-height: 80%;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            overflow: hidden;
        `;
        
        dialog.innerHTML = `
            <div style="padding: 20px; border-bottom: 1px solid #eee; flex-shrink: 0;">
                <h3 style="margin: 0;">Select Output Directory</h3>
                <div id="currentPath" style="margin-top: 10px; font-family: monospace; background: #f5f5f5; padding: 8px; border-radius: 4px; word-break: break-all;"></div>
            </div>
            <div id="directoryList" style="
                flex: 1; 
                overflow-y: auto; 
                padding: 10px;
                min-height: 200px;
                scrollbar-width: thin;
                scrollbar-color: #ccc #f0f0f0;
            "></div>
            <div style="padding: 20px; border-top: 1px solid #eee; display: flex; gap: 10px; justify-content: flex-end; flex-shrink: 0;">
                <button id="selectCurrent" class="btn btn-primary">Select Current Directory</button>
                <button id="cancelBrowser" class="btn btn-secondary">Cancel</button>
            </div>
        `;
        
        modal.appendChild(dialog);
        
        let currentPath = initialPath;
        
        // Load directory contents
        async function loadDirectory(path) {
            try {
                const response = await fetch('/api/directory/browse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    currentPath = data.current_path; // Keep absolute path for internal use
                    const displayPath = data.current_display_path || data.current_path;
                    
                    const currentPathElement = modal.querySelector('#currentPath');
                    if (currentPathElement) {
                        currentPathElement.textContent = displayPath;
                    }
                    
                    const listContainer = modal.querySelector('#directoryList');
                    if (listContainer) {
                        listContainer.innerHTML = '';
                        
                        // Always add parent directory option (unless we're at movies root)
                        if (data.parent_path && data.parent_path !== data.current_path) {
                            const parentItem = document.createElement('div');
                            parentItem.className = 'directory-item parent-directory';
                            parentItem.style.cssText = `
                                padding: 12px;
                                border: 1px solid #ddd;
                                border-radius: 4px;
                                margin-bottom: 5px;
                                cursor: pointer;
                                background: #f9f9f9;
                                font-weight: 500;
                                transition: all 0.2s ease;
                            `;
                            
                            const parentDisplayPath = data.parent_display_path || '..';
                            parentItem.innerHTML = `📁 .. (${parentDisplayPath})`;
                            
                            // Add hover effects
                            parentItem.onmouseenter = () => {
                                parentItem.style.background = '#e9e9e9';
                                parentItem.style.borderColor = '#bbb';
                            };
                            parentItem.onmouseleave = () => {
                                parentItem.style.background = '#f9f9f9';
                                parentItem.style.borderColor = '#ddd';
                            };
                            
                            parentItem.onclick = () => loadDirectory(data.parent_path);
                            listContainer.appendChild(parentItem);
                        }
                        
                        // Add directories
                        data.directories.forEach(dir => {
                            const dirItem = document.createElement('div');
                            dirItem.className = 'directory-item';
                            const isWritable = dir.is_writable;
                            const bgColor = isWritable ? '#fff' : '#f0f0f0';
                            const hoverColor = isWritable ? '#f0f8ff' : '#e8e8e8';
                            
                            dirItem.style.cssText = `
                                padding: 12px;
                                border: 1px solid #ddd;
                                border-radius: 4px;
                                margin-bottom: 5px;
                                cursor: pointer;
                                background: ${bgColor};
                                transition: all 0.2s ease;
                                ${!isWritable ? 'opacity: 0.7;' : ''}
                            `;
                            dirItem.innerHTML = `📁 ${dir.name} ${isWritable ? '' : '<span style="color: #666; font-size: 0.9em;">(Read-only)</span>'}`;
                            
                            // Add hover effects
                            dirItem.onmouseenter = () => {
                                dirItem.style.background = hoverColor;
                                dirItem.style.borderColor = '#bbb';
                                dirItem.style.transform = 'translateY(-1px)';
                                dirItem.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                            };
                            dirItem.onmouseleave = () => {
                                dirItem.style.background = bgColor;
                                dirItem.style.borderColor = '#ddd';
                                dirItem.style.transform = 'translateY(0)';
                                dirItem.style.boxShadow = 'none';
                            };
                            
                            dirItem.onclick = () => loadDirectory(dir.path);
                            listContainer.appendChild(dirItem);
                        });
                        
                        // Show message if no subdirectories (but parent is still available)
                        if (data.directories.length === 0) {
                            const noSubdirsMsg = document.createElement('div');
                            noSubdirsMsg.style.cssText = `
                                padding: 20px;
                                text-align: center;
                                color: #666;
                                font-style: italic;
                                border: 1px dashed #ddd;
                                border-radius: 4px;
                                background: #fafafa;
                            `;
                            noSubdirsMsg.textContent = 'No subdirectories found';
                            listContainer.appendChild(noSubdirsMsg);
                        }
                        
                        // Ensure minimum height and always show scrollbar
                        listContainer.style.cssText += `
                            min-height: 200px;
                            overflow-y: scroll;
                            scrollbar-width: thin;
                            scrollbar-color: #ccc #f0f0f0;
                        `;
                        
                        // Add webkit scrollbar styles for better cross-browser support
                        const style = document.createElement('style');
                        style.textContent = `
                            #directoryList::-webkit-scrollbar {
                                width: 8px;
                            }
                            #directoryList::-webkit-scrollbar-track {
                                background: #f0f0f0;
                                border-radius: 4px;
                            }
                            #directoryList::-webkit-scrollbar-thumb {
                                background: #ccc;
                                border-radius: 4px;
                            }
                            #directoryList::-webkit-scrollbar-thumb:hover {
                                background: #999;
                            }
                        `;
                        if (!document.getElementById('directoryBrowserStyles')) {
                            style.id = 'directoryBrowserStyles';
                            document.head.appendChild(style);
                        }
                    }
                } else {
                    showAlert('Error loading directory: ' + data.error, 'error');
                }
            } catch (error) {
                showAlert('Error loading directory: ' + error.message, 'error');
            }
        }
        
        // Set up event handlers after modal is added to DOM
        setTimeout(() => {
            const selectButton = modal.querySelector('#selectCurrent');
            const cancelButton = modal.querySelector('#cancelBrowser');
            const directoryList = modal.querySelector('#directoryList');
            
            // Prevent scroll events from passing through to background
            modal.addEventListener('wheel', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                // If the scroll is over the directory list, handle it there
                if (directoryList && directoryList.contains(e.target)) {
                    directoryList.scrollTop += e.deltaY;
                }
            }, { passive: false });
            
            // Prevent touch scroll events from passing through
            modal.addEventListener('touchmove', (e) => {
                if (!directoryList || !directoryList.contains(e.target)) {
                    e.preventDefault();
                }
            }, { passive: false });
            
            // Prevent keyboard scroll events from passing through
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowUp' || e.key === 'ArrowDown' || 
                    e.key === 'PageUp' || e.key === 'PageDown' ||
                    e.key === 'Home' || e.key === 'End') {
                    
                    if (directoryList && directoryList.contains(document.activeElement)) {
                        // Let the directory list handle it
                        return;
                    } else {
                        // Prevent background scrolling
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }
                
                // Close modal on Escape
                if (e.key === 'Escape') {
                    modal.remove();
                }
            });
            
            // Focus the directory list for keyboard navigation
            if (directoryList) {
                directoryList.setAttribute('tabindex', '0');
                directoryList.focus();
            }
            
            if (selectButton) {
                selectButton.onclick = () => {
                    // Convert absolute path to relative path for storage
                    let pathToSave = currentPath;
                    if (currentPath.startsWith('/movies')) {
                        pathToSave = currentPath.substring('/movies'.length);
                        if (!pathToSave.startsWith('/') && pathToSave !== '') {
                            pathToSave = '/' + pathToSave;
                        }
                        if (pathToSave === '') {
                            pathToSave = '/';
                        }
                    }
                    
                    document.getElementById('outputDirectory').value = pathToSave;
                    modal.remove();
                };
            }
            
            if (cancelButton) {
                cancelButton.onclick = () => {
                    modal.remove();
                };
            }
            
            modal.onclick = (e) => {
                if (e.target === modal) {
                    modal.remove();
                }
            };
            
            // Load initial directory
            loadDirectory(initialPath);
        }, 0);
        
        return modal;
    }
    
    // Populate form with settings
    function populateForm(settings) {
        console.log('Populating form with settings:', settings);
        
        document.getElementById('maxConcurrentEncodes').value = settings.max_concurrent_encodes || 2;
        document.getElementById('progressUpdateInterval').value = settings.progress_update_interval || 1;
        document.getElementById('outputDirectory').value = settings.output_directory || '';
        
        // Handle preset dropdown
        const presetSelect = document.getElementById('defaultPreset');
        const presetValue = settings.default_preset || 'Fast 1080p30';
        console.log(`Trying to set preset to: ${presetValue}`);
        console.log(`Available options:`, Array.from(presetSelect.options).map(opt => opt.value));
        
        // Check if the preset exists in the dropdown
        const optionExists = Array.from(presetSelect.options).some(option => option.value === presetValue);
        if (optionExists) {
            presetSelect.value = presetValue;
            console.log(`Successfully set preset to: ${presetValue}`);
        } else {
            console.warn(`Preset "${presetValue}" not found in dropdown options`);
            // Don't show alert here since populatePresetDropdown will handle it
        }
        
        document.getElementById('testingMode').checked = settings.testing_mode || false;
        document.getElementById('testDurationSeconds').value = settings.test_duration_seconds || 60;
        
        // Display options
        document.getElementById('statsForNerds').checked = settings.stats_for_nerds || false;
        
        // Notification settings
        const notifications = settings.notification_settings || {};
        console.log('Loading notification settings:', notifications);
        
        document.getElementById('notifyCompletion').checked = notifications.on_completion !== false;
        document.getElementById('notifyFailure').checked = notifications.on_failure !== false;
        document.getElementById('notifyQueueEmpty').checked = notifications.on_queue_empty !== false;
        
        console.log('Set notification checkboxes:', {
            completion: document.getElementById('notifyCompletion').checked,
            failure: document.getElementById('notifyFailure').checked,
            queueEmpty: document.getElementById('notifyQueueEmpty').checked
        });
        
        // Update testing mode visibility
        toggleTestingMode();
    }
    
    // Save settings
    async function saveSettings(formData) {
        try {
            console.log('Saving settings:', formData);
            
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                showAlert('Settings saved successfully!', 'success');
                currentSettings = data.settings;
                console.log('Settings saved, server returned:', data.settings);
            } else {
                showAlert('Error saving settings: ' + data.error, 'error');
            }
        } catch (error) {
            showAlert('Error saving settings: ' + error.message, 'error');
        }
    }
    
    // Show alert message (fixed to top of screen)
    function showAlert(message, type) {
        // Create alert container if it doesn't exist
        let alertContainer = document.getElementById('fixedAlertContainer');
        if (!alertContainer) {
            alertContainer = document.createElement('div');
            alertContainer.id = 'fixedAlertContainer';
            alertContainer.style.cssText = `
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 9999;
                width: 90%;
                max-width: 600px;
                pointer-events: none;
            `;
            document.body.appendChild(alertContainer);
        }
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.style.cssText = `
            margin-bottom: 10px;
            padding: 12px 20px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-weight: 500;
            pointer-events: auto;
            animation: slideInFromTop 0.3s ease-out;
        `;
        
        // Set colors based on type
        if (type === 'success') {
            alertDiv.style.backgroundColor = '#d4edda';
            alertDiv.style.color = '#155724';
            alertDiv.style.border = '1px solid #c3e6cb';
        } else if (type === 'error') {
            alertDiv.style.backgroundColor = '#f8d7da';
            alertDiv.style.color = '#721c24';
            alertDiv.style.border = '1px solid #f5c6cb';
        } else if (type === 'warning') {
            alertDiv.style.backgroundColor = '#fff3cd';
            alertDiv.style.color = '#856404';
            alertDiv.style.border = '1px solid #ffeaa7';
        }
        
        alertDiv.textContent = message;
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.style.cssText = `
            float: right;
            background: none;
            border: none;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
            margin-left: 10px;
            opacity: 0.7;
        `;
        closeBtn.onclick = () => alertDiv.remove();
        alertDiv.appendChild(closeBtn);
        
        // Add animation keyframes if not already added
        if (!document.getElementById('alertAnimations')) {
            const style = document.createElement('style');
            style.id = 'alertAnimations';
            style.textContent = `
                @keyframes slideInFromTop {
                    from {
                        transform: translateY(-100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateY(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        alertContainer.appendChild(alertDiv);
        
        // Auto-hide success messages
        if (type === 'success') {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.remove();
                }
            }, 5000);
        }
        
        // Auto-hide error messages after longer time
        if (type === 'error' || type === 'warning') {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.remove();
                }
            }, 10000);
        }
    }
    
    // Toggle testing mode visibility
    function toggleTestingMode() {
        const testingMode = document.getElementById('testingMode').checked;
        const testDurationGroup = document.getElementById('testDurationGroup');
        testDurationGroup.style.display = testingMode ? 'block' : 'none';
    }
    
    // Handle form submission
    function handleFormSubmit(e) {
        e.preventDefault();
        
        const form = e.target;
        const settings = {};
        
        // Handle regular form fields
        const formData = new FormData(form);
        for (const [key, value] of formData.entries()) {
            if (key.includes('.')) {
                // Handle nested properties like notification_settings.on_completion
                const [parent, child] = key.split('.');
                if (!settings[parent]) settings[parent] = {};
                settings[parent][child] = value === 'on';
            } else if (form.elements[key].type === 'checkbox') {
                settings[key] = value === 'on';
            } else if (form.elements[key].type === 'number') {
                settings[key] = parseInt(value);
            } else {
                settings[key] = value;
            }
        }
        
        // Handle unchecked checkboxes (they don't appear in FormData)
        const allCheckboxes = form.querySelectorAll('input[type="checkbox"]');
        allCheckboxes.forEach(checkbox => {
            const name = checkbox.name;
            if (name.includes('.')) {
                const [parent, child] = name.split('.');
                if (!settings[parent]) settings[parent] = {};
                if (!(child in settings[parent])) {
                    settings[parent][child] = false;
                }
            } else {
                if (!(name in settings)) {
                    settings[name] = false;
                }
            }
        });
        
        console.log('Form submission - collected settings:', settings);
        saveSettings(settings);
    }
    
    // Handle reset to defaults
    function handleResetSettings() {
        if (confirm('Reset all settings to defaults? This cannot be undone.')) {
            const defaultSettings = {
                max_concurrent_encodes: 2,
                testing_mode: false,
                test_duration_seconds: 60,
                output_directory: '',
                default_preset: 'Fast 1080p30',
                progress_update_interval: 1,
                stats_for_nerds: false,
                notification_settings: {
                    on_completion: true,
                    on_failure: true,
                    on_queue_empty: true
                }
            };
            
            populateForm(defaultSettings);
        }
    }
    
    // Handle template file upload
    async function handleTemplateFile(file) {
        if (!file.name.endsWith('.json')) {
            showAlert('Please select a .json file', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('template', file);
        
        try {
            const response = await fetch('/api/templates/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Handle successful upload
                showAlert(data.message, 'success');
                
                // Show additional details if there were partial failures
                if (data.failed_templates && data.failed_templates.length > 0) {
                    console.warn('Some templates failed:', data.failed_templates);
                    // Show detailed errors for partial failures
                    if (data.detailed_errors) {
                        const detailsMsg = 'Failed templates: ' + data.detailed_errors.join('; ');
                        showAlert(detailsMsg, 'warning');
                    }
                }
                
                // Show details if multiple templates were processed
                if (data.saved_templates && data.saved_templates.length > 1) {
                    console.log('Uploaded templates:', data.saved_templates);
                }
                
                // Refresh templates list
                loadTemplates(); // This will also refresh the preset dropdown
                
            } else {
                // Handle error - show the specific error message from the server
                let errorMessage = 'Upload failed: ' + data.error;
                
                // Add additional context for common errors
                if (data.error.includes('Permission denied')) {
                    errorMessage += '\n\nTip: Check that the settings directory is writable by the container (UID 1001).';
                }
                
                showAlert(errorMessage, 'error');
                
                // Log detailed error information for debugging
                if (data.failed_templates) {
                    console.error('Failed templates:', data.failed_templates);
                }
            }
        } catch (error) {
            // Handle network or other errors
            showAlert('Error uploading template: ' + error.message, 'error');
        }
    }
    
    // Initialize event listeners
    function initializeEventListeners() {
        // Form submission
        document.getElementById('settingsForm').addEventListener('submit', handleFormSubmit);
        
        // Testing mode toggle
        document.getElementById('testingMode').addEventListener('change', toggleTestingMode);
        
        // Reset to defaults
        document.getElementById('resetSettings').addEventListener('click', handleResetSettings);
        
        // Output directory browser
        document.getElementById('browseOutputDir').addEventListener('click', browseOutputDirectory);
        
        // Template upload
        const templateUpload = document.getElementById('templateUpload');
        const templateFile = document.getElementById('templateFile');
        
        templateUpload.addEventListener('click', () => {
            templateFile.click();
        });
        
        templateUpload.addEventListener('dragover', (e) => {
            e.preventDefault();
            templateUpload.classList.add('dragover');
        });
        
        templateUpload.addEventListener('dragleave', () => {
            templateUpload.classList.remove('dragover');
        });
        
        templateUpload.addEventListener('drop', (e) => {
            e.preventDefault();
            templateUpload.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleTemplateFile(files[0]);
            }
        });
        
        templateFile.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleTemplateFile(e.target.files[0]);
            }
        });
    }
    
    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        initializeEventListeners();
        loadSettings();
    });
})();
