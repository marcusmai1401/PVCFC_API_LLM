"""
Fuzzy Text Matching Utilities

Provides fuzzy text overlap scoring for citation validation.
Uses only Python stdlib (difflib, re) for compatibility.

Functions:
    fuzzy_overlap: Compute fuzzy overlap between two texts
    fuzzy_overlap_keywords: Check keyword presence in text

Example:
    >>> from app.rag.fuzzy_matcher import fuzzy_overlap, fuzzy_overlap_keywords
    >>> score = fuzzy_overlap("Hello World", "hello world")
    >>> score > 0.9
    True
    >>> keywords = ["language", "NLP", "transformers"]
    >>> text = "Natural Language Processing (NLP) enables machines."
    >>> round(fuzzy_overlap_keywords(text, keywords), 2)
    0.67
"""

import re
from difflib import SequenceMatcher
from typing import List, Set


def _normalize(text: str) -> str:
    """
    Normalize text for comparison.

    Args:
        text: Input text

    Returns:
        Normalized text (lowercase, stripped, collapsed whitespace)

    Example:
        >>> _normalize("  Hello   World  ")
        'hello world'
    """
    if not text:
        return ""

    # Lowercase and strip
    text = text.lower().strip()

    # Collapse multiple whitespace to single space
    text = re.sub(r"\s+", " ", text)

    return text


def _tokenize(text: str) -> List[str]:
    """
    Tokenize normalized text.

    Args:
        text: Input text (should be normalized)

    Returns:
        List of tokens

    Example:
        >>> _tokenize("hello world")
        ['hello', 'world']
    """
    if not text:
        return []
    return text.split()


def fuzzy_overlap(text_a: str, text_b: str) -> float:
    """
    Compute fuzzy overlap between two texts.

    Uses both token-level (Jaccard) and character-level (SequenceMatcher) similarity.
    Final score is weighted average: 0.5 * token_overlap + 0.5 * char_overlap.

    Args:
        text_a: First text
        text_b: Second text

    Returns:
        Similarity score in [0.0, 1.0], where 1.0 is identical

    Example:
        >>> round(fuzzy_overlap("Hello, World!", "hello world"), 2) >= 0.90
        True
        >>> round(fuzzy_overlap("abc", "xyz"), 2)
        0.0
        >>> fuzzy_overlap("", "non-empty")
        0.0
        >>> fuzzy_overlap("same text", "same text")
        1.0
    """
    # Normalize both texts
    norm_a = _normalize(text_a)
    norm_b = _normalize(text_b)

    # Handle empty strings
    if not norm_a or not norm_b:
        return 0.0

    # Token overlap (Jaccard)
    tokens_a = set(_tokenize(norm_a))
    tokens_b = set(_tokenize(norm_b))

    if not tokens_a or not tokens_b:
        token_overlap = 0.0
    else:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        token_overlap = intersection / union if union > 0 else 0.0

    # Character overlap (difflib)
    char_overlap = SequenceMatcher(None, norm_a, norm_b).ratio()

    # Weighted average
    score = 0.5 * token_overlap + 0.5 * char_overlap

    # Clip to [0, 1]
    return max(0.0, min(1.0, score))


def fuzzy_overlap_keywords(page_text: str, keywords: List[str]) -> float:
    """
    Compute keyword overlap with text.

    Checks how many keywords are present in the text using:
    - Word boundary matching for alphanumeric keywords
    - Substring matching for keywords with special characters

    Args:
        page_text: Text to search in
        keywords: List of keywords to find

    Returns:
        Fraction of keywords found, in [0.0, 1.0]

    Example:
        >>> text = "Natural Language Processing (NLP) enables machines to understand language."
        >>> round(fuzzy_overlap_keywords(text, ["language", "NLP", "transformers"]), 2)
        0.67
        >>> fuzzy_overlap_keywords(text, [])
        0.0
        >>> fuzzy_overlap_keywords("", ["any"])
        0.0
    """
    if not keywords:
        return 0.0

    # Normalize page text once
    norm_text = _normalize(page_text)

    if not norm_text:
        return 0.0

    matched = 0

    for keyword in keywords:
        # Normalize keyword
        norm_kw = _normalize(keyword)

        if not norm_kw:
            continue

        # Check if keyword is alphanumeric (use word boundary)
        if norm_kw.replace(" ", "").isalnum():
            # Use regex word boundary for exact word match
            # Escape special regex chars
            escaped_kw = re.escape(norm_kw)
            pattern = r"\b" + escaped_kw + r"\b"
            if re.search(pattern, norm_text):
                matched += 1
        else:
            # Fallback: substring check for keywords with special chars
            if norm_kw in norm_text:
                matched += 1

    # Return fraction
    score = matched / len(keywords)

    return max(0.0, min(1.0, score))


# Additional helper for extracting keywords from text
def extract_keywords_simple(text: str, min_length: int = 4) -> Set[str]:
    """
    Extract simple keywords from text.

    Filters to tokens with length >= min_length, alphanumeric only.

    Args:
        text: Input text
        min_length: Minimum token length (default: 4)

    Returns:
        Set of normalized keywords

    Example:
        >>> kw = extract_keywords_simple("Natural Language Processing")
        >>> "language" in kw
        True
        >>> "and" in kw
        False
    """
    norm = _normalize(text)
    tokens = _tokenize(norm)

    # Filter by length and alphanumeric
    keywords = {
        token for token in tokens if len(token) >= min_length and token.isalnum()
    }

    return keywords


if __name__ == "__main__":
    # Run doctests
    import doctest

    doctest.testmod()

    # Smoke tests
    print("=== Fuzzy Matcher Smoke Tests ===")

    # Test 1: Exact match
    score1 = fuzzy_overlap("hello world", "hello world")
    print(f"Exact match: {score1:.2f} (expected: 1.00)")
    assert score1 == 1.0

    # Test 2: Partial match
    score2 = fuzzy_overlap("hello world", "hello there")
    print(f"Partial match: {score2:.2f} (expected: ~0.50)")
    assert 0.4 <= score2 <= 0.6

    # Test 3: No match
    score3 = fuzzy_overlap("abc", "xyz")
    print(f"No match: {score3:.2f} (expected: 0.00)")
    assert score3 == 0.0

    # Test 4: Keywords
    text = "Natural Language Processing (NLP) enables machines to understand language."
    keywords = ["language", "NLP", "transformers"]
    score4 = fuzzy_overlap_keywords(text, keywords)
    print(f"Keywords match: {score4:.2f} (expected: 0.67)")
    assert abs(score4 - 0.67) < 0.01

    # Test 5: Empty handling
    score5 = fuzzy_overlap("", "text")
    print(f"Empty handling: {score5:.2f} (expected: 0.00)")
    assert score5 == 0.0

    print("\n✓ All smoke tests passed!")
