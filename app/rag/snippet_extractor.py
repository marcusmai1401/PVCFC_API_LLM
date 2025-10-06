"""
Snippet Extractor for Citation Context

Extracts relevant text snippets from pages to provide context for citations.
Finds keyword matches and returns surrounding context windows.

Features:
- Keyword-based snippet extraction
- Context window management
- Snippet merging for overlapping regions
- Keyword highlighting
- Relevance-based ranking

Usage:
    extractor = SnippetExtractor()
    snippets = extractor.extract_snippets(
        text="Full page text here...",
        query="operating pressure",
        max_snippets=3
    )
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from loguru import logger

# Import config for default parameters
try:
    from app.config import get_config

    _pipeline_config = get_config()
    _default_context_size = _pipeline_config.SNIPPET_CONTEXT_SIZE
    _default_max_snippets = _pipeline_config.MAX_SNIPPETS_PER_PAGE
except ImportError:
    _default_context_size = 200
    _default_max_snippets = 3
    logger.warning("Config not available, using default snippet parameters")

# Import text processing utilities
try:
    from app.utils.text_processing import clean_text_for_snippet, tokenize_for_bm25
except ImportError:
    logger.warning("Text processing utils not available, using fallback")

    def tokenize_for_bm25(text: str) -> List[str]:
        return text.lower().split()

    def clean_text_for_snippet(text: str) -> str:
        return text.strip()


@dataclass
class Snippet:
    """
    Represents an extracted text snippet with context

    Attributes:
        text: The snippet text
        start_pos: Start position in original text
        end_pos: End position in original text
        matched_keywords: Set of keywords found in this snippet
        score: Relevance score (0.0 - 1.0)
        highlighted_text: Text with keywords highlighted (optional)
    """

    text: str
    start_pos: int
    end_pos: int
    matched_keywords: Set[str]
    score: float = 0.0
    highlighted_text: Optional[str] = None

    def __len__(self) -> int:
        """Length of snippet text"""
        return len(self.text)

    def overlaps_with(self, other: "Snippet", tolerance: int = 10) -> bool:
        """
        Check if this snippet overlaps with another

        Args:
            other: Another snippet
            tolerance: Number of characters to consider as overlap boundary

        Returns:
            True if snippets overlap
        """
        return (
            self.start_pos <= other.end_pos + tolerance
            and self.end_pos + tolerance >= other.start_pos
        )

    def merge_with(self, other: "Snippet") -> "Snippet":
        """
        Merge this snippet with another overlapping snippet

        Args:
            other: Another snippet to merge with

        Returns:
            New merged snippet
        """
        merged_start = min(self.start_pos, other.start_pos)
        merged_end = max(self.end_pos, other.end_pos)

        # Use the text from the original source (will be re-extracted)
        merged_text = self.text  # Placeholder, will be replaced by caller

        # Combine matched keywords
        merged_keywords = self.matched_keywords.union(other.matched_keywords)

        # Use higher score
        merged_score = max(self.score, other.score)

        return Snippet(
            text=merged_text,
            start_pos=merged_start,
            end_pos=merged_end,
            matched_keywords=merged_keywords,
            score=merged_score,
        )


class SnippetExtractor:
    """
    Extract relevant snippets from text based on query keywords

    This class provides methods to:
    1. Find keyword matches in text
    2. Extract context windows around matches
    3. Merge overlapping snippets
    4. Highlight keywords in snippets
    5. Rank snippets by relevance
    """

    def __init__(
        self,
        context_size: int = _default_context_size,
        max_snippets: int = _default_max_snippets,
        min_snippet_length: int = 50,
        highlight_template: str = "**{keyword}**",
    ):
        """
        Initialize SnippetExtractor

        Args:
            context_size: Number of characters to include around matches
            max_snippets: Maximum number of snippets to return
            min_snippet_length: Minimum length for a valid snippet
            highlight_template: Template for highlighting keywords (use {keyword})
        """
        self.context_size = context_size
        self.max_snippets = max_snippets
        self.min_snippet_length = min_snippet_length
        self.highlight_template = highlight_template

    def extract_snippets(
        self,
        text: str,
        query: str,
        max_snippets: Optional[int] = None,
        highlight: bool = True,
    ) -> List[Snippet]:
        """
        Extract relevant snippets from text based on query

        Args:
            text: Source text to extract from
            query: Query string with keywords
            max_snippets: Override default max_snippets
            highlight: Whether to highlight keywords in snippets

        Returns:
            List of Snippet objects, sorted by relevance
        """
        if not text or not query:
            return []

        max_snippets = max_snippets or self.max_snippets

        # Clean text for processing
        text = clean_text_for_snippet(text)

        # Extract keywords from query
        keywords = self._extract_keywords(query)

        if not keywords:
            logger.debug("No keywords extracted from query")
            return []

        # Find all keyword matches in text
        matches = self._find_keyword_matches(text, keywords)

        if not matches:
            logger.debug("No keyword matches found in text")
            return []

        # Extract snippets around matches
        snippets = self._extract_snippets_from_matches(text, matches, keywords)

        # Merge overlapping snippets
        snippets = self._merge_overlapping_snippets(text, snippets)

        # Score and rank snippets
        snippets = self._score_snippets(snippets, keywords)
        snippets.sort(key=lambda s: s.score, reverse=True)

        # Limit to max_snippets
        snippets = snippets[:max_snippets]

        # Add highlighting if requested
        if highlight:
            for snippet in snippets:
                snippet.highlighted_text = self._highlight_keywords(
                    snippet.text, snippet.matched_keywords
                )

        return snippets

    def _extract_keywords(self, query: str) -> Set[str]:
        """
        Extract keywords from query

        Args:
            query: Query string

        Returns:
            Set of lowercase keywords
        """
        # Use tokenization to get keywords
        tokens = tokenize_for_bm25(query)

        # Filter out very short tokens (likely stopwords or noise)
        keywords = {token for token in tokens if len(token) >= 2}

        return keywords

    def _find_keyword_matches(
        self, text: str, keywords: Set[str]
    ) -> List[Tuple[int, int, str]]:
        """
        Find all positions where keywords match in text

        Args:
            text: Text to search in
            keywords: Set of keywords to find

        Returns:
            List of (start_pos, end_pos, keyword) tuples
        """
        matches = []
        text_lower = text.lower()

        for keyword in keywords:
            # Use word boundary matching for better accuracy
            # Escape special regex characters in keyword
            escaped_keyword = re.escape(keyword)

            # Find all occurrences
            for match in re.finditer(r"\b" + escaped_keyword + r"\b", text_lower):
                start_pos = match.start()
                end_pos = match.end()
                matches.append((start_pos, end_pos, keyword))

        # Sort by position
        matches.sort(key=lambda x: x[0])

        return matches

    def _extract_snippets_from_matches(
        self,
        text: str,
        matches: List[Tuple[int, int, str]],
        all_keywords: Set[str],
    ) -> List[Snippet]:
        """
        Extract snippet context windows around keyword matches

        Args:
            text: Source text
            matches: List of (start_pos, end_pos, keyword) tuples
            all_keywords: All keywords from query

        Returns:
            List of Snippet objects
        """
        snippets = []
        text_length = len(text)

        for start_pos, end_pos, keyword in matches:
            # Calculate context window
            snippet_start = max(0, start_pos - self.context_size // 2)
            snippet_end = min(text_length, end_pos + self.context_size // 2)

            # Try to expand to word boundaries
            snippet_start = self._find_word_boundary(
                text, snippet_start, direction="left"
            )
            snippet_end = self._find_word_boundary(text, snippet_end, direction="right")

            # Extract snippet text
            snippet_text = text[snippet_start:snippet_end].strip()

            # Skip if too short
            if len(snippet_text) < self.min_snippet_length:
                continue

            # Find which keywords are in this snippet
            snippet_lower = snippet_text.lower()
            matched_keywords = {kw for kw in all_keywords if kw in snippet_lower}

            # Create snippet object
            snippet = Snippet(
                text=snippet_text,
                start_pos=snippet_start,
                end_pos=snippet_end,
                matched_keywords=matched_keywords,
            )

            snippets.append(snippet)

        return snippets

    def _find_word_boundary(self, text: str, pos: int, direction: str = "left") -> int:
        """
        Find nearest word boundary from position

        Args:
            text: Source text
            pos: Starting position
            direction: 'left' or 'right'

        Returns:
            Position of word boundary
        """
        if direction == "left":
            # Look left for space or start
            while pos > 0 and not text[pos - 1].isspace():
                pos -= 1
        else:  # right
            # Look right for space or end
            while pos < len(text) and not text[pos].isspace():
                pos += 1

        return pos

    def _merge_overlapping_snippets(
        self,
        text: str,
        snippets: List[Snippet],
    ) -> List[Snippet]:
        """
        Merge snippets that overlap or are very close

        Args:
            text: Original text (for re-extracting merged regions)
            snippets: List of snippets to merge

        Returns:
            List of merged snippets
        """
        if not snippets:
            return []

        # Sort by start position
        snippets = sorted(snippets, key=lambda s: s.start_pos)

        merged = []
        current = snippets[0]

        for next_snippet in snippets[1:]:
            if current.overlaps_with(next_snippet, tolerance=20):
                # Merge with current
                current = current.merge_with(next_snippet)
                # Re-extract text from merged region
                current.text = text[current.start_pos : current.end_pos].strip()
            else:
                # Add current to results and move to next
                merged.append(current)
                current = next_snippet

        # Don't forget the last one
        merged.append(current)

        return merged

    def _score_snippets(
        self,
        snippets: List[Snippet],
        keywords: Set[str],
    ) -> List[Snippet]:
        """
        Score snippets by relevance

        Factors:
        - Number of unique keywords matched
        - Keyword density in snippet
        - Position in document (earlier is slightly better)

        Args:
            snippets: List of snippets to score
            keywords: All keywords from query

        Returns:
            Snippets with updated scores
        """
        total_keywords = len(keywords)

        for snippet in snippets:
            # Factor 1: Coverage - what fraction of keywords appear
            coverage = (
                len(snippet.matched_keywords) / total_keywords
                if total_keywords > 0
                else 0
            )

            # Factor 2: Density - how concentrated are keywords
            snippet_tokens = tokenize_for_bm25(snippet.text)
            matched_token_count = sum(
                1 for token in snippet_tokens if token in snippet.matched_keywords
            )
            density = matched_token_count / len(snippet_tokens) if snippet_tokens else 0

            # Factor 3: Position bonus (slight preference for earlier snippets)
            # Normalize by assuming text is up to 10000 chars
            position_score = 1.0 - (snippet.start_pos / 10000.0)
            position_score = max(0.7, position_score)  # Floor at 0.7

            # Combine factors (weighted)
            snippet.score = (
                coverage * 0.5
                + density * 0.3  # 50% weight on keyword coverage
                + position_score  # 30% weight on keyword density
                * 0.2  # 20% weight on position
            )

        return snippets

    def _highlight_keywords(
        self,
        text: str,
        keywords: Set[str],
    ) -> str:
        """
        Highlight keywords in text

        Args:
            text: Text to highlight in
            keywords: Keywords to highlight

        Returns:
            Text with keywords highlighted
        """
        if not keywords:
            return text

        # Sort keywords by length (longest first) to avoid partial replacements
        sorted_keywords = sorted(keywords, key=len, reverse=True)

        highlighted = text

        for keyword in sorted_keywords:
            # Use case-insensitive replacement with word boundaries
            pattern = re.compile(r"\b(" + re.escape(keyword) + r")\b", re.IGNORECASE)

            # Replace with highlighted version
            highlighted = pattern.sub(
                lambda m: self.highlight_template.format(keyword=m.group(0)),
                highlighted,
            )

        return highlighted


# Singleton instance
_snippet_extractor_instance = None


def get_snippet_extractor() -> SnippetExtractor:
    """
    Get singleton SnippetExtractor instance

    Returns:
        SnippetExtractor instance
    """
    global _snippet_extractor_instance

    if _snippet_extractor_instance is None:
        _snippet_extractor_instance = SnippetExtractor()

    return _snippet_extractor_instance
