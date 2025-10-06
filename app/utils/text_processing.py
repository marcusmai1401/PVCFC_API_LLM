"""
Text Processing Utilities

Shared functions for text preprocessing and tokenization used across:
- BM25 indexing (build_page_index)
- Query processing (page_reranker)
- Snippet extraction

Ensures consistency in text normalization and tokenization.
"""

import re
import unicodedata
from typing import List


def normalize_text(
    text: str, lowercase: bool = True, remove_extra_spaces: bool = True
) -> str:
    """
    Normalize text for consistent processing

    Args:
        text: Input text
        lowercase: Convert to lowercase
        remove_extra_spaces: Collapse multiple spaces to single space

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Normalize unicode (convert to NFC form)
    text = unicodedata.normalize("NFC", text)

    # Lowercase if requested
    if lowercase:
        text = text.lower()

    # Remove extra whitespace
    if remove_extra_spaces:
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

    return text


def tokenize_for_bm25(text: str, min_token_length: int = 1) -> List[str]:
    """
    Tokenize text for BM25 indexing and querying

    This is the CANONICAL tokenization function used for:
    - Building BM25 index (in build_page_index.py)
    - Processing queries (in page_reranker.py)

    Rules:
    - Lowercase conversion
    - Split on whitespace
    - Keep alphanumeric tokens and hyphens (e.g., "KT-06101", "150psi")
    - Filter out very short tokens (configurable)
    - Preserve technical terms and model numbers

    Args:
        text: Input text to tokenize
        min_token_length: Minimum token length to keep (default: 1)

    Returns:
        List of tokens

    Examples:
        >>> tokenize_for_bm25("Operating pressure: 150 psi")
        ['operating', 'pressure', '150', 'psi']

        >>> tokenize_for_bm25("Model KT-06101 specifications")
        ['model', 'kt-06101', 'specifications']
    """
    if not text:
        return []

    # Normalize first
    text = normalize_text(text, lowercase=True, remove_extra_spaces=True)

    # Split on whitespace
    tokens = text.split()

    # Filter tokens
    filtered_tokens = []
    for token in tokens:
        # Keep token if it meets minimum length
        if len(token) >= min_token_length:
            # Optional: Remove purely punctuation tokens
            # But keep tokens with mixed alphanumeric + punctuation (technical terms)
            if re.search(r"[a-zA-Z0-9]", token):
                filtered_tokens.append(token)

    return filtered_tokens


def preprocess_text_for_bm25(text: str) -> str:
    """
    Preprocess text for BM25 indexing (corpus preparation)

    This returns the preprocessed text string (not tokens) for storage
    in the corpus. The actual tokenization happens during BM25 build.

    Args:
        text: Input text

    Returns:
        Preprocessed text string
    """
    return normalize_text(text, lowercase=True, remove_extra_spaces=True)


def clean_text_for_snippet(text: str) -> str:
    """
    Clean text for snippet extraction

    Less aggressive than BM25 preprocessing - preserves case and formatting
    for display purposes.

    Args:
        text: Input text

    Returns:
        Cleaned text (preserves original case)
    """
    if not text:
        return ""

    # Normalize unicode
    text = unicodedata.normalize("NFC", text)

    # Remove control characters but preserve newlines
    text = "".join(
        char
        for char in text
        if char == "\n" or not unicodedata.category(char).startswith("C")
    )

    # Collapse multiple newlines to double newline
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces (but not newlines)
    text = re.sub(r"[^\S\n]+", " ", text)

    return text.strip()


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    Extract important keywords from text

    Simple keyword extraction based on token frequency
    (can be enhanced with TF-IDF or more sophisticated methods later)

    Args:
        text: Input text
        top_n: Number of top keywords to return

    Returns:
        List of keywords (sorted by importance)
    """
    from collections import Counter

    # Tokenize
    tokens = tokenize_for_bm25(text, min_token_length=3)

    # Count frequencies
    token_counts = Counter(tokens)

    # Get top N most common
    top_keywords = [word for word, count in token_counts.most_common(top_n)]

    return top_keywords


# Backwards compatibility aliases
def preprocess_for_bm25(text: str) -> str:
    """Alias for preprocess_text_for_bm25"""
    return preprocess_text_for_bm25(text)


def tokenize(text: str) -> List[str]:
    """Alias for tokenize_for_bm25 with default parameters"""
    return tokenize_for_bm25(text)
