"""
Query Type Detector Module

Classifies query type for adaptive retrieval strategies
"""

from typing import List

from loguru import logger


class QueryTypeDetector:
    """
    Classify query type for adaptive retrieval

    Query types:
    - tag_only: Pure tag lookup queries
    - mixed: Tag + parameter queries
    - visual: Visual/descriptive queries
    - semantic: General semantic queries
    """

    def __init__(self):
        """Initialize query type detector"""
        # Visual query keywords
        self.visual_keywords = [
            "diagram",
            "vẽ",
            "layout",
            "schematic",
            "nhiều ống",
            "kết nối",
            "đường ống",
            "hình",
            "bản vẽ",
            "drawing",
        ]

        # Parameter keywords
        self.param_keywords = [
            "pressure",
            "áp suất",
            "temperature",
            "nhiệt độ",
            "flow",
            "lưu lượng",
            "bar",
            "psi",
            "°c",
            "°f",
            "kg/h",
            "m³/h",
            "m3/h",
            "mpa",
            "kpa",
        ]

        logger.debug("QueryTypeDetector initialized")

    def detect(self, query: str, detected_tags: List[str] = None) -> str:
        """
        Detect query type for adaptive retrieval

        Args:
            query: Query text
            detected_tags: List of detected equipment tags

        Returns:
            Query type: "tag_only", "mixed", "visual", or "semantic"
        """
        query_lower = query.lower()

        # Tag-only: pure tag lookup (short queries with tags)
        if detected_tags and len(query.split()) <= 3:
            logger.debug("Query type: tag_only")
            return "tag_only"

        # Visual: descriptive queries about visuals
        if any(kw in query_lower for kw in self.visual_keywords):
            logger.debug("Query type: visual")
            return "visual"

        # Mixed: tags + parameters
        if detected_tags and any(kw in query_lower for kw in self.param_keywords):
            logger.debug("Query type: mixed")
            return "mixed"

        # Default: semantic search
        logger.debug("Query type: semantic")
        return "semantic"


# Export main class
__all__ = ["QueryTypeDetector"]
