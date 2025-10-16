"""
P&ID Query Enhancer Module

Detects equipment tags and enhances queries for P&ID-specific retrieval
"""

from typing import Dict, List

from loguru import logger

from app.rag.normalizers.tag_normalizer import TagNormalizer


class PIDQueryEnhancer:
    """
    Detect equipment tags and enhance query for P&ID retrieval

    Features:
    - Tag detection using TagNormalizer
    - Tag variant generation (E04217, E-04217, e04217, etc.)
    - Equipment type inference from tag prefix
    - Query type classification (tag_only, mixed, visual, semantic)
    """

    def __init__(self):
        """Initialize PID query enhancer"""
        self.tag_normalizer = TagNormalizer()

        # Equipment type mapping (from tag prefix)
        self.TYPE_MAP = {
            "E": "heat exchanger",
            "H": "heat exchanger",
            "P": "pump",
            "K": "compressor",
            "C": "compressor",
            "V": "vessel",
            "T": "tank",
            "D": "drum",
            "S": "separator",
            "R": "reactor",
            "F": "furnace",
            "B": "boiler",
        }

        logger.debug("PIDQueryEnhancer initialized")

    def enhance(self, query: str) -> Dict:
        """
        Enhance query with P&ID-specific analysis

        Args:
            query: Original user query

        Returns:
            Enhanced query dict with:
            - strategy: "tag_focused" or "semantic"
            - original: original query text
            - tags: detected equipment tags
            - variants: tag variants for fuzzy matching
            - equipment_types: inferred equipment types
            - query_type: tag_only, mixed, visual, or semantic
        """
        # Extract tags using existing TagNormalizer
        tag_results = self.tag_normalizer.extract_tags(query)

        if not tag_results:
            logger.debug(f"No tags detected in query: {query[:50]}")
            return {"strategy": "semantic", "original": query}

        # Parse tags
        tags = [t["normalized"] for t in tag_results]
        logger.info(f"Detected tags: {tags}")

        # Generate variants (max 4 per tag)
        variants = self._generate_variants(tags)

        # Infer equipment types
        equipment_types = [self.TYPE_MAP.get(t[0], "") for t in tags if t]
        equipment_types = [t for t in equipment_types if t]  # Remove empty

        # Detect query type
        query_type = self._detect_query_type(query, tags)

        logger.info(
            f"Query enhanced - strategy: tag_focused, type: {query_type}, "
            f"tags: {tags}, equipment_types: {equipment_types}"
        )

        return {
            "strategy": "tag_focused",
            "original": query,
            "tags": tags,
            "variants": variants,
            "equipment_types": equipment_types,
            "query_type": query_type,
        }

    def _generate_variants(self, tags: List[str]) -> Dict[str, List[str]]:
        """
        Generate tag variants for fuzzy matching

        For each tag (e.g., E04217), generates:
        - E04217 (original)
        - E-04217 (with hyphen)
        - E 04217 (with space)
        - e04217 (lowercase)

        Args:
            tags: List of normalized tags

        Returns:
            Dict mapping tag to list of variants
        """
        variants = {}

        for tag in tags:
            tag_variants = [
                tag,  # E04217
                tag.replace("-", ""),  # E04217 (if was E-04217)
                tag.lower(),  # e04217
            ]

            # Add hyphen variant if not already hyphenated
            if "-" not in tag and len(tag) > 1:
                # Insert hyphen after first letter: E04217 → E-04217
                hyphenated = tag[0] + "-" + tag[1:]
                tag_variants.append(hyphenated)

            # Add space variant
            if len(tag) > 1:
                spaced = tag[0] + " " + tag[1:]
                tag_variants.append(spaced)

            # Deduplicate while preserving order
            seen = set()
            unique_variants = []
            for v in tag_variants:
                if v not in seen:
                    seen.add(v)
                    unique_variants.append(v)

            # Limit to 4 variants
            variants[tag] = unique_variants[:4]

        logger.debug(f"Generated variants: {variants}")
        return variants

    def _detect_query_type(self, query: str, tags: List[str]) -> str:
        """
        Detect query type for adaptive retrieval

        Types:
        - tag_only: Pure tag lookup (e.g., "E04217", "E04217 ở đâu")
        - mixed: Tag + parameters (e.g., "áp suất của E04217")
        - visual: Visual/descriptive (e.g., "diagram nhiều ống")
        - semantic: General query (fallback)

        Args:
            query: Query text
            tags: Detected tags

        Returns:
            Query type string
        """
        query_lower = query.lower()

        # Pure tag (1-3 words, has tags)
        if tags and len(query.split()) <= 3:
            logger.debug("Query type: tag_only (short query with tags)")
            return "tag_only"

        # Visual descriptive
        visual_keywords = [
            "diagram",
            "vẽ",
            "layout",
            "schematic",
            "nhiều ống",
            "kết nối",
            "đường ống",
            "hình",
            "bản vẽ",
        ]
        if any(kw in query_lower for kw in visual_keywords):
            logger.debug("Query type: visual (visual keywords detected)")
            return "visual"

        # Mixed (has tags + parameters)
        param_keywords = [
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
        ]
        if tags and any(kw in query_lower for kw in param_keywords):
            logger.debug("Query type: mixed (tags + parameters)")
            return "mixed"

        # Default
        logger.debug("Query type: semantic (default)")
        return "semantic"


# Export main class
__all__ = ["PIDQueryEnhancer"]
