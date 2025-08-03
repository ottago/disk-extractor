"""
Unit tests for language mapper utilities
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.language_mapper import LanguageMapper


class TestLanguageMapper(unittest.TestCase):
    """Test language code mapping functionality"""
    
    def test_common_language_codes(self):
        """Test common language codes are mapped correctly"""
        test_cases = [
            ('eng', 'English'),
            ('spa', 'Spanish'),
            ('es', 'Spanish'),
            ('fre', 'French'),
            ('fra', 'French'),
            ('fr', 'French'),
            ('ger', 'German'),
            ('deu', 'German'),
            ('de', 'German'),
            ('ita', 'Italian'),
            ('it', 'Italian'),
            ('jpn', 'Japanese'),
            ('ja', 'Japanese'),
            ('chi', 'Chinese'),
            ('zho', 'Chinese'),
            ('zh', 'Chinese'),
            ('rus', 'Russian'),
            ('ru', 'Russian')
        ]
        
        for code, expected_name in test_cases:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, expected_name)
    
    def test_case_insensitive(self):
        """Test language code mapping is case insensitive"""
        test_cases = [
            ('ENG', 'English'),
            ('Eng', 'English'),
            ('SPA', 'Spanish'),
            ('FRA', 'French')
        ]
        
        for code, expected_name in test_cases:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, expected_name)
    
    def test_unknown_language_codes(self):
        """Test unknown language codes return uppercase version"""
        unknown_codes = ['xyz', 'abc', 'unknown']
        
        for code in unknown_codes:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, code.upper())
    
    def test_empty_language_code(self):
        """Test empty language code returns 'Unknown'"""
        test_cases = ['', None]
        
        for code in test_cases:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, 'Unknown')
    
    def test_is_english_detection(self):
        """Test English language detection"""
        english_codes = ['eng', 'en', 'ENG', 'EN', 'Eng']
        
        for code in english_codes:
            with self.subTest(code=code):
                result = LanguageMapper.is_english(code)
                self.assertTrue(result)
    
    def test_is_not_english_detection(self):
        """Test non-English language detection"""
        non_english_codes = ['spa', 'fr', 'de', 'it', 'ja', 'zh', '']
        
        for code in non_english_codes:
            with self.subTest(code=code):
                result = LanguageMapper.is_english(code)
                self.assertFalse(result)
    
    def test_get_all_languages(self):
        """Test getting all language mappings"""
        all_languages = LanguageMapper.get_all_languages()
        
        # Check it's a dictionary
        self.assertIsInstance(all_languages, dict)
        
        # Check it contains expected entries
        self.assertIn('eng', all_languages)
        self.assertEqual(all_languages['eng'], 'English')
        
        # Check it's a copy (not the original)
        all_languages['test'] = 'Test'
        original = LanguageMapper.get_all_languages()
        self.assertNotIn('test', original)
    
    def test_language_map_consistency(self):
        """Test language map has consistent structure"""
        language_map = LanguageMapper.LANGUAGE_MAP
        
        # Check all values are strings
        for code, name in language_map.items():
            with self.subTest(code=code, name=name):
                self.assertIsInstance(code, str)
                self.assertIsInstance(name, str)
                self.assertTrue(len(code) > 0)
                self.assertTrue(len(name) > 0)
    
    def test_multiple_codes_same_language(self):
        """Test multiple codes mapping to same language work correctly"""
        # Test Spanish codes
        spanish_codes = ['spa', 'es']
        for code in spanish_codes:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, 'Spanish')
        
        # Test French codes
        french_codes = ['fre', 'fra', 'fr']
        for code in french_codes:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, 'French')
        
        # Test German codes
        german_codes = ['ger', 'deu', 'de']
        for code in german_codes:
            with self.subTest(code=code):
                result = LanguageMapper.get_language_name(code)
                self.assertEqual(result, 'German')


if __name__ == '__main__':
    unittest.main()
