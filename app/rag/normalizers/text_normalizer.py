"""
Text Normalizer
Chuẩn hoá text từ PDF: whitespace, unicode, dấu câu, tách đoạn
"""
import re
import unicodedata
from typing import List, Optional
from loguru import logger


class TextNormalizer:
    """
    Normalizer để làm sạch và chuẩn hoá text từ PDF
    """
    
    def __init__(self,
                 fix_unicode: bool = True,
                 normalize_whitespace: bool = True,
                 fix_punctuation: bool = True,
                 split_paragraphs: bool = True,
                 remove_control_chars: bool = True):
        """
        Initialize normalizer
        
        Args:
            fix_unicode: Fix unicode issues (normalize NFC, fix encoding)
            normalize_whitespace: Normalize spaces, tabs, newlines
            fix_punctuation: Fix common punctuation issues
            split_paragraphs: Split text into paragraphs
            remove_control_chars: Remove control characters
        """
        self.fix_unicode = fix_unicode
        self.normalize_whitespace = normalize_whitespace
        self.fix_punctuation = fix_punctuation
        self.split_paragraphs = split_paragraphs
        self.remove_control_chars = remove_control_chars
        
    def normalize(self, text: str) -> str:
        """
        Apply all normalization steps
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        if not text:
            return text
            
        # Apply normalizations in order
        if self.remove_control_chars:
            text = self._remove_control_characters(text)
            
        if self.fix_unicode:
            text = self._fix_unicode_issues(text)
            
        if self.normalize_whitespace:
            text = self._normalize_whitespace(text)
            
        if self.fix_punctuation:
            text = self._fix_punctuation_spacing(text)
            
        return text.strip()
    
    def normalize_paragraphs(self, text: str) -> List[str]:
        """
        Normalize and split into paragraphs
        
        Args:
            text: Input text
            
        Returns:
            List of normalized paragraphs
        """
        # First normalize the text
        text = self.normalize(text)
        
        if not self.split_paragraphs:
            return [text] if text else []
            
        # Split into paragraphs
        paragraphs = self._split_into_paragraphs(text)
        
        # Clean each paragraph
        cleaned = []
        for para in paragraphs:
            para = para.strip()
            if para:
                cleaned.append(para)
                
        return cleaned
    
    def _remove_control_characters(self, text: str) -> str:
        """
        Remove control characters except newlines and tabs
        
        Args:
            text: Input text
            
        Returns:
            Text without control characters
        """
        # Keep only printable characters, spaces, newlines, and tabs
        allowed = set(['\n', '\r', '\t'])
        
        cleaned = []
        for char in text:
            if char in allowed or not unicodedata.category(char).startswith('C'):
                cleaned.append(char)
            else:
                # Replace control chars with space
                cleaned.append(' ')
                
        return ''.join(cleaned)
    
    def _fix_unicode_issues(self, text: str) -> str:
        """
        Fix common unicode issues
        
        Args:
            text: Input text
            
        Returns:
            Fixed text
        """
        # Normalize to NFC (canonical composition)
        text = unicodedata.normalize('NFC', text)
        
        # Fix common mojibake patterns
        replacements = {
            'â€™': "'",  # Right single quote
            'â€œ': '"',  # Left double quote
            'â€': '"',   # Right double quote
            'â€"': '—',  # Em dash
            'â€"': '–',  # En dash
            'â€¦': '...',  # Ellipsis
            'Ã©': 'é',   # e acute
            'Ã¨': 'è',   # e grave
            'Ã ': 'à',   # a grave
            'Ã§': 'ç',   # c cedilla
            'Ã±': 'ñ',   # n tilde
            '\xa0': ' ',  # Non-breaking space
            '\u2028': '\n',  # Line separator
            '\u2029': '\n\n',  # Paragraph separator
        }
        
        for bad, good in replacements.items():
            text = text.replace(bad, good)
            
        # Remove zero-width characters
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace characters
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple tabs with single space
        text = re.sub(r'\t+', ' ', text)
        
        # Normalize line breaks (Windows -> Unix)
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove spaces at start/end of lines
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        return text
    
    def _fix_punctuation_spacing(self, text: str) -> str:
        """
        Fix spacing around punctuation
        
        Args:
            text: Input text
            
        Returns:
            Text with fixed punctuation spacing
        """
        # Remove space before punctuation
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        
        # Add space after punctuation if missing (except at end)
        text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)
        
        # Fix quotes spacing
        text = re.sub(r'\s+"', '"', text)  # Remove space before opening quote
        text = re.sub(r'"\s+', '"', text)  # Remove space after closing quote
        
        # Fix parentheses spacing
        text = re.sub(r'\s+\)', ')', text)  # Remove space before )
        text = re.sub(r'\(\s+', '(', text)  # Remove space after (
        
        # Fix dash spacing
        text = re.sub(r'\s+-\s+', ' - ', text)  # Ensure spaces around dash
        text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1-\2', text)  # No spaces in number ranges
        
        # Fix ellipsis
        text = re.sub(r'\.\s+\.\s+\.', '...', text)
        text = re.sub(r'\.{4,}', '...', text)  # Limit to 3 dots
        
        return text
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs
        
        Args:
            text: Input text
            
        Returns:
            List of paragraphs
        """
        # Split on double newlines
        paragraphs = text.split('\n\n')
        
        # Also split on single newline if followed by capital letter or number
        result = []
        for para in paragraphs:
            lines = para.split('\n')
            current = []
            
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                    
                # Check if this starts a new paragraph
                if current and self._is_paragraph_start(line):
                    # Save current paragraph
                    result.append(' '.join(current))
                    current = [line]
                else:
                    current.append(line)
            
            # Add remaining lines
            if current:
                result.append(' '.join(current))
        
        return result
    
    def _is_paragraph_start(self, line: str) -> bool:
        """
        Check if line starts a new paragraph
        
        Args:
            line: Text line
            
        Returns:
            True if this starts a new paragraph
        """
        line = line.strip()
        if not line:
            return False
            
        # Numbered list
        if re.match(r'^\d+[\.\)]\s+', line):
            return True
            
        # Bullet list
        if re.match(r'^[-•*]\s+', line):
            return True
            
        # Section heading (all caps or title case with colon)
        if line.isupper() and len(line.split()) <= 5:
            return True
            
        if re.match(r'^[A-Z][^.!?]*:\s*$', line):
            return True
            
        # Starts with multiple spaces (indentation)
        if line != line.lstrip() and len(line) - len(line.lstrip()) >= 2:
            return True
            
        return False


class TechnicalTextNormalizer(TextNormalizer):
    """
    Extended normalizer for technical documents
    """
    
    def __init__(self, 
                 preserve_equations: bool = True,
                 preserve_tables: bool = True,
                 **kwargs):
        """
        Initialize technical normalizer
        
        Args:
            preserve_equations: Preserve mathematical equations
            preserve_tables: Preserve table formatting
            **kwargs: Arguments for parent class
        """
        super().__init__(**kwargs)
        self.preserve_equations = preserve_equations
        self.preserve_tables = preserve_tables
    
    def normalize(self, text: str) -> str:
        """
        Apply normalization with technical content preservation
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        if not text:
            return text
            
        # Protect technical content
        protected_sections = []
        
        if self.preserve_equations:
            text, eq_sections = self._protect_equations(text)
            protected_sections.extend(eq_sections)
            
        if self.preserve_tables:
            text, table_sections = self._protect_tables(text)
            protected_sections.extend(table_sections)
        
        # Apply normal normalization
        text = super().normalize(text)
        
        # Restore protected sections
        for placeholder, original in protected_sections:
            text = text.replace(placeholder, original)
            
        return text
    
    def _protect_equations(self, text: str) -> tuple:
        """
        Protect mathematical equations from normalization
        
        Args:
            text: Input text
            
        Returns:
            (text with placeholders, list of (placeholder, original) pairs)
        """
        protected = []
        placeholder_counter = 0
        
        # Protect inline math (between $ or \( \))
        patterns = [
            (r'\$[^$]+\$', 'MATH'),
            (r'\\\([^)]+\\\)', 'MATH'),
            (r'\\\[[^\]]+\\\]', 'MATHBLOCK'),
        ]
        
        for pattern, prefix in patterns:
            matches = list(re.finditer(pattern, text))
            for match in matches:
                placeholder = f"__{prefix}_{placeholder_counter}__"
                protected.append((placeholder, match.group()))
                text = text.replace(match.group(), placeholder, 1)
                placeholder_counter += 1
                
        return text, protected
    
    def _protect_tables(self, text: str) -> tuple:
        """
        Protect table formatting from normalization
        
        Args:
            text: Input text
            
        Returns:
            (text with placeholders, list of (placeholder, original) pairs)
        """
        protected = []
        
        # Simple heuristic: lines with multiple | or tab-separated values
        lines = text.split('\n')
        in_table = False
        table_lines = []
        result_lines = []
        
        for line in lines:
            # Check if line looks like table
            if '|' in line and line.count('|') >= 2:
                in_table = True
                table_lines.append(line)
            elif in_table and (not line.strip() or '---' in line):
                # Table separator or empty line in table
                table_lines.append(line)
            elif in_table:
                # End of table
                if table_lines:
                    placeholder = f"__TABLE_{len(protected)}__"
                    protected.append((placeholder, '\n'.join(table_lines)))
                    result_lines.append(placeholder)
                    table_lines = []
                in_table = False
                result_lines.append(line)
            else:
                result_lines.append(line)
        
        # Handle remaining table lines
        if table_lines:
            placeholder = f"__TABLE_{len(protected)}__"
            protected.append((placeholder, '\n'.join(table_lines)))
            result_lines.append(placeholder)
            
        return '\n'.join(result_lines), protected
