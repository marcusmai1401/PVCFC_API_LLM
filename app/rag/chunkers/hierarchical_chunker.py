"""
Hierarchical Chunker
Split documents into hierarchical chunks based on structure
"""
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
            "chunk_id": self.chunk_id,
            "text": self.text,
            "doc_id": self.doc_id,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "chunk_index": self.chunk_index,
            "parent_chunk_id": self.parent_chunk_id,
            "heading": self.heading,
            "level": self.level,
            "metadata": self.metadata,
        }


class HierarchicalChunker:
    """
    Chunker that creates hierarchical chunks based on document structure
    """

    def __init__(
        self,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 100,
        chunk_overlap: int = 50,
        use_token_count: bool = True,
        tokenizer_model: str = "cl100k_base",
        chunking_strategy: str = "hierarchical",  # 'hierarchical' or 'sentence-window'
        sentence_window_size: int = 3,  # Number of sentences per window
    ):
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
        self.chunking_strategy = chunking_strategy
        self.sentence_window_size = sentence_window_size

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

    def chunk_markdown(
        self, markdown: str, doc_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk markdown document using selected strategy

        Args:
            markdown: Markdown text
            doc_id: Document identifier
            metadata: Optional document metadata

        Returns:
            List of chunks
        """
        # Use sentence-window strategy if specified
        if self.chunking_strategy == "sentence-window":
            return self._chunk_sentence_window(markdown, doc_id, metadata)

        # If using small-to-big strategy
        if self.chunking_strategy == "small-to-big":
            return self._chunk_small_to_big_markdown(markdown, doc_id, metadata)

        # Otherwise use hierarchical strategy
        # Parse markdown structure
        sections = self._parse_markdown_structure(markdown)

        # Create chunks from sections with parent-child relationships
        chunks = []
        chunk_index = 0

        for section in sections:
            section_chunks = self._chunk_section_with_parent(
                section=section,
                doc_id=doc_id,
                chunk_index=chunk_index,
                metadata=metadata or {},
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

        return chunks

    def chunk_extraction(
        self, extraction_result: Dict[str, Any], doc_id: Optional[str] = None
    ) -> List[Chunk]:
        """
        Chunk extraction result from VectorExtractor

        Args:
            extraction_result: Result from VectorExtractor
            doc_id: Document identifier (uses file_path if not provided)

        Returns:
            List of chunks
        """
        if not doc_id:
            doc_id = extraction_result.get("file_path", "unknown")
            doc_id = hashlib.sha256(doc_id.encode()).hexdigest()[:8]

        chunks = []
        chunk_index = 0

        # Process each page
        for page_data in extraction_result.get("pages", []):
            page_num = page_data.get("page_num", 0)
            blocks = page_data.get("blocks", [])

            # Group blocks by structure
            grouped = self._group_blocks_by_structure(blocks)

            for group in grouped:
                group_chunks = self._chunk_block_group(
                    blocks=group["blocks"],
                    doc_id=doc_id,
                    page_num=page_num,
                    chunk_index=chunk_index,
                    heading=group.get("heading"),
                    level=group.get("level", 0),
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
        lines = markdown.split("\n")
        sections = []
        current_section = None

        for line in lines:
            # Check for heading
            if line.startswith("#"):
                # Save previous section
                if current_section:
                    sections.append(current_section)

                # Parse heading level
                level = len(line) - len(line.lstrip("#"))
                heading_text = line.lstrip("#").strip()

                current_section = {
                    "heading": heading_text,
                    "level": level,
                    "content": [],
                    "page_start": 0,
                    "page_end": 0,
                }
            elif current_section:
                # Add content to current section
                current_section["content"].append(line)

                # Extract page numbers from comments
                if "<!-- Page" in line:
                    import re

                    match = re.search(r"Page (\d+)", line)
                    if match:
                        page_num = int(match.group(1)) - 1
                        if not current_section["page_start"]:
                            current_section["page_start"] = page_num
                        current_section["page_end"] = page_num
            else:
                # No section yet, create default
                if not sections and line.strip():
                    current_section = {
                        "heading": None,
                        "level": 0,
                        "content": [line],
                        "page_start": 0,
                        "page_end": 0,
                    }

        # Add last section
        if current_section:
            sections.append(current_section)

        return sections

    def _chunk_section(
        self,
        section: Dict[str, Any],
        doc_id: str,
        chunk_index: int,
        parent_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> List[Chunk]:
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
        content = "\n".join(section["content"])

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
                page_start=section["page_start"],
                page_end=section["page_end"],
                char_count=len(content),
                token_count=size if self.use_token_count else 0,
                chunk_index=chunk_index,
                parent_chunk_id=parent_id,
                heading=section["heading"],
                level=section["level"],
                metadata=metadata,
            )
            chunks.append(chunk)
        else:
            # Split section into multiple chunks
            sub_chunks = self._split_content(
                content=content,
                doc_id=doc_id,
                chunk_index=chunk_index,
                page_start=section["page_start"],
                page_end=section["page_end"],
                heading=section["heading"],
                level=section["level"],
                parent_id=parent_id,
                metadata=metadata,
            )
            chunks.extend(sub_chunks)

        return chunks

    def _split_content(
        self,
        content: str,
        doc_id: str,
        chunk_index: int,
        page_start: int,
        page_end: int,
        heading: Optional[str],
        level: int,
        parent_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> List[Chunk]:
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
        paragraphs = content.split("\n\n")

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
                chunk_text = "\n\n".join(current_chunk_text)
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
                    metadata=metadata,
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
            chunk_text = "\n\n".join(current_chunk_text)
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
                metadata=metadata,
            )
            chunks.append(chunk)

        return chunks

    def _group_blocks_by_structure(
        self, blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
            structure_type = block.get("structure_type", "paragraph")

            if structure_type.startswith("heading"):
                # Start new group
                if current_group:
                    groups.append(current_group)

                level = (
                    1
                    if structure_type == "heading1"
                    else 2
                    if structure_type == "heading2"
                    else 3
                )
                current_group = {
                    "heading": block.get("text", ""),
                    "level": level,
                    "blocks": [],
                }
            elif current_group:
                current_group["blocks"].append(block)
            else:
                # No heading yet
                if not groups:
                    current_group = {"heading": None, "level": 0, "blocks": [block]}

        # Add last group
        if current_group:
            groups.append(current_group)

        return groups

    def _chunk_block_group(
        self,
        blocks: List[Dict[str, Any]],
        doc_id: str,
        page_num: int,
        chunk_index: int,
        heading: Optional[str],
        level: int,
    ) -> List[Chunk]:
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
        texts = [block.get("text", "") for block in blocks]
        content = "\n".join(texts)

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
            metadata={"blocks": len(blocks)},
        )

    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        return f"{doc_id}_chunk_{chunk_index:04d}"

    def _chunk_section_with_parent(
        self,
        section: Dict[str, Any],
        doc_id: str,
        chunk_index: int,
        metadata: Dict[str, Any],
    ) -> List[Chunk]:
        """
        Chunk a section with parent-child relationships.
        Creates a parent chunk for the heading and child chunks for content.

        Args:
            section: Section dictionary
            doc_id: Document ID
            chunk_index: Current chunk index
            metadata: Chunk metadata

        Returns:
            List of chunks with parent-child relationships
        """
        chunks = []
        parent_chunk_id = None

        # Create parent chunk if section has a heading
        if section.get("heading"):
            parent_chunk_id = self._generate_chunk_id(doc_id, chunk_index)

            # Parent chunk contains heading and summary
            parent_text = f"{section['heading']}"

            # Add first part of content as summary (max 200 chars)
            content = "\n".join(section["content"])
            if content.strip():
                summary = content[:200].strip()
                if len(content) > 200:
                    summary += "..."
                parent_text = f"{parent_text}\n\n{summary}"

            parent_chunk = Chunk(
                chunk_id=parent_chunk_id,
                text=parent_text,
                doc_id=doc_id,
                page_start=section["page_start"],
                page_end=section["page_end"],
                char_count=len(parent_text),
                token_count=len(self.tokenizer.encode(parent_text))
                if self.use_token_count and self.tokenizer
                else 0,
                chunk_index=chunk_index,
                parent_chunk_id=None,  # Parent chunks don't have parents
                heading=section["heading"],
                level=section["level"],
                metadata={**metadata, "chunk_type": "parent"},
            )
            chunks.append(parent_chunk)
            chunk_index += 1

        # Create child chunks for content
        content = "\n".join(section["content"])
        if content.strip():
            # Use existing _chunk_section logic but with parent_id
            child_chunks = self._chunk_section(
                section=section,
                doc_id=doc_id,
                chunk_index=chunk_index,
                parent_id=parent_chunk_id,
                metadata={**metadata, "chunk_type": "child"},
            )
            chunks.extend(child_chunks)

        return chunks

    def _chunk_sentence_window(
        self, text: str, doc_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk text using sentence-window strategy.
        Each chunk contains a window of sentences with overlap.

        Args:
            text: Text to chunk
            doc_id: Document ID
            metadata: Optional metadata

        Returns:
            List of chunks
        """
        import re

        # Split into sentences more robustly
        # Match sentence endings followed by space (but not end of string)
        sentence_endings = re.findall(r"[^.!?]*[.!?]", text)
        sentences = [s.strip() for s in sentence_endings if s.strip()]

        if not sentences:
            return []

        chunks = []
        chunk_index = 0

        # Extract page information from text if available
        page_start = 0
        page_end = 0
        page_pattern = re.compile(r"<!-- Page (\d+) -->")
        page_matches = page_pattern.findall(text)
        if page_matches:
            page_nums = [int(p) - 1 for p in page_matches]
            page_start = min(page_nums)
            page_end = max(page_nums)

        # Create sliding window chunks
        # Calculate step based on overlap percentage
        overlap_sentences = max(
            0, int(self.sentence_window_size * self.chunk_overlap / 100)
        )
        window_step = max(1, self.sentence_window_size - overlap_sentences)

        i = 0
        while i < len(sentences):
            # Get window of sentences
            window_end = min(i + self.sentence_window_size, len(sentences))
            window_sentences = sentences[i:window_end]
            chunk_text = " ".join(window_sentences)

            # Skip if too short
            if len(chunk_text) < self.min_chunk_size and window_end < len(sentences):
                i += 1
                continue

            # Create chunk
            chunk_id = self._generate_chunk_id(doc_id, chunk_index)
            chunk = Chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                doc_id=doc_id,
                page_start=page_start,
                page_end=page_end,
                char_count=len(chunk_text),
                token_count=len(self.tokenizer.encode(chunk_text))
                if self.use_token_count and self.tokenizer
                else 0,
                chunk_index=chunk_index,
                parent_chunk_id=None,
                heading=None,
                level=0,
                metadata={
                    **metadata,
                    "chunking_strategy": "sentence-window",
                    "window_size": self.sentence_window_size,
                }
                if metadata
                else {
                    "chunking_strategy": "sentence-window",
                    "window_size": self.sentence_window_size,
                },
            )
            chunks.append(chunk)
            chunk_index += 1

            # Move window forward
            i += window_step

        return chunks

    def _chunk_small_to_big_markdown(
        self, markdown: str, doc_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk markdown by aggregating small units (sentences) up to target size within sections.
        Preserves parent-child relationships by creating a parent chunk per heading section.
        """
        import re

        sections = self._parse_markdown_structure(markdown)
        chunks: List[Chunk] = []
        chunk_index = 0

        for section in sections:
            # Create parent chunk first (if has heading)
            parent_chunk_id = None
            if section.get("heading"):
                parent_chunk_id = self._generate_chunk_id(doc_id, chunk_index)
                content = "\n".join(section["content"]).strip()
                summary = (
                    content[:200].strip() + ("..." if len(content) > 200 else "")
                    if content
                    else ""
                )
                parent_text = section["heading"] + ("\n\n" + summary if summary else "")
                parent_chunk = Chunk(
                    chunk_id=parent_chunk_id,
                    text=parent_text,
                    doc_id=doc_id,
                    page_start=section["page_start"],
                    page_end=section["page_end"],
                    char_count=len(parent_text),
                    token_count=len(self.tokenizer.encode(parent_text))
                    if self.use_token_count and self.tokenizer
                    else 0,
                    chunk_index=chunk_index,
                    parent_chunk_id=None,
                    heading=section["heading"],
                    level=section["level"],
                    metadata={**(metadata or {}), "chunk_type": "parent"},
                )
                chunks.append(parent_chunk)
                chunk_index += 1

            # Chunk content by sentences, aggregate up to max_chunk_size
            content = "\n".join(section["content"]).strip()
            if not content:
                continue
            sentences = re.findall(r"[^.!?]*[.!?]", content)
            sentences = [s.strip() for s in sentences if s.strip()]
            if not sentences:
                continue

            current_sentences: List[str] = []
            current_size = 0

            for sent in sentences:
                sent_size = (
                    len(self.tokenizer.encode(sent))
                    if self.use_token_count and self.tokenizer
                    else len(sent)
                )

                if current_sentences and current_size + sent_size > self.max_chunk_size:
                    # flush current chunk
                    chunk_text = " ".join(current_sentences)
                    c = Chunk(
                        chunk_id=self._generate_chunk_id(doc_id, chunk_index),
                        text=chunk_text,
                        doc_id=doc_id,
                        page_start=section["page_start"],
                        page_end=section["page_end"],
                        char_count=len(chunk_text),
                        token_count=current_size if self.use_token_count else 0,
                        chunk_index=chunk_index,
                        parent_chunk_id=parent_chunk_id,
                        heading=section["heading"],
                        level=section["level"],
                        metadata={
                            **(metadata or {}),
                            "chunk_type": "child",
                            "chunking_strategy": "small-to-big",
                        },
                    )
                    chunks.append(c)
                    chunk_index += 1

                    # overlap by one last sentence if overlap configured
                    if self.chunk_overlap > 0 and current_sentences:
                        current_sentences = [current_sentences[-1], sent]
                        current_size = (
                            len(self.tokenizer.encode(current_sentences[0]))
                            if self.use_token_count and self.tokenizer
                            else len(current_sentences[0])
                        ) + sent_size
                    else:
                        current_sentences = [sent]
                        current_size = sent_size
                else:
                    # accumulate
                    current_sentences.append(sent)
                    current_size += sent_size

            # flush remaining
            if current_sentences:
                chunk_text = " ".join(current_sentences)
                c = Chunk(
                    chunk_id=self._generate_chunk_id(doc_id, chunk_index),
                    text=chunk_text,
                    doc_id=doc_id,
                    page_start=section["page_start"],
                    page_end=section["page_end"],
                    char_count=len(chunk_text),
                    token_count=current_size if self.use_token_count else 0,
                    chunk_index=chunk_index,
                    parent_chunk_id=parent_chunk_id,
                    heading=section["heading"],
                    level=section["level"],
                    metadata={
                        **(metadata or {}),
                        "chunk_type": "child",
                        "chunking_strategy": "small-to-big",
                    },
                )
                chunks.append(c)
                chunk_index += 1

        return chunks

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
                "total_chunks": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0,
            }

        sizes = [
            c.token_count if self.use_token_count else c.char_count for c in chunks
        ]

        return {
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(sizes) / len(sizes),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
            "total_size": sum(sizes),
            "levels": list(set(c.level for c in chunks)),
            "pages_covered": {
                "start": min(c.page_start for c in chunks),
                "end": max(c.page_end for c in chunks),
            },
        }
