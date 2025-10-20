"""
P&ID Context Validator
Prevents false positives by detecting semantic vs P&ID context

This module ensures queries like "procedure 5153" or "What is PI?"
are NOT incorrectly routed to P&ID search.
"""

from typing import Dict, List


class PIDContextValidator:
    """
    Validates if query is truly P&ID-related or semantic with coincidental numbers

    False positive examples:
    - "procedure 5153" → Has context word "procedure"
    - "What is 2024 plan?" → Has semantic intent
    - "How PI works?" → PI is PREFIX but query is semantic
    - "PI là gì?" → Vietnamese semantic question

    True positive examples:
    - "5153" → Pure SUFFIX
    - "04 5153" → Valid components
    - "áp suất của 5153" → Has P&ID keyword
    """

    # Semantic context indicators (suggest NOT P&ID query)
    SEMANTIC_KEYWORDS = [
        # English question words
        "how",
        "what",
        "why",
        "when",
        "where",
        "who",
        "which",
        # English verbs/actions
        "explain",
        "describe",
        "tell",
        "show",
        "define",
        # Process/procedure related
        "procedure",
        "process",
        "step",
        "method",
        "way",
        # Documentation
        "manual",
        "guide",
        "instruction",
        "handbook",
        "documentation",
        # General semantic
        "meaning",
        "definition",
        "concept",
        "theory",
        "principle",
        "calculate",
        "compute",
        "formula",
        # Vietnamese question words
        "làm sao",
        "thế nào",
        "là gì",
        "tại sao",
        "ở đâu",
        "khi nào",
        # Vietnamese verbs
        "giải thích",
        "mô tả",
        "cho biết",
        "hướng dẫn",
        # Vietnamese process
        "quy trình",
        "qui trình",
        "cách",
        "phương pháp",
        # Vietnamese general
        "nghĩa là",
        "định nghĩa",
        "ý nghĩa",
    ]

    # P&ID context indicators (suggest IS P&ID query)
    PID_KEYWORDS = [
        # Measurement types (English)
        "pressure",
        "temperature",
        "flow",
        "level",
        "speed",
        # Instrument types (English)
        "tag",
        "instrument",
        "sensor",
        "transmitter",
        "indicator",
        "controller",
        "alarm",
        "switch",
        # Equipment (English)
        "valve",
        "pump",
        "compressor",
        "vessel",
        "tank",
        "exchanger",
        # P&ID specific (English)
        "p&id",
        "pid",
        "piping",
        "instrumentation",
        # Units (English/universal)
        "bar",
        "psi",
        "mpa",
        "kpa",
        "°c",
        "°f",
        "kg/h",
        "m3/h",
        "m³/h",
        # Measurement types (Vietnamese)
        "áp suất",
        "ap suat",
        "nhiệt độ",
        "nhiet do",
        "lưu lượng",
        "luu luong",
        "mức",
        "muc",
        "tốc độ",
        "toc do",
        # Instrument types (Vietnamese)
        "cảm biến",
        "cam bien",
        "thiết bị",
        "thiet bi",
        "đồng hồ",
        "dong ho",
        # Equipment (Vietnamese)
        "van",
        "bơm",
        "bom",
        "máy nén",
        "may nen",
        "bình",
        "binh",
        # Actions (Vietnamese)
        "đo",
        "do",
        "điều khiển",
        "dieu khien",
        "báo động",
        "bao dong",
    ]

    def validate(self, query: str, detected_strategy: str) -> Dict:
        """
        Validate if detected P&ID strategy is appropriate

        Multi-layer validation:
        1. Count semantic vs P&ID keywords
        2. Check query length (for SUFFIX-only)
        3. Calculate confidence score

        Args:
            query: Original user query
            detected_strategy: Strategy from PIDQueryEnhancer
                              (suffix_search, component_search, tag_focused)

        Returns:
            Dictionary with validation result:
            {
                "is_valid": bool - Whether to use P&ID search
                "confidence": float - Confidence score (0-1)
                "reason": str - Human-readable reason
                "fallback_to_semantic": bool - Should fallback
            }
        """
        query_lower = query.lower()
        query_clean = query.strip()

        # Count semantic indicators
        semantic_count = sum(1 for kw in self.SEMANTIC_KEYWORDS if kw in query_lower)

        # Count P&ID indicators
        pid_count = sum(1 for kw in self.PID_KEYWORDS if kw in query_lower)

        # Strategy-specific validation
        if detected_strategy == "suffix_search":
            return self._validate_suffix_search(
                query_clean, query_lower, semantic_count, pid_count
            )

        elif detected_strategy == "component_search":
            return self._validate_component_search(
                query_clean, query_lower, semantic_count, pid_count
            )

        elif detected_strategy == "tag_focused":
            # Existing strategy - more lenient
            return self._validate_tag_focused(
                query_clean, query_lower, semantic_count, pid_count
            )

        # Unknown strategy - reject
        return {
            "is_valid": False,
            "confidence": 0.0,
            "reason": f"Unknown strategy: {detected_strategy}",
            "fallback_to_semantic": True,
        }

    def _validate_suffix_search(
        self, query_clean: str, query_lower: str, semantic_count: int, pid_count: int
    ) -> Dict:
        """
        Validate SUFFIX-only search (very strict)

        SUFFIX queries should be:
        - Pure digits (3-5 chars)
        - No semantic context
        - Short (<=10 chars)
        - Not empty
        """
        # Rule 0: Empty query → reject
        if not query_clean or len(query_clean) == 0:
            return {
                "is_valid": False,
                "confidence": 0.0,
                "reason": "Empty query",
                "fallback_to_semantic": True,
            }

        # Rule 1: ANY semantic keywords → reject
        if semantic_count > 0:
            return {
                "is_valid": False,
                "confidence": 0.2,
                "reason": f"Semantic context detected ({semantic_count} keywords)",
                "fallback_to_semantic": True,
            }

        # Rule 2: Query too long → probably not pure tag
        if len(query_clean) > 10:
            return {
                "is_valid": False,
                "confidence": 0.3,
                "reason": f"Query too long ({len(query_clean)} chars) for pure SUFFIX",
                "fallback_to_semantic": True,
            }

        # Rule 3: Has P&ID keywords → boost confidence
        if pid_count > 0:
            return {
                "is_valid": True,
                "confidence": 0.95,
                "reason": f"Pure digits with P&ID context ({pid_count} keywords)",
                "fallback_to_semantic": False,
            }

        # Rule 4: Pure digits, no context → likely P&ID
        return {
            "is_valid": True,
            "confidence": 0.9,
            "reason": "Pure digits query, no semantic context",
            "fallback_to_semantic": False,
        }

    def _validate_component_search(
        self, query_clean: str, query_lower: str, semantic_count: int, pid_count: int
    ) -> Dict:
        """
        Validate component search (moderate strictness)

        Component queries can have some context,
        but semantic intent should not dominate
        """
        # Rule 1: More semantic than P&ID indicators → reject
        if semantic_count > 0 and semantic_count > pid_count:
            return {
                "is_valid": False,
                "confidence": 0.4,
                "reason": f"More semantic ({semantic_count}) than P&ID ({pid_count}) keywords",
                "fallback_to_semantic": True,
            }

        # Rule 2: Has P&ID context → accept with high confidence
        if pid_count > 0:
            return {
                "is_valid": True,
                "confidence": 0.8,
                "reason": f"P&ID context present ({pid_count} keywords)",
                "fallback_to_semantic": False,
            }

        # Rule 3: No semantic context → accept with moderate confidence
        if semantic_count == 0:
            return {
                "is_valid": True,
                "confidence": 0.7,
                "reason": "Valid components, no semantic keywords",
                "fallback_to_semantic": False,
            }

        # Rule 4: Equal semantic and P&ID → accept with lower confidence
        return {
            "is_valid": True,
            "confidence": 0.6,
            "reason": f"Balanced context (sem={semantic_count}, pid={pid_count})",
            "fallback_to_semantic": False,
        }

    def _validate_tag_focused(
        self, query_clean: str, query_lower: str, semantic_count: int, pid_count: int
    ) -> Dict:
        """
        Validate tag-focused search (moderate - improved safety)

        More strict than before to prevent false positives,
        but still lenient for backward compatibility
        """
        # If very heavy semantic context (>=3 keywords) → reject even with P&ID
        # This prevents "How to explain the procedure of tag 5153?" from being P&ID
        if semantic_count >= 3:
            return {
                "is_valid": False,
                "confidence": 0.2,
                "reason": f"Heavy semantic context ({semantic_count} keywords)",
                "fallback_to_semantic": True,
            }

        # If has P&ID context (and not heavy semantic) → accept
        if pid_count > 0:
            return {
                "is_valid": True,
                "confidence": 0.85,
                "reason": "Tag detected with P&ID context",
                "fallback_to_semantic": False,
            }

        # If moderate semantic (1-2 keywords) → accept with lower confidence
        if 1 <= semantic_count < 3:
            return {
                "is_valid": True,
                "confidence": 0.5,
                "reason": f"Tag detected with moderate semantic context ({semantic_count} keywords)",
                "fallback_to_semantic": False,
            }

        # Default: accept (backward compatible, no semantic keywords)
        return {
            "is_valid": True,
            "confidence": 0.7,
            "reason": "Tag pattern detected, minimal semantic context",
            "fallback_to_semantic": False,
        }


def should_fallback_on_empty(pid_results: List, min_results: int = 1) -> bool:
    """
    Check if should fallback to semantic when P&ID search returns few/no results

    Args:
        pid_results: Results from P&ID search (list or dict)
        min_results: Minimum results to consider valid (default: 1)

    Returns:
        True if should fallback to semantic search

    Examples:
        >>> should_fallback_on_empty([])
        True
        >>> should_fallback_on_empty([{"tag": "04 IS 501"}])
        False
        >>> should_fallback_on_empty([], min_results=5)
        True
    """
    # Handle None
    if pid_results is None:
        return True

    # Handle dict (grouped results)
    if isinstance(pid_results, dict):
        # Check total_tags field
        if "total_tags" in pid_results:
            return pid_results["total_tags"] < min_results
        # Check groups
        if "groups" in pid_results:
            total = sum(len(g.get("tags", [])) for g in pid_results["groups"])
            return total < min_results
        # Unknown dict format
        return True

    # Handle list
    if isinstance(pid_results, list):
        return len(pid_results) < min_results

    # Unknown type
    return True


__all__ = ["PIDContextValidator", "should_fallback_on_empty"]
