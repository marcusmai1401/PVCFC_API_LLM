"""
P&ID Query Enhancer Module

Detects equipment tags and enhances queries for P&ID-specific retrieval

Updated with:
- SUFFIX-only query detection (e.g., "5153")
- Component-based query parsing (e.g., "04 5153", "PAHH 5153")
- Multi-prefix ambiguity handling
"""

import re
from typing import Dict, List, Optional

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
            - strategy: "suffix_search", "component_search", "tag_focused", or "semantic"
            - original: original query text
            - suffix/components/tags: depending on strategy
            - variants: tag variants for fuzzy matching
            - equipment_types: inferred equipment types
            - query_type: tag_only, mixed, visual, semantic, suffix_only, component_query
        """
        # NEW: Check SUFFIX-only query first (e.g., "5153", "501")
        suffix = self._detect_suffix_only_query(query)
        if suffix:
            logger.info(f"Detected SUFFIX-only query: {suffix}")
            return {
                "strategy": "suffix_search",
                "original": query,
                "suffix": suffix,
                "query_type": "suffix_only",
                "warning": "Multiple tags may match this suffix. Consider adding PREFIX or UNIT for specificity.",
            }

        # NEW: Try component-based parsing (e.g., "04 5153", "PAHH 5153", "04 PAHH")
        components = self._parse_query_components(query)
        if components:
            logger.info(f"Detected component query: {components}")
            return {
                "strategy": "component_search",
                "original": query,
                "components": components,  # {unit?, prefix?, suffix?}
                "query_type": "component_query",
            }

        # Existing: Extract tags using TagNormalizer
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

    def _detect_suffix_only_query(self, query: str) -> Optional[str]:
        """
        Detect if query is pure SUFFIX (3-5 digits only)

        Examples:
            "5153" → "5153"
            "501" → "501"
            "22076" → "22076"

        Args:
            query: Query string

        Returns:
            Suffix string if detected, None otherwise
        """
        query_clean = query.strip()

        # Match 3-5 digits only
        if re.match(r"^\d{3,5}$", query_clean):
            return query_clean

        return None

    def _parse_query_components(self, query: str) -> Optional[Dict]:
        """
        Parse query into components for flexible search

        Examples:
            "04 5153" → {unit: "04", suffix: "5153"}
            "PAHH 5153" → {prefix: "PAHH", suffix: "5153"}
            "04 PAHH" → {unit: "04", prefix: "PAHH"}
            "04 PAHH 5153" → {unit: "04", prefix: "PAHH", suffix: "5153"}

        Args:
            query: Query string

        Returns:
            Dict with detected components or None
        """
        # Try to use TagNormalizer's parse_tag_components first
        parsed = self.tag_normalizer.parse_tag_components(query)
        if parsed:
            # Build components dict from parsed result
            components = {}
            if parsed.get("unit"):
                components["unit"] = parsed["unit"]
            if parsed.get("prefix"):
                components["prefix"] = parsed["prefix"]
            if parsed.get("suffix"):
                components["suffix"] = parsed["suffix"]
            if parsed.get("variant"):
                components["variant"] = parsed["variant"]

            logger.debug(f"Parsed components from full tag: {components}")
            return components if components else None

        # Fallback: Token-based parsing for partial queries
        tokens = query.upper().strip().split()
        components = {}

        for token in tokens:
            # Check if UNIT (1-3 digits)
            if re.match(r"^\d{1,3}$", token):
                # Disambiguate: is it UNIT or SUFFIX?
                # SUFFIX is 3-5 digits, UNIT is 1-3 digits
                # If we don't have a suffix yet and len >= 3, it might be suffix
                if len(token) >= 3 and "suffix" not in components:
                    components["suffix"] = token
                elif "suffix" not in components:
                    components["unit"] = token

            # Check if SUFFIX (3-5 digits) - more explicit
            elif re.match(r"^\d{3,5}$", token) and "suffix" not in components:
                components["suffix"] = token

            # Check if PREFIX (2-6 letters)
            elif re.match(r"^[A-Z]{2,6}$", token):
                components["prefix"] = token

            # Check if VARIANT (single letter) - only if we already have suffix
            elif re.match(r"^[A-Z]$", token) and "suffix" in components:
                components["variant"] = token

        if not components:
            return None

        logger.debug(f"Parsed components from tokens: {components}")
        return components


# Export main class
__all__ = ["PIDQueryEnhancer"]
