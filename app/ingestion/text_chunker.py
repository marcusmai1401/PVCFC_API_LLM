"""
Text Chunking Module for Document Processing
Implements semantic chunking with overlap and metadata preservation
"""
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class TextChunk:
    """Represents a single text chunk"""

    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    char_count: int
    word_count: int
    start_char: int
    end_char: int
    page_nums: List[int]
    metadata: Dict[str, Any]
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


class TextChunker:
    """
    Text chunking class with multiple strategies
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
        chunking_strategy: str = "semantic",
    ):
        """
        Initialize text chunker

        Args:
            chunk_size: Target size for chunks (in characters)
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum size for a valid chunk
            chunking_strategy: Strategy to use ('semantic', 'fixed', 'sentence')
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.chunking_strategy = chunking_strategy

        # Sentence splitters
        self.sentence_endings = re.compile(r"[.!?]\s+")
        self.paragraph_separator = re.compile(r"\n\n+")

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        metadata: Optional[Dict] = None,
        page_nums: Optional[List[int]] = None,
    ) -> List[TextChunk]:
        """
        Chunk text using the configured strategy

        Args:
            text: Text to chunk
            doc_id: Document identifier
            metadata: Optional metadata to attach to chunks
            page_nums: Optional page numbers for the text

        Returns:
            List of TextChunk objects
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            logger.warning(f"Text too short to chunk: {len(text)} chars")
            return []

        metadata = metadata or {}
        page_nums = page_nums or []

        # Choose chunking strategy
        if self.chunking_strategy == "semantic":
            chunks = self._semantic_chunking(text)
        elif self.chunking_strategy == "sentence":
            chunks = self._sentence_chunking(text)
        else:  # fixed
            chunks = self._fixed_chunking(text)

        # Create TextChunk objects
        text_chunks = []
        for i, (chunk_text, start_char, end_char) in enumerate(chunks):
            chunk_id = self._generate_chunk_id(doc_id, i, chunk_text)

            text_chunk = TextChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                chunk_index=i,
                text=chunk_text,
                char_count=len(chunk_text),
                word_count=len(chunk_text.split()),
                start_char=start_char,
                end_char=end_char,
                page_nums=page_nums,
                metadata=metadata.copy(),
            )

            text_chunks.append(text_chunk)

        logger.info(f"Created {len(text_chunks)} chunks from {len(text)} chars")
        return text_chunks

    def _semantic_chunking(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Semantic chunking that respects paragraph and sentence boundaries
        """
        chunks = []

        # Split into paragraphs first
        paragraphs = self.paragraph_separator.split(text)

        current_chunk = []
        current_size = 0
        current_start = 0
        char_position = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            # If paragraph is too large, split it
            if para_size > self.chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append((chunk_text, current_start, char_position))

                    # Start new chunk with overlap
                    if self.chunk_overlap > 0 and current_chunk:
                        overlap_text = current_chunk[-1][-self.chunk_overlap :]
                        current_chunk = [overlap_text]
                        current_size = len(overlap_text)
                        current_start = char_position - self.chunk_overlap
                    else:
                        current_chunk = []
                        current_size = 0
                        current_start = char_position

                # Split large paragraph by sentences
                sentences = self._split_into_sentences(para)
                for sent in sentences:
                    sent_size = len(sent)

                    if current_size + sent_size > self.chunk_size and current_chunk:
                        # Save current chunk
                        chunk_text = " ".join(current_chunk)
                        chunks.append((chunk_text, current_start, char_position))

                        # Start new chunk with overlap
                        if self.chunk_overlap > 0:
                            overlap_text = (
                                current_chunk[-1][-self.chunk_overlap :]
                                if current_chunk
                                else ""
                            )
                            current_chunk = (
                                [overlap_text, sent] if overlap_text else [sent]
                            )
                            current_size = len(overlap_text) + sent_size
                            current_start = char_position - len(overlap_text)
                        else:
                            current_chunk = [sent]
                            current_size = sent_size
                            current_start = char_position
                    else:
                        current_chunk.append(sent)
                        current_size += sent_size

                    char_position += sent_size

            # Paragraph fits in current chunk
            elif current_size + para_size <= self.chunk_size:
                current_chunk.append(para)
                current_size += para_size
                char_position += para_size

            # Need to start new chunk
            else:
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append((chunk_text, current_start, char_position))

                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-1][-self.chunk_overlap :]
                    current_chunk = [overlap_text, para]
                    current_size = len(overlap_text) + para_size
                    current_start = char_position - len(overlap_text)
                else:
                    current_chunk = [para]
                    current_size = para_size
                    current_start = char_position

                char_position += para_size

        # Add remaining chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append((chunk_text, current_start, char_position))

        return chunks

    def _sentence_chunking(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Chunk by sentences
        """
        chunks = []
        sentences = self._split_into_sentences(text)

        current_chunk = []
        current_size = 0
        current_start = 0
        char_position = 0

        for sent in sentences:
            sent_size = len(sent)

            if current_size + sent_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append((chunk_text, current_start, char_position))

                # Start new chunk with overlap
                if self.chunk_overlap > 0:
                    # Take last few sentences for overlap
                    overlap_sents = []
                    overlap_size = 0
                    for s in reversed(current_chunk):
                        overlap_size += len(s)
                        overlap_sents.insert(0, s)
                        if overlap_size >= self.chunk_overlap:
                            break
                    current_chunk = overlap_sents + [sent]
                    current_size = sum(len(s) for s in current_chunk)
                    current_start = char_position - overlap_size
                else:
                    current_chunk = [sent]
                    current_size = sent_size
                    current_start = char_position
            else:
                current_chunk.append(sent)
                current_size += sent_size

            char_position += sent_size

        # Add remaining chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append((chunk_text, current_start, char_position))

        return chunks

    def _fixed_chunking(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Simple fixed-size chunking
        """
        chunks = []
        text_length = len(text)

        start = 0
        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            # Try to break at word boundary
            if end < text_length:
                space_pos = text.rfind(" ", start, end)
                if space_pos > start:
                    end = space_pos

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append((chunk_text, start, end))

            # Move start position with overlap
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        sentences = []

        # Split by sentence endings
        parts = self.sentence_endings.split(text)

        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                # Add back the sentence ending if not the last part
                if i < len(parts) - 1:
                    # Find the ending character
                    match = self.sentence_endings.search(
                        text[text.find(part) + len(part) :]
                    )
                    if match:
                        part += match.group(0).strip()
                sentences.append(part)

        # If no sentence endings found, return the whole text
        if not sentences and text.strip():
            sentences = [text.strip()]

        return sentences

    def _generate_chunk_id(self, doc_id: str, index: int, text: str) -> str:
        """Generate unique chunk ID"""
        # Create hash of doc_id + index + text preview
        content = f"{doc_id}_{index}_{text[:100]}"
        hash_obj = hashlib.md5(content.encode())
        return f"{doc_id}_chunk_{index}_{hash_obj.hexdigest()[:8]}"

    def chunk_document(
        self, document: Dict[str, Any], doc_id: Optional[str] = None
    ) -> List[TextChunk]:
        """
        Chunk a document with pages

        Args:
            document: Document dictionary with 'pages' key
            doc_id: Optional document ID override

        Returns:
            List of TextChunk objects
        """
        doc_id = doc_id or document.get("file_name", "unknown")
        all_chunks = []

        # Get document metadata
        doc_metadata = {
            "title": document.get("title"),
            "author": document.get("author"),
            "subject": document.get("subject"),
            "file_name": document.get("file_name"),
        }

        # Process each page
        pages = document.get("pages", [])
        for page in pages:
            page_num = page.get("page_num", 0)
            page_text = page.get("text", "")

            if page_text:
                # Chunk the page text
                page_chunks = self.chunk_text(
                    text=page_text,
                    doc_id=doc_id,
                    metadata={**doc_metadata, "page": page_num},
                    page_nums=[page_num],
                )

                all_chunks.extend(page_chunks)

        # Update chunk indices
        for i, chunk in enumerate(all_chunks):
            chunk.chunk_index = i

        logger.info(f"Created {len(all_chunks)} chunks from document {doc_id}")
        return all_chunks

    def save_chunks(self, chunks: List[TextChunk], output_file: Path):
        """Save chunks to JSON file"""
        output_file.parent.mkdir(parents=True, exist_ok=True)

        chunks_data = [chunk.to_dict() for chunk in chunks]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(chunks)} chunks to {output_file}")

    def load_chunks(self, input_file: Path) -> List[TextChunk]:
        """Load chunks from JSON file"""
        with open(input_file, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)

        chunks = [TextChunk(**data) for data in chunks_data]
        logger.info(f"Loaded {len(chunks)} chunks from {input_file}")

        return chunks


# Alias for backward compatibility
SemanticChunker = TextChunker

# Export main classes
__all__ = ["TextChunker", "TextChunk", "SemanticChunker"]
