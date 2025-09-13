"""
Markdown Converter
Convert extracted PDF blocks to structured Markdown
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from loguru import logger


class MarkdownConverter:
    """
    Convert extracted PDF content to Markdown format
    """
    
    def __init__(self,
                 preserve_bbox: bool = False,
                 preserve_fonts: bool = False,
                 add_page_breaks: bool = True,
                 heading_font_threshold: float = 14.0):
        """
        Initialize converter
        
        Args:
            preserve_bbox: Include bounding box info as HTML comments
            preserve_fonts: Include font info as HTML comments
            add_page_breaks: Add page break markers
            heading_font_threshold: Min font size for headings
        """
        self.preserve_bbox = preserve_bbox
        self.preserve_fonts = preserve_fonts
        self.add_page_breaks = add_page_breaks
        self.heading_font_threshold = heading_font_threshold
    
    def convert_extraction(self, extraction_result: Dict[str, Any]) -> str:
        """
        Convert full extraction result to Markdown
        
        Args:
            extraction_result: Result from VectorExtractor
            
        Returns:
            Markdown formatted text
        """
        markdown_parts = []
        
        # Add document metadata as YAML front matter
        if 'file_path' in extraction_result:
            markdown_parts.append("---")
            markdown_parts.append(f"source: {extraction_result['file_path']}")
            markdown_parts.append(f"total_pages: {extraction_result.get('total_pages', 0)}")
            if 'statistics' in extraction_result:
                stats = extraction_result['statistics']
                markdown_parts.append(f"total_blocks: {stats.get('total_blocks', 0)}")
                markdown_parts.append(f"total_characters: {stats.get('total_characters', 0)}")
            markdown_parts.append("---\n")
        
        # Process each page
        for page_data in extraction_result.get('pages', []):
            page_md = self.convert_page(page_data)
            markdown_parts.append(page_md)
            
            if self.add_page_breaks and page_data != extraction_result['pages'][-1]:
                markdown_parts.append("\n---\n")  # Page separator
        
        return '\n'.join(markdown_parts)
    
    def convert_page(self, page_data: Dict[str, Any]) -> str:
        """
        Convert single page to Markdown
        
        Args:
            page_data: Page data from extraction
            
        Returns:
            Markdown formatted page
        """
        parts = []
        
        # Add page metadata comment
        page_num = page_data.get('page_num', 0)
        parts.append(f"<!-- Page {page_num + 1} -->")
        
        if self.preserve_bbox:
            width = page_data.get('width', 0)
            height = page_data.get('height', 0)
            parts.append(f"<!-- Dimensions: {width}x{height} -->")
        
        # Process blocks
        blocks = page_data.get('blocks', [])
        
        # Group consecutive blocks by structure type for better formatting
        grouped_blocks = self._group_blocks(blocks)
        
        for group_type, group_blocks in grouped_blocks:
            if group_type.startswith('heading'):
                # Convert headings
                for block in group_blocks:
                    heading_md = self._block_to_heading(block, group_type)
                    parts.append(heading_md)
            else:
                # Convert paragraphs
                paragraph_texts = []
                for block in group_blocks:
                    block_md = self._block_to_paragraph(block)
                    paragraph_texts.append(block_md)
                
                # Join paragraph blocks
                if paragraph_texts:
                    parts.append('\n'.join(paragraph_texts))
        
        return '\n\n'.join(parts)
    
    def _group_blocks(self, blocks: List[Dict[str, Any]]) -> List[tuple]:
        """
        Group consecutive blocks by structure type
        
        Args:
            blocks: List of text blocks
            
        Returns:
            List of (structure_type, blocks) tuples
        """
        if not blocks:
            return []
        
        grouped = []
        current_type = blocks[0].get('structure_type', 'paragraph')
        current_group = [blocks[0]]
        
        for block in blocks[1:]:
            block_type = block.get('structure_type', 'paragraph')
            
            # Check if we should start a new group
            if block_type != current_type:
                grouped.append((current_type, current_group))
                current_type = block_type
                current_group = [block]
            else:
                current_group.append(block)
        
        # Add last group
        if current_group:
            grouped.append((current_type, current_group))
        
        return grouped
    
    def _block_to_heading(self, block: Dict[str, Any], structure_type: str) -> str:
        """
        Convert block to Markdown heading
        
        Args:
            block: Text block
            structure_type: Type of heading
            
        Returns:
            Markdown heading
        """
        text = block.get('text', '').strip()
        if not text:
            return ""
        
        # Determine heading level
        if structure_type == 'heading1' or block.get('font_size', 0) > 16:
            level = "#"
        elif structure_type == 'heading2' or block.get('font_size', 0) > 14:
            level = "##"
        else:
            level = "###"
        
        heading = f"{level} {text}"
        
        # Add metadata as comment if requested
        if self.preserve_bbox or self.preserve_fonts:
            metadata = []
            if self.preserve_bbox and 'bbox' in block:
                bbox = block['bbox']
                metadata.append(f"bbox:{bbox}")
            if self.preserve_fonts:
                if 'font_size' in block:
                    metadata.append(f"size:{block['font_size']}")
                if 'font_name' in block:
                    metadata.append(f"font:{block['font_name']}")
            
            if metadata:
                heading += f"\n<!-- {', '.join(metadata)} -->"
        
        return heading
    
    def _block_to_paragraph(self, block: Dict[str, Any]) -> str:
        """
        Convert block to Markdown paragraph
        
        Args:
            block: Text block
            
        Returns:
            Markdown paragraph text
        """
        text = block.get('text', '').strip()
        if not text:
            return ""
        
        # Check for special paragraph types
        if self._is_list_item(text):
            # Format as list item
            if text[0].isdigit():
                # Numbered list - ensure proper format
                text = self._format_numbered_list(text)
            else:
                # Bullet list - convert to markdown
                text = self._format_bullet_list(text)
        
        # Add metadata as comment if requested
        if self.preserve_bbox or self.preserve_fonts:
            metadata = []
            if self.preserve_bbox and 'bbox' in block:
                bbox = block['bbox']
                metadata.append(f"bbox:{bbox}")
            if self.preserve_fonts:
                if 'font_size' in block:
                    metadata.append(f"size:{block['font_size']}")
                if 'font_name' in block:
                    metadata.append(f"font:{block['font_name']}")
            
            if metadata:
                text = f"<!-- {', '.join(metadata)} -->\n{text}"
        
        return text
    
    def _is_list_item(self, text: str) -> bool:
        """Check if text is a list item"""
        import re
        # Numbered list
        if re.match(r'^\d+[\.\)]\s+', text):
            return True
        # Bullet list
        if re.match(r'^[-•*]\s+', text):
            return True
        return False
    
    def _format_numbered_list(self, text: str) -> str:
        """Format numbered list item"""
        import re
        # Ensure consistent format: "1. Item"
        text = re.sub(r'^(\d+)[.\)]\s*', r'\1. ', text)
        return text
    
    def _format_bullet_list(self, text: str) -> str:
        """Format bullet list item"""
        import re
        # Convert to markdown bullet
        text = re.sub(r'^[-•*]\s*', '- ', text)
        return text
    
    def convert_with_structure(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert to Markdown with structure information preserved
        
        Args:
            extraction_result: Result from VectorExtractor
            
        Returns:
            Dictionary with markdown and structure metadata
        """
        markdown = self.convert_extraction(extraction_result)
        
        # Extract structure information
        structure_info = {
            'headings': [],
            'pages': [],
            'statistics': extraction_result.get('statistics', {})
        }
        
        # Collect headings with their positions
        for page_data in extraction_result.get('pages', []):
            page_num = page_data.get('page_num', 0)
            structure_info['pages'].append({
                'page_num': page_num,
                'char_count': page_data.get('char_count', 0),
                'block_count': page_data.get('block_count', 0)
            })
            
            for block in page_data.get('blocks', []):
                structure_type = block.get('structure_type', 'paragraph')
                if structure_type.startswith('heading'):
                    structure_info['headings'].append({
                        'text': block.get('text', ''),
                        'level': structure_type,
                        'page': page_num,
                        'font_size': block.get('font_size', 0)
                    })
        
        return {
            'markdown': markdown,
            'structure': structure_info,
            'source_file': extraction_result.get('file_path', '')
        }
    
    def save_markdown(self, 
                     markdown: str, 
                     output_path: str | Path,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Save markdown to file
        
        Args:
            markdown: Markdown text
            output_path: Output file path
            metadata: Optional metadata to save alongside
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save markdown
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        # Save metadata if provided
        if metadata:
            metadata_path = output_path.with_suffix('.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved markdown to {output_path}")
