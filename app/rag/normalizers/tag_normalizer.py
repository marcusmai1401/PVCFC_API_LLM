"""
Tag Normalizer
Chuẩn hoá tag P&ID: regex patterns, uppercase, remove spaces
"""
import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class TagPattern:
    """Pattern definition for equipment tags"""
    name: str
    pattern: str
    description: str
    examples: List[str]


class TagNormalizer:
    """
    Normalizer để chuẩn hoá equipment tags trong P&ID documents
    """
    
    # Common P&ID tag patterns
    DEFAULT_PATTERNS = [
        TagPattern(
            name="valve",
            pattern=r"[A-Z]{2,3}[-\s]?\d{3,5}[A-Z]?",
            description="Valve tags (e.g., PV-101, FCV-2001)",
            examples=["PV-101", "FCV-2001", "HV 305A"]
        ),
        TagPattern(
            name="pump",
            pattern=r"P[-\s]?\d{3,4}[A-Z]?",
            description="Pump tags (e.g., P-101, P-2001A)",
            examples=["P-101", "P 2001A", "P-305B"]
        ),
        TagPattern(
            name="compressor",
            pattern=r"[CK][-\s]?\d{3,5}[A-Z]?",
            description="Compressor tags (e.g., C-101, K-2001)",
            examples=["C-101", "K-2001", "C 305A"]
        ),
        TagPattern(
            name="vessel",
            pattern=r"[VDT][-\s]?\d{3,4}[A-Z]?",
            description="Vessel/Tank tags (e.g., V-101, T-201)",
            examples=["V-101", "T-201", "D-305"]
        ),
        TagPattern(
            name="heat_exchanger",
            pattern=r"[EH][-\s]?\d{3,4}[A-Z]?",
            description="Heat exchanger tags (e.g., E-101, H-201)",
            examples=["E-101", "H-201", "E 305A"]
        ),
        TagPattern(
            name="instrument",
            pattern=r"[PTFL][IQRCAHLS]{1,2}[-\s]?\d{3,5}[A-Z]?",
            description="Instrument tags (e.g., PT-101, FIC-201)",
            examples=["PT-101", "FIC-201", "LT 305", "PIC-401A"]
        ),
        TagPattern(
            name="general",
            pattern=r"[A-Z]{2,4}[-\s]?\d{2,5}[A-Z]?",
            description="General equipment tags",
            examples=["KT-06101", "ABC-123", "XY 999Z"]
        )
    ]
    
    def __init__(self,
                 patterns: Optional[List[TagPattern]] = None,
                 uppercase: bool = True,
                 remove_spaces: bool = True,
                 standardize_separator: bool = True,
                 separator: str = "-"):
        """
        Initialize tag normalizer
        
        Args:
            patterns: Custom tag patterns (uses defaults if None)
            uppercase: Convert tags to uppercase
            remove_spaces: Remove spaces within tags
            standardize_separator: Use consistent separator
            separator: Standard separator to use (default "-")
        """
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.uppercase = uppercase
        self.remove_spaces = remove_spaces
        self.standardize_separator = standardize_separator
        self.separator = separator
        
        # Compile regex patterns
        self._compiled_patterns = {}
        for pattern in self.patterns:
            self._compiled_patterns[pattern.name] = re.compile(pattern.pattern, re.IGNORECASE)
    
    def normalize_tag(self, tag: str) -> str:
        """
        Normalize a single equipment tag
        
        Args:
            tag: Input tag
            
        Returns:
            Normalized tag
        """
        if not tag:
            return tag
            
        # Remove leading/trailing whitespace
        tag = tag.strip()
        
        # Convert to uppercase if needed
        if self.uppercase:
            tag = tag.upper()
        
        # Standardize separator
        if self.standardize_separator:
            # Replace various separators with standard one
            tag = re.sub(r'[\s\-_/\\]+', self.separator, tag)
        elif self.remove_spaces:
            # Just remove spaces
            tag = tag.replace(' ', '')
        
        # Remove any remaining special characters except separator
        if self.separator != '-':
            tag = re.sub(r'[^\w' + re.escape(self.separator) + r']', '', tag)
        else:
            tag = re.sub(r'[^\w\-]', '', tag)
        
        return tag
    
    def extract_tags(self, text: str) -> List[Dict[str, str]]:
        """
        Extract and normalize equipment tags from text
        
        Args:
            text: Input text
            
        Returns:
            List of dictionaries with tag info
        """
        tags_found = []
        seen_tags = set()
        
        for pattern_name, regex in self._compiled_patterns.items():
            matches = regex.finditer(text)
            
            for match in matches:
                original = match.group()
                normalized = self.normalize_tag(original)
                
                # Skip if already seen
                if normalized in seen_tags:
                    continue
                    
                seen_tags.add(normalized)
                tags_found.append({
                    'original': original,
                    'normalized': normalized,
                    'type': pattern_name,
                    'position': match.span()
                })
        
        # Sort by position in text
        tags_found.sort(key=lambda x: x['position'][0])
        
        return tags_found
    
    def replace_tags_in_text(self, text: str, normalize: bool = True) -> str:
        """
        Replace all tags in text with normalized versions
        
        Args:
            text: Input text
            normalize: Whether to normalize the tags
            
        Returns:
            Text with replaced tags
        """
        if not normalize:
            return text
            
        # Extract tags
        tags = self.extract_tags(text)
        
        # Replace from end to start to preserve positions
        for tag_info in reversed(tags):
            start, end = tag_info['position']
            text = text[:start] + tag_info['normalized'] + text[end:]
            
        return text
    
    def validate_tag(self, tag: str) -> Dict[str, any]:
        """
        Validate if a string is a valid equipment tag
        
        Args:
            tag: Tag to validate
            
        Returns:
            Dictionary with validation results
        """
        normalized = self.normalize_tag(tag)
        
        for pattern_name, regex in self._compiled_patterns.items():
            if regex.fullmatch(normalized):
                return {
                    'valid': True,
                    'type': pattern_name,
                    'normalized': normalized,
                    'pattern': self._get_pattern_by_name(pattern_name)
                }
        
        return {
            'valid': False,
            'normalized': normalized,
            'message': 'No matching pattern found'
        }
    
    def _get_pattern_by_name(self, name: str) -> Optional[TagPattern]:
        """Get pattern definition by name"""
        for pattern in self.patterns:
            if pattern.name == name:
                return pattern
        return None
    
    def group_tags_by_type(self, tags: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """
        Group extracted tags by equipment type
        
        Args:
            tags: List of tag dictionaries from extract_tags
            
        Returns:
            Dictionary grouped by type
        """
        grouped = {}
        
        for tag_info in tags:
            tag_type = tag_info['type']
            if tag_type not in grouped:
                grouped[tag_type] = []
            grouped[tag_type].append(tag_info['normalized'])
            
        return grouped
    
    def get_tag_statistics(self, text: str) -> Dict[str, any]:
        """
        Get statistics about tags in text
        
        Args:
            text: Input text
            
        Returns:
            Statistics dictionary
        """
        tags = self.extract_tags(text)
        grouped = self.group_tags_by_type(tags)
        
        stats = {
            'total_tags': len(tags),
            'unique_tags': len(set(t['normalized'] for t in tags)),
            'types': {},
            'most_common_type': None
        }
        
        # Count by type
        for tag_type, tag_list in grouped.items():
            stats['types'][tag_type] = len(tag_list)
        
        # Find most common type
        if stats['types']:
            most_common = max(stats['types'].items(), key=lambda x: x[1])
            stats['most_common_type'] = most_common[0]
            
        return stats


class ISA5_1_TagNormalizer(TagNormalizer):
    """
    Extended normalizer following ISA 5.1 standard for instrumentation
    """
    
    ISA_PATTERNS = [
        TagPattern(
            name="flow",
            pattern=r"F[IQRCAHLS]{1,3}[-\s]?\d{3,5}[A-Z]?",
            description="Flow instruments (FT, FIC, FCV, etc.)",
            examples=["FT-101", "FIC-201", "FCV-301"]
        ),
        TagPattern(
            name="pressure",
            pattern=r"P[IQRCAHLS]{1,3}[-\s]?\d{3,5}[A-Z]?",
            description="Pressure instruments (PT, PIC, PCV, PSV, etc.)",
            examples=["PT-101", "PIC-201", "PSV-301"]
        ),
        TagPattern(
            name="temperature",
            pattern=r"T[IQRCAHLS]{1,3}[-\s]?\d{3,5}[A-Z]?",
            description="Temperature instruments (TT, TIC, TCV, etc.)",
            examples=["TT-101", "TIC-201", "TCV-301"]
        ),
        TagPattern(
            name="level",
            pattern=r"L[IQRCAHLS]{1,3}[-\s]?\d{3,5}[A-Z]?",
            description="Level instruments (LT, LIC, LCV, etc.)",
            examples=["LT-101", "LIC-201", "LCV-301"]
        ),
        TagPattern(
            name="analysis",
            pattern=r"A[IQRCAHLS]{1,3}[-\s]?\d{3,5}[A-Z]?",
            description="Analysis instruments (AT, AIC, etc.)",
            examples=["AT-101", "AIC-201"]
        )
    ]
    
    def __init__(self, **kwargs):
        """Initialize with ISA 5.1 patterns"""
        # Combine ISA patterns with general equipment patterns
        all_patterns = self.ISA_PATTERNS + [p for p in self.DEFAULT_PATTERNS 
                                            if p.name not in ['instrument']]
        super().__init__(patterns=all_patterns, **kwargs)
    
    def parse_isa_tag(self, tag: str) -> Dict[str, str]:
        """
        Parse ISA 5.1 instrument tag into components
        
        Args:
            tag: Instrument tag (e.g., "FIC-101")
            
        Returns:
            Dictionary with tag components
        """
        normalized = self.normalize_tag(tag)
        
        # ISA tag format: [Variable][Function][-][Loop#][Suffix]
        match = re.match(r"([A-Z])([A-Z]{0,3})[-]?(\d{3,5})([A-Z])?", normalized)
        
        if not match:
            return {'valid': False, 'tag': normalized}
            
        variable, functions, loop_num, suffix = match.groups()
        
        # Decode variable letter
        variable_map = {
            'F': 'Flow',
            'P': 'Pressure',
            'T': 'Temperature',
            'L': 'Level',
            'A': 'Analysis',
            'V': 'Vibration',
            'E': 'Voltage',
            'I': 'Current',
            'Q': 'Quantity',
            'S': 'Speed',
            'W': 'Weight',
            'Z': 'Position'
        }
        
        # Decode function letters
        function_map = {
            'I': 'Indicator',
            'C': 'Controller',
            'T': 'Transmitter',
            'S': 'Switch',
            'V': 'Valve',
            'E': 'Element',
            'A': 'Alarm',
            'H': 'High',
            'L': 'Low',
            'R': 'Recorder',
            'Q': 'Totalizer'
        }
        
        parsed_functions = [function_map.get(f, f) for f in functions]
        
        return {
            'valid': True,
            'tag': normalized,
            'variable': variable_map.get(variable, variable),
            'variable_code': variable,
            'functions': parsed_functions,
            'function_codes': functions,
            'loop_number': loop_num,
            'suffix': suffix or ''
        }
