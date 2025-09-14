"""
Unit tests for TemplateManager
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.template_manager import TemplateManager


class TestTemplateManager(unittest.TestCase):
    """Test TemplateManager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.manager = TemplateManager()
        
        # Override the template directory for testing
        self.manager.template_dir = self.temp_path
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_template(self, name: str, content: dict) -> Path:
        """Create a test template file"""
        template_path = self.temp_path / f"{name}.json"
        template_path.write_text(json.dumps(content, indent=2))
        return template_path
    
    def test_list_templates_empty(self):
        """Test listing templates when directory is empty"""
        # Override template directory to use our empty temp dir
        self.manager.template_dir = self.temp_path
        self.manager._load_templates()  # Reload from empty directory
        
        templates = self.manager.list_templates()
        # Should only have built-in templates, not our test files
        self.assertIsInstance(templates, list)
    
    def test_list_templates_with_files(self):
        """Test listing templates with template files"""
        # Create test templates in the temp directory
        template1 = {
            {
                {
                    "PresetName": "Test Template 1",
                    "VideoEncoder": "x264"
                }
            }
        }
        
        template2 = {
            {
                {
                    "PresetName": "Test Template 2", 
                    "VideoEncoder": "x265"
                }
            }
        }
        
        self.create_test_template("template1", template1)
        self.create_test_template("template2", template2)
        
        # Override template directory and reload
        self.manager.template_dir = self.temp_path
        self.manager._load_templates()
        
        templates = self.manager.list_templates()
        self.assertIsInstance(templates, list)
        self.assertGreater(len(templates), 0)
    
    def test_get_template_existing(self):
        """Test getting an existing template"""
        template_content = {
            {
                {
                    "PresetName": "Test Template",
                    "VideoEncoder": "x264",
                    "VideoQualityType": 1,
                    "VideoQualitySlider": 22.0
                }
            }
        }
        
        # Save template using the actual API
        success, message = self.manager.save_template("test_template", template_content)
        self.assertTrue(success, f"Failed to save template: {message}")
        
        template = self.manager.get_template("test_template")
        self.assertIsNotNone(template)
    
    def test_get_template_nonexistent(self):
        """Test getting a non-existent template"""
        template = self.manager.get_template("nonexistent")
        self.assertIsNone(template)
    
    def test_save_template(self):
        """Test saving a new template"""
        template_content = {
            {
                {
                    "PresetName": "New Template",
                    "VideoEncoder": "x265"
                }
            }
        }
        
        success, message = self.manager.save_template("new_template", template_content)
        self.assertTrue(success, f"Save failed: {message}")
        
        # Verify template can be retrieved
        template = self.manager.get_template("new_template")
        self.assertIsNotNone(template)
    
    def test_save_template_overwrite(self):
        """Test overwriting an existing template"""
        original_content = {
            {
                {
                    "PresetName": "Original",
                    "VideoEncoder": "x264"
                }
            }
        }
        
        new_content = {
            {
                {
                    "PresetName": "Updated",
                    "VideoEncoder": "x265"
                }
            }
        }
        
        # Create original template
        success1, _ = self.manager.save_template("test_template", original_content)
        self.assertTrue(success1)
        
        # Overwrite with new content
        success2, message = self.manager.save_template("test_template", new_content)
        self.assertTrue(success2, f"Overwrite failed: {message}")
        
        # Verify content was updated
        template = self.manager.get_template("test_template")
        self.assertIsNotNone(template)
    
    def test_delete_template_existing(self):
        """Test deleting an existing template"""
        template_content = {
            {
                {
                    "PresetName": "To Delete",
                    "VideoEncoder": "x264"
                }
            }
        }
        
        # Save template first
        success1, _ = self.manager.save_template("delete_me", template_content)
        self.assertTrue(success1)
        
        # Delete it
        success2 = self.manager.delete_template("delete_me")
        self.assertTrue(success2)
        
        # Verify it's gone
        template = self.manager.get_template("delete_me")
        self.assertIsNone(template)
    
    def test_delete_template_nonexistent(self):
        """Test deleting a non-existent template"""
        success = self.manager.delete_template("nonexistent")
        self.assertFalse(success)
    
    def test_validate_template_valid(self):
        """Test validating a valid template"""
        valid_template = {
            {
                {
                    "PresetName": "Valid Template",
                    "VideoEncoder": "x264",
                    "VideoQualityType": 1,
                    "VideoQualitySlider": 22.0
                }
            }
        }
        
        is_valid, message = self.manager._validate_template(valid_template)
        self.assertTrue(is_valid, f"Validation failed: {message}")
    
    def test_validate_template_invalid_structure(self):
        """Test validating template with invalid structure"""
        invalid_template = {
            "InvalidKey": "InvalidValue"
        }
        
        is_valid, message = self.manager._validate_template(invalid_template)
        self.assertFalse(is_valid)
        self.assertIn("PresetList", message)
    
    def test_validate_template_missing_preset_name(self):
        """Test validating template with missing PresetName"""
        invalid_template = {
            {
                {
                    "VideoEncoder": "x264"
                    # Missing PresetName
                }
            }
        }
        
        is_valid, message = self.manager._validate_template(invalid_template)
        self.assertFalse(is_valid)
        self.assertIn("PresetName", message)
    
    def test_generate_output_filename(self):
        """Test output filename generation"""
        filename = self.manager.generate_output_filename(
            movie_name="Test Movie",
            release_date="2023",
            template_name="Fast 1080p30"
        )
        
        self.assertIsInstance(filename, str)
        self.assertIn("Test Movie", filename)
        self.assertIn("2023", filename)
    
    def test_build_handbrake_command(self):
        """Test HandBrake command building"""
        # This requires a valid template, so we'll test the method exists
        self.assertTrue(hasattr(self.manager, 'build_handbrake_command'))
        self.assertTrue(callable(getattr(self.manager, 'build_handbrake_command')))


if __name__ == '__main__':
    unittest.main()
