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
        templates = self.manager.list_templates()
        self.assertEqual(len(templates), 0)
    
    def test_list_templates_with_files(self):
        """Test listing templates with template files"""
        # Create test templates
        template1 = {
            "PresetList": [
                {
                    "PresetName": "Test Template 1",
                    "VideoEncoder": "x264"
                }
            ]
        }
        
        template2 = {
            "PresetList": [
                {
                    "PresetName": "Test Template 2",
                    "VideoEncoder": "x265"
                }
            ]
        }
        
        self.create_test_template("template1", template1)
        self.create_test_template("template2", template2)
        
        templates = self.manager.list_templates()
        self.assertEqual(len(templates), 2)
        
        template_names = [t['name'] for t in templates]
        self.assertIn("template1", template_names)
        self.assertIn("template2", template_names)
    
    def test_get_template_existing(self):
        """Test getting an existing template"""
        template_content = {
            "PresetList": [
                {
                    "PresetName": "Test Template",
                    "VideoEncoder": "x264",
                    "VideoQualityType": 1,
                    "VideoQualitySlider": 22.0
                }
            ]
        }
        
        self.create_test_template("test_template", template_content)
        
        template = self.manager.get_template("test_template")
        
        self.assertIsNotNone(template)
        self.assertEqual(template['name'], "test_template")
        self.assertIn('content', template)
        self.assertIn('PresetList', template['content'])
    
    def test_get_template_nonexistent(self):
        """Test getting a non-existent template"""
        template = self.manager.get_template("nonexistent")
        self.assertIsNone(template)
    
    def test_save_template(self):
        """Test saving a new template"""
        template_content = {
            "PresetList": [
                {
                    "PresetName": "New Template",
                    "VideoEncoder": "x265"
                }
            ]
        }
        
        success = self.manager.save_template("new_template", template_content)
        self.assertTrue(success)
        
        # Verify file was created
        template_file = self.temp_path / "new_template.json"
        self.assertTrue(template_file.exists())
        
        # Verify content
        saved_content = json.loads(template_file.read_text())
        self.assertEqual(saved_content, template_content)
    
    def test_save_template_overwrite(self):
        """Test overwriting an existing template"""
        original_content = {
            "PresetList": [
                {
                    "PresetName": "Original",
                    "VideoEncoder": "x264"
                }
            ]
        }
        
        new_content = {
            "PresetList": [
                {
                    "PresetName": "Updated",
                    "VideoEncoder": "x265"
                }
            ]
        }
        
        # Create original template
        self.create_test_template("test_template", original_content)
        
        # Overwrite with new content
        success = self.manager.save_template("test_template", new_content)
        self.assertTrue(success)
        
        # Verify content was updated
        template = self.manager.get_template("test_template")
        self.assertEqual(template['content'], new_content)
    
    def test_delete_template_existing(self):
        """Test deleting an existing template"""
        template_content = {
            "PresetList": [
                {
                    "PresetName": "To Delete",
                    "VideoEncoder": "x264"
                }
            ]
        }
        
        self.create_test_template("delete_me", template_content)
        
        success = self.manager.delete_template("delete_me")
        self.assertTrue(success)
        
        # Verify file was deleted
        template_file = self.temp_path / "delete_me.json"
        self.assertFalse(template_file.exists())
    
    def test_delete_template_nonexistent(self):
        """Test deleting a non-existent template"""
        success = self.manager.delete_template("nonexistent")
        self.assertFalse(success)
    
    def test_validate_template_valid(self):
        """Test validating a valid template"""
        valid_template = {
            "PresetList": [
                {
                    "PresetName": "Valid Template",
                    "VideoEncoder": "x264",
                    "VideoQualityType": 1,
                    "VideoQualitySlider": 22.0
                }
            ]
        }
        
        is_valid, errors = self.manager.validate_template(valid_template)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_template_invalid_structure(self):
        """Test validating template with invalid structure"""
        invalid_template = {
            "InvalidKey": "InvalidValue"
        }
        
        is_valid, errors = self.manager.validate_template(invalid_template)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_validate_template_missing_preset_name(self):
        """Test validating template with missing PresetName"""
        invalid_template = {
            "PresetList": [
                {
                    "VideoEncoder": "x264"
                    # Missing PresetName
                }
            ]
        }
        
        is_valid, errors = self.manager.validate_template(invalid_template)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_get_template_presets(self):
        """Test getting preset names from a template"""
        template_content = {
            "PresetList": [
                {
                    "PresetName": "Preset 1",
                    "VideoEncoder": "x264"
                },
                {
                    "PresetName": "Preset 2",
                    "VideoEncoder": "x265"
                }
            ]
        }
        
        self.create_test_template("multi_preset", template_content)
        
        presets = self.manager.get_template_presets("multi_preset")
        self.assertEqual(len(presets), 2)
        self.assertIn("Preset 1", presets)
        self.assertIn("Preset 2", presets)
    
    def test_get_template_presets_nonexistent(self):
        """Test getting presets from non-existent template"""
        presets = self.manager.get_template_presets("nonexistent")
        self.assertEqual(len(presets), 0)
    
    def test_template_exists(self):
        """Test checking if template exists"""
        template_content = {
            "PresetList": [
                {
                    "PresetName": "Test",
                    "VideoEncoder": "x264"
                }
            ]
        }
        
        self.create_test_template("exists_test", template_content)
        
        self.assertTrue(self.manager.template_exists("exists_test"))
        self.assertFalse(self.manager.template_exists("nonexistent"))
    
    def test_get_template_stats(self):
        """Test getting template statistics"""
        # Create multiple templates
        for i in range(3):
            template_content = {
                "PresetList": [
                    {
                        "PresetName": f"Template {i}",
                        "VideoEncoder": "x264"
                    }
                ]
            }
            self.create_test_template(f"template_{i}", template_content)
        
        stats = self.manager.get_template_stats()
        
        self.assertEqual(stats['total_templates'], 3)
        self.assertIn('template_directory', stats)
        self.assertEqual(stats['template_directory'], str(self.temp_path))


if __name__ == '__main__':
    unittest.main()
