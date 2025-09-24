"""
Text processing utilities
"""
import re
import unicodedata
from typing import List, Optional


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and special characters
    """
    # Remove control characters
    text = "".join(
        char for char in text if not unicodedata.category(char).startswith("C")
    )

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)

    return text.strip()


def normalize_text(text: str) -> str:
    """
    Normalize text for indexing/search
    """
    # Convert to lowercase
    text = text.lower()

    # Remove punctuation except sentence endings
    text = re.sub(r"[^\w\s.!?-]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences
    """
    # Simple sentence splitting
    sentences = re.split(r"[.!?]\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    """
    if len(text) <= max_length:
        return text

    truncated = text[: max_length - len(suffix)]
    # Try to break at word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.8:  # If space is reasonably close
        truncated = truncated[:last_space]

    return truncated + suffix


def count_tokens_approximate(text: str) -> int:
    """
    Approximate token count (roughly 4 chars per token)
    """
    return len(text) // 4


__all__ = [
    "clean_text",
    "normalize_text",
    "split_sentences",
    "truncate_text",
    "count_tokens_approximate",
]
