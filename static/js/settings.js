// Settings page JavaScript
(function() {
    'use strict';
    
    // Settings management
    let currentSettings = {};
    
    // Load current settings and templates
    async function loadSettings() {
        try {
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
        
        // Load available templates
        await loadTemplates();
    }
    
    // Load available templates
    async function loadTemplates() {
        try {
            const response = await fetch('/api/templates');
            const data = await response.json();
            
            if (data.success) {
                updateTemplatesList(data.templates);
            } else {
                console.error('Error loading templates:', data.error);
            }
        } catch (error) {
            console.error('Error loading templates:', error.message);
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
                await loadTemplates(); // Refresh templates list
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
    
    // Populate form with settings
    function populateForm(settings) {
        document.getElementById('maxConcurrentEncodes').value = settings.max_concurrent_encodes || 2;
        document.getElementById('progressUpdateInterval').value = settings.progress_update_interval || 1;
        document.getElementById('outputDirectory').value = settings.output_directory || '';
        document.getElementById('defaultPreset').value = settings.default_preset || 'Fast 1080p30';
        document.getElementById('testingMode').checked = settings.testing_mode || false;
        document.getElementById('testDurationSeconds').value = settings.test_duration_seconds || 60;
        
        // Notification settings
        const notifications = settings.notification_settings || {};
        document.getElementById('notifyCompletion').checked = notifications.on_completion !== false;
        document.getElementById('notifyFailure').checked = notifications.on_failure !== false;
        document.getElementById('notifyQueueEmpty').checked = notifications.on_queue_empty !== false;
        
        // Update testing mode visibility
        toggleTestingMode();
    }
    
    // Save settings
    async function saveSettings(formData) {
        try {
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
            } else {
                showAlert('Error saving settings: ' + data.error, 'error');
            }
        } catch (error) {
            showAlert('Error saving settings: ' + error.message, 'error');
        }
    }
    
    // Show alert message
    function showAlert(message, type) {
        const alertContainer = document.getElementById('alertContainer');
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        alertContainer.innerHTML = '';
        alertContainer.appendChild(alertDiv);
        
        // Auto-hide success messages
        if (type === 'success') {
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
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
        
        const formData = new FormData(e.target);
        const settings = {};
        
        // Convert form data to settings object
        for (const [key, value] of formData.entries()) {
            if (key.includes('.')) {
                // Handle nested properties like notification_settings.on_completion
                const [parent, child] = key.split('.');
                if (!settings[parent]) settings[parent] = {};
                settings[parent][child] = value === 'on';
            } else if (e.target.elements[key].type === 'checkbox') {
                settings[key] = value === 'on';
            } else if (e.target.elements[key].type === 'number') {
                settings[key] = parseInt(value);
            } else {
                settings[key] = value;
            }
        }
        
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
                showAlert('Template uploaded successfully!', 'success');
                document.getElementById('templateName').textContent = file.name;
                document.getElementById('currentTemplate').style.display = 'block';
            } else {
                showAlert('Error uploading template: ' + data.error, 'error');
            }
        } catch (error) {
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
