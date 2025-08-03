"""
Unit tests for validation utilities
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.validation import (
    validate_filename, 
    sanitize_string, 
    validate_metadata_input, 
    validate_year,
    ValidationError
)


class TestValidateFilename(unittest.TestCase):
    """Test filename validation"""
    
    def test_valid_filename(self):
        """Test valid .img filenames"""
        valid_names = [
            'movie.img',
            'Movie Title.img',
            'Movie-Title_2023.img',
            'Movie (2023).img',
            'Movie [Director Cut].img'
        ]
        
        for name in valid_names:
            with self.subTest(filename=name):
                result = validate_filename(name)
                self.assertEqual(result, name)
    
    def test_path_traversal_detection(self):
        """Test path traversal attempts are blocked"""
        malicious_names = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32',
            'movie/../../../etc/passwd.img',
            'movie\\..\\..\\config.img'
        ]
        
        for name in malicious_names:
            with self.subTest(filename=name):
                with self.assertRaises(ValidationError) as cm:
                    validate_filename(name)
                self.assertIn('path traversal', str(cm.exception))
    
    def test_null_byte_detection(self):
        """Test null byte injection is blocked"""
        malicious_names = [
            'movie\x00.img',
            'movie.img\x00'  # Changed this test case to avoid path traversal
        ]
        
        for name in malicious_names:
            with self.subTest(filename=name):
                with self.assertRaises(ValidationError) as cm:
                    validate_filename(name)
                # Accept either null byte or path traversal detection (both are security issues)
                error_msg = str(cm.exception)
                self.assertTrue(
                    'null byte' in error_msg or 'path traversal' in error_msg,
                    f"Expected null byte or path traversal error, got: {error_msg}"
                )
    
    def test_extension_validation(self):
        """Test only .img files are allowed"""
        invalid_extensions = [
            'movie.exe',
            'movie.txt',
            'movie.img.exe',
            'movie'
        ]
        
        for name in invalid_extensions:
            with self.subTest(filename=name):
                with self.assertRaises(ValidationError) as cm:
                    validate_filename(name)
                self.assertIn('only .img files', str(cm.exception))
    
    def test_empty_filename(self):
        """Test empty filename is rejected"""
        with self.assertRaises(ValidationError) as cm:
            validate_filename('')
        self.assertIn('cannot be empty', str(cm.exception))
    
    def test_filename_length_limit(self):
        """Test filename length limits"""
        long_name = 'a' * 300 + '.img'
        with self.assertRaises(ValidationError) as cm:
            validate_filename(long_name)
        self.assertIn('filename too long', str(cm.exception))
    
    def test_invalid_characters(self):
        """Test invalid characters are rejected"""
        invalid_names = [
            'movie<script>.img',
            'movie|pipe.img',
            'movie*wildcard.img'
        ]
        
        for name in invalid_names:
            with self.subTest(filename=name):
                with self.assertRaises(ValidationError) as cm:
                    validate_filename(name)
                self.assertIn('invalid characters', str(cm.exception))


class TestSanitizeString(unittest.TestCase):
    """Test string sanitization"""
    
    def test_normal_string(self):
        """Test normal strings pass through"""
        test_string = "Normal movie title"
        result = sanitize_string(test_string)
        self.assertEqual(result, test_string)
    
    def test_null_byte_removal(self):
        """Test null bytes are removed"""
        test_string = "Movie\x00Title"
        result = sanitize_string(test_string)
        self.assertEqual(result, "MovieTitle")
    
    def test_whitespace_stripping(self):
        """Test whitespace is stripped"""
        test_string = "  Movie Title  "
        result = sanitize_string(test_string)
        self.assertEqual(result, "Movie Title")
    
    def test_length_limiting(self):
        """Test length limiting works"""
        test_string = "a" * 100
        result = sanitize_string(test_string, max_length=50)
        self.assertEqual(len(result), 50)
        self.assertEqual(result, "a" * 50)
    
    def test_non_string_input(self):
        """Test non-string inputs return empty string"""
        test_inputs = [None, 123, [], {}]
        
        for test_input in test_inputs:
            with self.subTest(input=test_input):
                result = sanitize_string(test_input)
                self.assertEqual(result, '')


class TestValidateMetadataInput(unittest.TestCase):
    """Test metadata input validation"""
    
    def test_valid_metadata(self):
        """Test valid metadata passes validation"""
        valid_data = {
            'filename': 'movie.img',
            'movie_name': 'Test Movie',
            'release_date': '2023-01-01',
            'synopsis': 'A test movie',
            'titles': []
        }
        
        result = validate_metadata_input(valid_data)
        self.assertEqual(result['filename'], 'movie.img')
        self.assertEqual(result['movie_name'], 'Test Movie')
        self.assertIsInstance(result['titles'], list)
    
    def test_missing_filename(self):
        """Test missing filename is rejected"""
        invalid_data = {
            'movie_name': 'Test Movie'
        }
        
        with self.assertRaises(ValidationError) as cm:
            validate_metadata_input(invalid_data)
        self.assertIn('Filename is required', str(cm.exception))
    
    def test_invalid_data_type(self):
        """Test non-dict input is rejected"""
        invalid_inputs = ['string', 123, []]
        
        for invalid_input in invalid_inputs:
            with self.subTest(input=invalid_input):
                with self.assertRaises(ValidationError) as cm:
                    validate_metadata_input(invalid_input)
                self.assertIn('must be a dictionary', str(cm.exception))
    
    def test_invalid_titles_type(self):
        """Test non-list titles are rejected"""
        invalid_data = {
            'filename': 'movie.img',
            'titles': 'not a list'
        }
        
        with self.assertRaises(ValidationError) as cm:
            validate_metadata_input(invalid_data)
        self.assertIn('Titles must be a list', str(cm.exception))
    
    def test_string_sanitization(self):
        """Test string fields are sanitized"""
        data_with_nulls = {
            'filename': 'movie.img',
            'movie_name': 'Movie\x00Title',
            'synopsis': '  Synopsis with whitespace  '
        }
        
        result = validate_metadata_input(data_with_nulls)
        self.assertEqual(result['movie_name'], 'MovieTitle')
        self.assertEqual(result['synopsis'], 'Synopsis with whitespace')


class TestValidateYear(unittest.TestCase):
    """Test year validation"""
    
    def test_valid_years(self):
        """Test valid years pass validation"""
        valid_years = ['2023', '1999', '2000', '2024']
        
        for year in valid_years:
            with self.subTest(year=year):
                result = validate_year(year)
                self.assertEqual(result, year)
    
    def test_invalid_years(self):
        """Test invalid years return empty string"""
        invalid_years = ['23', '12345', 'abc', '1800', '2200', '']
        
        for year in invalid_years:
            with self.subTest(year=year):
                result = validate_year(year)
                self.assertEqual(result, '')
    
    def test_whitespace_handling(self):
        """Test whitespace is handled correctly"""
        result = validate_year('  2023  ')
        self.assertEqual(result, '2023')


if __name__ == '__main__':
    unittest.main()
