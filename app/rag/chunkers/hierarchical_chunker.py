"""
Hierarchical Chunker
Split documents into hierarchical chunks based on structure
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import tiktoken
from loguru import logger


@dataclass
class Chunk:
    """Data class for document chunk"""
    chunk_id: str
    text: str
    doc_id: str
    page_start: int
    page_end: int
    char_count: int
    token_count: int
    chunk_index: int
    parent_chunk_id: Optional[str] = None
    heading: Optional[str] = None
    level: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'doc_id': self.doc_id,
            'page_start': self.page_start,
            'page_end': self.page_end,
            'char_count': self.char_count,
            'token_count': self.token_count,
            'chunk_index': self.chunk_index,
            'parent_chunk_id': self.parent_chunk_id,
            'heading': self.heading,
            'level': self.level,
            'metadata': self.metadata
        }


class HierarchicalChunker:
    """
    Chunker that creates hierarchical chunks based on document structure
    """
    
    def __init__(self,
                 max_chunk_size: int = 1000,
                 min_chunk_size: int = 100,
                 chunk_overlap: int = 50,
                 use_token_count: bool = True,
                 tokenizer_model: str = "cl100k_base"):
        """
        Initialize chunker
        
        Args:
            max_chunk_size: Maximum chunk size (chars or tokens)
            min_chunk_size: Minimum chunk size
            chunk_overlap: Overlap between chunks
            use_token_count: Use token count instead of char count
            tokenizer_model: Tiktoken model name
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_token_count = use_token_count
        
        # Initialize tokenizer if using token count
        if use_token_count:
            try:
                self.tokenizer = tiktoken.get_encoding(tokenizer_model)
            except Exception as e:
                logger.warning(f"Failed to load tokenizer {tokenizer_model}: {e}")
                logger.warning("Falling back to character count")
                self.use_token_count = False
                self.tokenizer = None
        else:
            self.tokenizer = None
    
    def chunk_markdown(self, 
                      markdown: str,
                      doc_id: str,
                      metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """
        Chunk markdown document hierarchically
        
        Args:
            markdown: Markdown text
            doc_id: Document identifier
            metadata: Optional document metadata
            
        Returns:
            List of chunks
        """
        # Parse markdown structure
        sections = self._parse_markdown_structure(markdown)
        
        # Create chunks from sections
        chunks = []
        chunk_index = 0
        
        for section in sections:
            section_chunks = self._chunk_section(
                section=section,
                doc_id=doc_id,
                chunk_index=chunk_index,
                parent_id=None,
                metadata=metadata or {}
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        
        return chunks
    
    def chunk_extraction(self,
                        extraction_result: Dict[str, Any],
                        doc_id: Optional[str] = None) -> List[Chunk]:
        """
        Chunk extraction result from VectorExtractor
        
        Args:
            extraction_result: Result from VectorExtractor
            doc_id: Document identifier (uses file_path if not provided)
            
        Returns:
            List of chunks
        """
        if not doc_id:
            doc_id = extraction_result.get('file_path', 'unknown')
            doc_id = hashlib.md5(doc_id.encode()).hexdigest()[:8]
        
        chunks = []
        chunk_index = 0
        
        # Process each page
        for page_data in extraction_result.get('pages', []):
            page_num = page_data.get('page_num', 0)
            blocks = page_data.get('blocks', [])
            
            # Group blocks by structure
            grouped = self._group_blocks_by_structure(blocks)
            
            for group in grouped:
                group_chunks = self._chunk_block_group(
                    blocks=group['blocks'],
                    doc_id=doc_id,
                    page_num=page_num,
                    chunk_index=chunk_index,
                    heading=group.get('heading'),
                    level=group.get('level', 0)
                )
                chunks.extend(group_chunks)
                chunk_index += len(group_chunks)
        
        return chunks
    
    def _parse_markdown_structure(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Parse markdown into hierarchical sections
        
        Args:
            markdown: Markdown text
            
        Returns:
            List of section dictionaries
        """
        lines = markdown.split('\n')
        sections = []
        current_section = None
        
        for line in lines:
            # Check for heading
            if line.startswith('#'):
                # Save previous section
                if current_section:
                    sections.append(current_section)
                
                # Parse heading level
                level = len(line) - len(line.lstrip('#'))
                heading_text = line.lstrip('#').strip()
                
                current_section = {
                    'heading': heading_text,
                    'level': level,
                    'content': [],
                    'page_start': 0,
                    'page_end': 0
                }
            elif current_section:
                # Add content to current section
                current_section['content'].append(line)
                
                # Extract page numbers from comments
                if '<!-- Page' in line:
                    import re
                    match = re.search(r'Page (\d+)', line)
                    if match:
                        page_num = int(match.group(1)) - 1
                        if not current_section['page_start']:
                            current_section['page_start'] = page_num
                        current_section['page_end'] = page_num
            else:
                # No section yet, create default
                if not sections and line.strip():
                    current_section = {
                        'heading': None,
                        'level': 0,
                        'content': [line],
                        'page_start': 0,
                        'page_end': 0
                    }
        
        # Add last section
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _chunk_section(self,
                      section: Dict[str, Any],
                      doc_id: str,
                      chunk_index: int,
                      parent_id: Optional[str],
                      metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Chunk a single section
        
        Args:
            section: Section dictionary
            doc_id: Document ID
            chunk_index: Current chunk index
            parent_id: Parent chunk ID
            metadata: Chunk metadata
            
        Returns:
            List of chunks
        """
        chunks = []
        content = '\n'.join(section['content'])
        
        # Skip empty sections
        if not content.strip():
            return chunks
        
        # Calculate size
        if self.use_token_count and self.tokenizer:
            size = len(self.tokenizer.encode(content))
        else:
            size = len(content)
        
        # If section fits in one chunk
        if size <= self.max_chunk_size:
            chunk_id = self._generate_chunk_id(doc_id, chunk_index)
            chunk = Chunk(
                chunk_id=chunk_id,
                text=content,
                doc_id=doc_id,
                page_start=section['page_start'],
                page_end=section['page_end'],
                char_count=len(content),
                token_count=size if self.use_token_count else 0,
                chunk_index=chunk_index,
                parent_chunk_id=parent_id,
                heading=section['heading'],
                level=section['level'],
                metadata=metadata
            )
            chunks.append(chunk)
        else:
            # Split section into multiple chunks
            sub_chunks = self._split_content(
                content=content,
                doc_id=doc_id,
                chunk_index=chunk_index,
                page_start=section['page_start'],
                page_end=section['page_end'],
                heading=section['heading'],
                level=section['level'],
                parent_id=parent_id,
                metadata=metadata
            )
            chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_content(self,
                      content: str,
                      doc_id: str,
                      chunk_index: int,
                      page_start: int,
                      page_end: int,
                      heading: Optional[str],
                      level: int,
                      parent_id: Optional[str],
                      metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Split content into chunks with overlap
        
        Args:
            content: Text content
            doc_id: Document ID
            chunk_index: Starting chunk index
            page_start: Start page
            page_end: End page
            heading: Section heading
            level: Hierarchy level
            parent_id: Parent chunk ID
            metadata: Chunk metadata
            
        Returns:
            List of chunks
        """
        chunks = []
        
        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        
        current_chunk_text = []
        current_size = 0
        
        for para in paragraphs:
            # Calculate paragraph size
            if self.use_token_count and self.tokenizer:
                para_size = len(self.tokenizer.encode(para))
            else:
                para_size = len(para)
            
            # Check if adding this paragraph exceeds max size
            if current_size + para_size > self.max_chunk_size and current_chunk_text:
                # Create chunk
                chunk_text = '\n\n'.join(current_chunk_text)
                chunk_id = self._generate_chunk_id(doc_id, chunk_index + len(chunks))
                
                chunk = Chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    doc_id=doc_id,
                    page_start=page_start,
                    page_end=page_end,
                    char_count=len(chunk_text),
                    token_count=current_size if self.use_token_count else 0,
                    chunk_index=chunk_index + len(chunks),
                    parent_chunk_id=parent_id,
                    heading=heading,
                    level=level,
                    metadata=metadata
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk_text:
                    # Keep last paragraph for overlap
                    current_chunk_text = [current_chunk_text[-1], para]
                    current_size = para_size + len(current_chunk_text[0])
                else:
                    current_chunk_text = [para]
                    current_size = para_size
            else:
                # Add to current chunk
                current_chunk_text.append(para)
                current_size += para_size
        
        # Create final chunk
        if current_chunk_text:
            chunk_text = '\n\n'.join(current_chunk_text)
            chunk_id = self._generate_chunk_id(doc_id, chunk_index + len(chunks))
            
            chunk = Chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                doc_id=doc_id,
                page_start=page_start,
                page_end=page_end,
                char_count=len(chunk_text),
                token_count=current_size if self.use_token_count else 0,
                chunk_index=chunk_index + len(chunks),
                parent_chunk_id=parent_id,
                heading=heading,
                level=level,
                metadata=metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _group_blocks_by_structure(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Group blocks by structure type
        
        Args:
            blocks: List of text blocks
            
        Returns:
            List of grouped blocks
        """
        groups = []
        current_group = None
        
        for block in blocks:
            structure_type = block.get('structure_type', 'paragraph')
            
            if structure_type.startswith('heading'):
                # Start new group
                if current_group:
                    groups.append(current_group)
                
                level = 1 if structure_type == 'heading1' else 2 if structure_type == 'heading2' else 3
                current_group = {
                    'heading': block.get('text', ''),
                    'level': level,
                    'blocks': []
                }
            elif current_group:
                current_group['blocks'].append(block)
            else:
                # No heading yet
                if not groups:
                    current_group = {
                        'heading': None,
                        'level': 0,
                        'blocks': [block]
                    }
        
        # Add last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _chunk_block_group(self,
                          blocks: List[Dict[str, Any]],
                          doc_id: str,
                          page_num: int,
                          chunk_index: int,
                          heading: Optional[str],
                          level: int) -> List[Chunk]:
        """
        Chunk a group of blocks
        
        Args:
            blocks: List of text blocks
            doc_id: Document ID
            page_num: Page number
            chunk_index: Starting chunk index
            heading: Group heading
            level: Hierarchy level
            
        Returns:
            List of chunks
        """
        # Combine block texts
        texts = [block.get('text', '') for block in blocks]
        content = '\n'.join(texts)
        
        # Create chunks
        return self._split_content(
            content=content,
            doc_id=doc_id,
            chunk_index=chunk_index,
            page_start=page_num,
            page_end=page_num,
            heading=heading,
            level=level,
            parent_id=None,
            metadata={'blocks': len(blocks)}
        )
    
    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        return f"{doc_id}_chunk_{chunk_index:04d}"
    
    def get_chunk_statistics(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """
        Get statistics about chunks
        
        Args:
            chunks: List of chunks
            
        Returns:
            Statistics dictionary
        """
        if not chunks:
            return {
                'total_chunks': 0,
                'avg_chunk_size': 0,
                'min_chunk_size': 0,
                'max_chunk_size': 0
            }
        
        sizes = [c.token_count if self.use_token_count else c.char_count 
                for c in chunks]
        
        return {
            'total_chunks': len(chunks),
            'avg_chunk_size': sum(sizes) / len(sizes),
            'min_chunk_size': min(sizes),
            'max_chunk_size': max(sizes),
            'total_size': sum(sizes),
            'levels': list(set(c.level for c in chunks)),
            'pages_covered': {
                'start': min(c.page_start for c in chunks),
                'end': max(c.page_end for c in chunks)
            }
        }
