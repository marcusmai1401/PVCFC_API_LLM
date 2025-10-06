"""
Text Chunker

Handles chunking of regular text documents with semantic boundary preservation.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseChunker, Chunk, ChunkType
from .utils import (
    chunk_by_tokens,
    detect_headers,
    estimate_tokens,
    extract_equipment_tags,
    normalize_whitespace,
    split_into_sentences,
)

logger = logging.getLogger(__name__)


class TextChunker(BaseChunker):
    """
    Chunker for regular text documents.

    Features:
    - Token-based chunking with overlap
    - Header preservation
    - Semantic boundary respect (paragraphs, sentences)
    - Equipment tag extraction
    """

    def __init__(
        self,
        chunk_size: int = 900,
        chunk_overlap: int = 140,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1200,
        preserve_headers: bool = True,
        extract_tags: bool = True,
    ):
        """
        Initialize text chunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap size in tokens
            min_chunk_size: Minimum chunk size in tokens
            max_chunk_size: Maximum chunk size in tokens
            preserve_headers: Whether to detect and preserve headers
            extract_tags: Whether to extract equipment tags
        """
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
        )

        self.preserve_headers = preserve_headers
        self.extract_tags = extract_tags

    def chunk(
        self,
        text: str,
        doc_id: Optional[str] = None,
        page: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk the input text.

        Args:
            text: Input text to chunk
            doc_id: Document ID
            page: Page number
            metadata: Additional metadata

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        # Normalize whitespace while preserving structure
        text = normalize_whitespace(text, preserve_paragraphs=True)

        # Detect headers if enabled
        headers = []
        if self.preserve_headers:
            headers = detect_headers(text)

        # Chunk by tokens
        text_chunks = chunk_by_tokens(
            text,
            max_tokens=self.chunk_size,
            overlap_tokens=self.chunk_overlap,
            estimator=self.estimate_tokens,
        )

        # Convert to Chunk objects
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            # Skip too small chunks
            token_count = self.estimate_tokens(chunk_text)
            if token_count < self.min_chunk_size:
                logger.debug(f"Skipping small chunk {i}: {token_count} tokens")
                continue

            # Generate chunk ID
            chunk_id = self._generate_chunk_id(doc_id, page, i)

            # Build metadata
            chunk_metadata = metadata.copy() if metadata else {}

            # Add headers if any overlap with this chunk
            chunk_headers = None
            if self.preserve_headers and headers:
                chunk_headers = [h[0] for h in headers if h[0] in chunk_text]
                if not chunk_headers:
                    chunk_headers = None

            # Extract equipment tags if enabled
            tags = None
            if self.extract_tags:
                tags = extract_equipment_tags(chunk_text)
                if not tags:
                    tags = None

            # Create chunk
            chunk = Chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                chunk_type=ChunkType.TEXT,
                metadata=chunk_metadata,
                doc_id=doc_id,
                page=page,
                chunk_index=i,
                token_count=token_count,
                headers=chunk_headers,
                equipment_tags=tags,
            )

            chunks.append(chunk)

            # Update metrics
            self.metrics["chunks_created"] += 1
            self.metrics["total_chars_processed"] += len(chunk_text)
            self.metrics["total_tokens_processed"] += token_count

        logger.info(
            f"Created {len(chunks)} text chunks from {len(text)} chars "
            f"(avg {self.metrics['total_tokens_processed'] // max(1, len(chunks))} tokens/chunk)"
        )

        return chunks

    def chunk_with_headers(
        self,
        sections: List[tuple],
        doc_id: Optional[str] = None,
        page: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk text that's already been split into sections with headers.

        Args:
            sections: List of (header, content) tuples
            doc_id: Document ID
            page: Page number
            metadata: Additional metadata

        Returns:
            List of Chunk objects
        """
        all_chunks = []

        for header, content in sections:
            # Prepend header to content
            full_text = f"{header}\n\n{content}" if header else content

            # Chunk this section
            section_chunks = self.chunk(
                text=full_text, doc_id=doc_id, page=page, metadata=metadata
            )

            # Mark all chunks with the section header
            for chunk in section_chunks:
                if header and "section_header" not in chunk.metadata:
                    chunk.metadata["section_header"] = header

            all_chunks.extend(section_chunks)

        return all_chunks
