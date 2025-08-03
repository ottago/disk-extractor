"""
Language mapping utilities for Disk Extractor

Maps language codes to human-readable names.
"""

from typing import Dict


class LanguageMapper:
    """Maps language codes to human-readable names"""
    
    LANGUAGE_MAP: Dict[str, str] = {
        'eng': 'English',
        'spa': 'Spanish', 'es': 'Spanish',
        'fre': 'French', 'fra': 'French', 'fr': 'French',
        'ger': 'German', 'deu': 'German', 'de': 'German',
        'ita': 'Italian', 'it': 'Italian',
        'por': 'Portuguese', 'pt': 'Portuguese',
        'jpn': 'Japanese', 'ja': 'Japanese',
        'kor': 'Korean', 'ko': 'Korean',
        'chi': 'Chinese', 'zho': 'Chinese', 'zh': 'Chinese',
        'rus': 'Russian', 'ru': 'Russian',
        'ara': 'Arabic', 'ar': 'Arabic',
        'hin': 'Hindi', 'hi': 'Hindi',
        'und': 'Unknown'
    }
    
    @classmethod
    def get_language_name(cls, lang_code: str) -> str:
        """
        Get human-readable language name from code
        
        Args:
            lang_code: Language code
            
        Returns:
            Human-readable language name
        """
        if not lang_code:
            return 'Unknown'
        return cls.LANGUAGE_MAP.get(lang_code.lower(), lang_code.upper())
    
    @classmethod
    def is_english(cls, lang_code: str) -> bool:
        """
        Check if language code represents English
        
        Args:
            lang_code: Language code
            
        Returns:
            True if English
        """
        if not lang_code:
            return False
        return lang_code.lower() in ['eng', 'en']
    
    @classmethod
    def get_all_languages(cls) -> Dict[str, str]:
        """
        Get all supported language mappings
        
        Returns:
            All language code mappings
        """
        return cls.LANGUAGE_MAP.copy()
