"""
Unit Normalizer
Chuẩn hóa đơn vị kỹ thuật và ký hiệu đặc biệt trong tài liệu P&ID
"""
import re
from typing import Dict, List, Optional
from loguru import logger


class UnitNormalizer:
    """
    Normalizer để chuẩn hóa đơn vị đo lường và ký hiệu kỹ thuật
    """
    
    # Mapping for common unit variations
    UNIT_MAPPINGS = {
        # Temperature
        '℃': '°C',
        '℉': '°F',
        'deg C': '°C',
        'deg F': '°F',
        'degC': '°C',
        'degF': '°F',
        
        # Pressure
        'Bar a': 'bar(a)',
        'Bar g': 'bar(g)',
        'bar a': 'bar(a)',
        'bar g': 'bar(g)',
        'bara': 'bar(a)',
        'barg': 'bar(g)',
        'KPa': 'kPa',
        'Kpa': 'kPa',
        'MPa': 'MPa',
        'Mpa': 'MPa',
        'PSI': 'psi',
        'PSIG': 'psig',
        'PSIA': 'psia',
        
        # Flow rate
        'm /h': 'm³/h',
        'm3/h': 'm³/h',
        'm3/hr': 'm³/h',
        'M3/H': 'm³/h',
        'Nm /h': 'Nm³/h',
        'Nm3/h': 'Nm³/h',
        'kg/hr': 'kg/h',
        'KG/H': 'kg/h',
        't/hr': 't/h',
        'T/H': 't/h',
        
        # Volume
        'm ': 'm³',
        'm3': 'm³',
        'M3': 'm³',
        'cubic meter': 'm³',
        'cubic meters': 'm³',
        'liter': 'L',
        'litre': 'L',
        
        # Power
        'KW': 'kW',
        'Kw': 'kW',
        'MW': 'MW',
        'Mw': 'MW',
        'HP': 'hp',
        
        # Others
        'MM': 'mm',
        'CM': 'cm',
        'M': 'm',
        'KG': 'kg',
        'Kg': 'kg',
        'TON': 't',
        'TONS': 't',
        '%wt': 'wt%',
        '%vol': 'vol%',
    }
    
    # Patterns for superscript numbers
    SUPERSCRIPT_PATTERNS = [
        (r'm\s*2\b', 'm²'),
        (r'm\s*3\b', 'm³'),
        (r'cm\s*2\b', 'cm²'),
        (r'cm\s*3\b', 'cm³'),
        (r'mm\s*2\b', 'mm²'),
        (r'mm\s*3\b', 'mm³'),
        (r'ft\s*2\b', 'ft²'),
        (r'ft\s*3\b', 'ft³'),
    ]
    
    def __init__(self, 
                 normalize_case: bool = True,
                 fix_superscripts: bool = True,
                 standardize_separators: bool = True):
        """
        Initialize unit normalizer
        
        Args:
            normalize_case: Normalize unit case
            fix_superscripts: Fix separated superscripts
            standardize_separators: Standardize number-unit separators
        """
        self.normalize_case = normalize_case
        self.fix_superscripts = fix_superscripts
        self.standardize_separators = standardize_separators
    
    def normalize(self, text: str) -> str:
        """
        Normalize units in text
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized units
        """
        if not text:
            return text
        
        # Fix superscripts first
        if self.fix_superscripts:
            text = self._fix_superscripts(text)
        
        # Apply unit mappings
        text = self._apply_unit_mappings(text)
        
        # Fix number-unit spacing
        if self.standardize_separators:
            text = self._fix_number_unit_spacing(text)
        
        # Normalize special patterns
        text = self._normalize_special_patterns(text)
        
        return text
    
    def _fix_superscripts(self, text: str) -> str:
        """
        Fix separated superscript numbers
        
        Args:
            text: Input text
            
        Returns:
            Text with fixed superscripts
        """
        # Fix patterns like "m 3" or "m 2"
        for pattern, replacement in self.SUPERSCRIPT_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Fix separated superscripts with /
        text = re.sub(r'm\s*/h\b', 'm³/h', text)
        text = re.sub(r'Nm\s*/h\b', 'Nm³/h', text)
        text = re.sub(r'm\s*/s\b', 'm³/s', text)
        
        return text
    
    def _apply_unit_mappings(self, text: str) -> str:
        """
        Apply unit standardization mappings
        
        Args:
            text: Input text
            
        Returns:
            Text with standardized units
        """
        # Sort by length to avoid partial replacements
        sorted_mappings = sorted(self.UNIT_MAPPINGS.items(), 
                                key=lambda x: len(x[0]), 
                                reverse=True)
        
        for old_unit, new_unit in sorted_mappings:
            # Use word boundaries for whole unit matching
            pattern = r'\b' + re.escape(old_unit) + r'\b'
            text = re.sub(pattern, new_unit, text, flags=re.IGNORECASE if self.normalize_case else 0)
        
        return text
    
    def _fix_number_unit_spacing(self, text: str) -> str:
        """
        Fix spacing between numbers and units
        
        Args:
            text: Input text
            
        Returns:
            Text with fixed spacing
        """
        # Add space between number and unit if missing
        # Pattern: number directly followed by letter (unit)
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
        
        # Remove extra spaces
        text = re.sub(r'(\d)\s+([°℃℉])', r'\1\2', text)  # No space before degree symbols
        text = re.sub(r'(\d)\s{2,}([a-zA-Z])', r'\1 \2', text)  # Single space only
        
        return text
    
    def _normalize_special_patterns(self, text: str) -> str:
        """
        Normalize special technical patterns
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized patterns
        """
        # Normalize ranges
        text = re.sub(r'(\d+)\s*[-–—]\s*(\d+)\s*([a-zA-Z°])', r'\1-\2 \3', text)
        
        # Normalize ± symbol
        text = re.sub(r'(\d+)\s*[±]\s*(\d+)', r'\1±\2', text)
        
        # Fix multiplication symbol
        text = re.sub(r'(\d+)\s*[xX×]\s*(\d+)', r'\1×\2', text)
        
        # Normalize percentage
        text = re.sub(r'(\d+)\s*%', r'\1%', text)
        
        return text
    
    def extract_units(self, text: str) -> List[Dict[str, str]]:
        """
        Extract all units from text
        
        Args:
            text: Input text
            
        Returns:
            List of found units with positions
        """
        units_found = []
        
        # Common unit patterns
        unit_patterns = [
            r'\b\d+\.?\d*\s*[°℃℉]C?\b',  # Temperature
            r'\b\d+\.?\d*\s*bar\s*\(?[ag]\)?\b',  # Pressure
            r'\b\d+\.?\d*\s*[kKmM]?Pa\b',  # Pressure
            r'\b\d+\.?\d*\s*psi[ag]?\b',  # Pressure
            r'\b\d+\.?\d*\s*m[²³]?/[hs]\b',  # Flow rate
            r'\b\d+\.?\d*\s*[kKtT]/h\b',  # Mass flow
            r'\b\d+\.?\d*\s*[kKmM]?W\b',  # Power
            r'\b\d+\.?\d*\s*hp\b',  # Power
            r'\b\d+\.?\d*\s*[mkc]?m[²³]?\b',  # Length/Area/Volume
            r'\b\d+\.?\d*\s*[kKtT]g?\b',  # Mass
            r'\b\d+\.?\d*\s*%\b',  # Percentage
        ]
        
        for pattern in unit_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                units_found.append({
                    'text': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'normalized': self.normalize(match.group())
                })
        
        return units_found
    
    def get_unit_statistics(self, text: str) -> Dict[str, any]:
        """
        Get statistics about units in text
        
        Args:
            text: Input text
            
        Returns:
            Statistics dictionary
        """
        units = self.extract_units(text)
        
        # Group by normalized form
        unit_groups = {}
        for unit in units:
            norm = unit['normalized']
            if norm not in unit_groups:
                unit_groups[norm] = []
            unit_groups[norm].append(unit['text'])
        
        return {
            'total_units': len(units),
            'unique_units': len(unit_groups),
            'unit_types': list(unit_groups.keys()),
            'most_common': max(unit_groups.items(), key=lambda x: len(x[1]))[0] if unit_groups else None,
            'variations': {k: list(set(v)) for k, v in unit_groups.items()}
        }
