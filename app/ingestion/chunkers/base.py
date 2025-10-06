"""
Base Chunker Abstract Class

Defines the interface for all chunker implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ChunkType(Enum):
    """Types of chunks based on content"""

    TEXT = "text"
    TABLE = "table"
    PID = "pid"
    MIXED = "mixed"


@dataclass
class Chunk:
    """
    Represents a single chunk of text with metadata
    """

    chunk_id: str
    text: str
    chunk_type: ChunkType
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Source information
    doc_id: Optional[str] = None
    page: Optional[int] = None
    chunk_index: Optional[int] = None

    # Chunking metrics
    token_count: Optional[int] = None
    char_count: Optional[int] = None

    # Content hash for deduplication
    content_hash: Optional[str] = None

    # Optional structured fields
    headers: Optional[List[str]] = None
    equipment_tags: Optional[List[str]] = None

    def __post_init__(self):
        """Calculate basic metrics"""
        if self.char_count is None:
            self.char_count = len(self.text)

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary"""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "chunk_type": self.chunk_type.value,
            "metadata": self.metadata,
            "doc_id": self.doc_id,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "content_hash": self.content_hash,
        }


class BaseChunker(ABC):
    """
    Abstract base class for all chunkers.

    All chunker implementations must inherit from this class
    and implement the chunk() method.
    """

    def __init__(
        self,
        chunk_size: int = 900,
        chunk_overlap: int = 140,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1200,
    ):
        """
        Initialize base chunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap size in tokens
            min_chunk_size: Minimum chunk size in tokens
            max_chunk_size: Maximum chunk size in tokens
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

        # Metrics
        self.metrics = {
            "chunks_created": 0,
            "total_chars_processed": 0,
            "total_tokens_processed": 0,
        }

    @abstractmethod
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
        pass

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses simple character-based estimation (char_count / 4).
        Can be overridden by subclasses for more accurate counting.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Simple estimate: 1 token ≈ 4 characters
        return len(text) // 4

    def _generate_chunk_id(
        self, doc_id: Optional[str], page: Optional[int], index: int
    ) -> str:
        """
        Generate a unique chunk ID.

        Args:
            doc_id: Document ID
            page: Page number
            index: Chunk index

        Returns:
            Chunk ID string
        """
        parts = []

        if doc_id:
            parts.append(doc_id)

        if page is not None:
            parts.append(f"p{page}")

        parts.append(f"c{index}")

        return "_".join(parts)

    def get_metrics(self) -> Dict[str, Any]:
        """Get chunking metrics"""
        return self.metrics.copy()

    def reset_metrics(self):
        """Reset metrics counters"""
        self.metrics = {
            "chunks_created": 0,
            "total_chars_processed": 0,
            "total_tokens_processed": 0,
        }
