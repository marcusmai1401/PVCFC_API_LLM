"""
Query-Time Equipment Enhancer
Tier 1: Fast keyword boosting without requiring metadata in database
"""
import re
from typing import List, Optional, Tuple

from loguru import logger


class QueryTimeEnhancer:
    """
    Enhance queries at query-time to improve equipment-specific retrieval
    WITHOUT requiring metadata extraction during ingestion
    """

    # Equipment tag patterns
    TAG_PATTERNS = [
        r"\b([A-Z]{2,3}\d{5})\b",  # KT06101, HCD025
        r"\b([A-Z]{1,2}[- ]?\d{2}[- ]?\d{3})\b",  # K-06-101, K 06 101
        r"\b(\d{3}_[A-Z0-9\-]+)\b",  # 003_3N4-S4274345
        r"\b([A-Z]{2}\d{4,6})\b",  # TE0256, BAO01234
    ]

    # Document type keywords
    DOC_TYPE_KEYWORDS = {
        "manual": ["manual", "operation", "maintenance", "operating", "o&m"],
        "datasheet": ["datasheet", "data sheet", "specification", "spec"],
        "performance": ["performance", "curve", "characteristic"],
        "drawing": ["drawing", "diagram", "p&id", "pid", "piping"],
        "instrument_list": ["instrument list", "instrument", "tag list"],
    }

    def __init__(self, boost_factor: int = 3):
        """
        Args:
            boost_factor: How many times to repeat equipment tag for boosting
        """
        self.boost_factor = boost_factor

    def enhance(self, query: str) -> Tuple[str, dict]:
        """
        Enhance query with equipment tag boosting

        Args:
            query: Original user query

        Returns:
            (enhanced_query, metadata)
            - enhanced_query: Query with boosted equipment tags
            - metadata: Extracted info (tags, doc_type, etc.)
        """
        metadata = {
            "equipment_tags": [],
            "doc_type": None,
            "enhancement_applied": False,
            "variant_count": 0,
        }

        # Extract equipment tags
        tags = self._extract_equipment_tags(query)
        metadata["equipment_tags"] = tags

        # Extract document type
        doc_type = self._extract_doc_type(query)
        metadata["doc_type"] = doc_type

        # Build enhanced query
        if tags:
            # Generate simple tag variants (no reindexing required)
            boost_terms: List[str] = []
            for t in tags:
                variants = self._generate_tag_variants(t)
                metadata["variant_count"] += len(variants)
                # Repeat variants by boost_factor
                for _ in range(self.boost_factor):
                    boost_terms.extend(variants)
            tag_boost = " ".join(boost_terms)
            enhanced_query = f"{query} {tag_boost}".strip()
            metadata["enhancement_applied"] = True

            logger.info(
                f"Query enhanced: extracted {len(tags)} tag(s), variants={metadata['variant_count']}, "
                f"doc_type={doc_type}, boost_factor={self.boost_factor}"
            )
        else:
            enhanced_query = query
            logger.debug("No equipment tags found, query not enhanced")

        return enhanced_query, metadata

    def _extract_equipment_tags(self, text: str) -> List[str]:
        """Extract equipment tags from text using patterns"""
        tags = set()

        for pattern in self.TAG_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Normalize: remove spaces/hyphens, uppercase
                normalized = re.sub(r"[-\s]", "", match).upper()
                tags.add(normalized)

        return list(tags)

    def _extract_doc_type(self, query: str) -> Optional[str]:
        """Extract document type from query"""
        query_lower = query.lower()

        for doc_type, keywords in self.DOC_TYPE_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                return doc_type

        return None

    def _generate_tag_variants(self, tag: str) -> List[str]:
        """Generate simple query-time variants for a tag without requiring metadata.
        Variants include:
        - base (no separators), e.g., KT06101
        - hyphen between alpha/digit groups, e.g., KT-06101 or HCD-025
        - space between alpha/digit groups, e.g., KT 06101 or HCD 025
        """
        base = re.sub(r"[-\s]", "", tag).upper()
        # Split into alpha/digit groups
        parts = re.findall(r"[A-Z]+|\d+", base)
        variants = {base}
        if len(parts) >= 2:
            variants.add("-".join(parts))
            variants.add(" ".join(parts))
        return list(variants)

    def should_filter_by_tag(self, metadata: dict) -> bool:
        """
        Determine if we should apply post-retrieval tag filtering

        Returns:
            True if we have high-confidence equipment tags
        """
        tags = metadata.get("equipment_tags", [])

        # Only filter if we have exactly 1-2 clear tags
        # (too many tags might indicate noise)
        return 1 <= len(tags) <= 2

    def post_filter_results(
        self, results: List, metadata: dict, min_confidence: float = 0.3
    ) -> List:
        """
        Post-filter retrieval results by equipment tag content match

        Args:
            results: Retrieval results
            metadata: Enhancement metadata from enhance()
            min_confidence: Minimum score to keep (relative to top score)

        Returns:
            Filtered results
        """
        if not self.should_filter_by_tag(metadata):
            logger.debug("Skipping post-filtering (no confident tags)")
            return results

        tags = metadata["equipment_tags"]

        # Precompile flexible patterns allowing optional hyphens/spaces between characters
        def _flex_pattern(tag: str) -> "re.Pattern[str]":
            base = re.sub(r"[-\s]", "", tag).lower()
            # Insert optional [-\s]* between each character of base
            pattern = "".join([re.escape(ch) + r"[-\s]*" for ch in base])
            # Remove trailing optional separator
            if pattern.endswith(r"[-\s]*"):
                pattern = pattern[: -len(r"[-\s]*")]
            return re.compile(pattern, re.IGNORECASE)

        patterns = [_flex_pattern(t) for t in tags]

        # Filter: keep results containing ANY of the tag patterns
        filtered = []
        for result in results:
            # Combine text and identifiers for matching
            text_lower = (
                f"{getattr(result, 'text', '')} {getattr(result, 'doc_id', '')}"
            ).lower()
            if any(p.search(text_lower) for p in patterns):
                filtered.append(result)

        if not filtered:
            logger.warning(
                f"Post-filtering removed all results for tags {tags}! "
                f"Falling back to top unfiltered results"
            )
            # Fallback: return top results anyway
            return results[:5]

        logger.info(
            f"Post-filtering: {len(results)} → {len(filtered)} results "
            f"(kept results containing {tags})"
        )

        return filtered


class LLMReranker:
    """
    Tier 2: LLM-based reranking for low-confidence cases
    """

    def __init__(self, confidence_threshold: float = 0.7):
        """
        Args:
            confidence_threshold: Use LLM rerank if top result < this score
        """
        self.confidence_threshold = confidence_threshold

    def should_rerank(self, results: List, metadata: dict) -> bool:
        """
        Determine if LLM reranking is needed

        Returns:
            True if we should use LLM to improve ranking
        """
        if not results:
            return False

        # Check if Tier 1 produced confident results
        top_score = results[0].score if hasattr(results[0], "score") else 1.0

        # Need rerank if:
        # 1. Top score is low
        # 2. OR we have equipment tags but uncertain results
        has_tags = len(metadata.get("equipment_tags", [])) > 0
        low_confidence = top_score < self.confidence_threshold

        return has_tags and low_confidence

    async def rerank(
        self, query: str, results: List, metadata: dict, max_results: int = 10
    ) -> List:
        """
        Use LLM to rerank results based on equipment relevance

        Args:
            query: User query
            results: Current retrieval results
            metadata: Enhancement metadata
            max_results: Max number of results to rerank (for speed)

        Returns:
            Reranked results
        """
        from app.services.llm_client import get_client

        equipment_tags = metadata.get("equipment_tags", [])
        if not equipment_tags:
            logger.debug("No equipment tags, skipping LLM rerank")
            return results

        logger.info(
            f"LLM reranking {len(results[:max_results])} results "
            f"for equipment: {equipment_tags}"
        )

        # Prepare LLM client
        llm = get_client(model_tier="light")

        # Score each result
        scored_results = []
        for result in results[:max_results]:
            # Ask LLM: is this doc about the equipment?
            prompt = f"""Question: Is this document primarily about equipment {', '.join(equipment_tags)}?

Document ID: {result.doc_id}
Content sample: {result.text[:300]}...

Answer with just "yes" or "no"."""

            try:
                response = llm.generate(prompt, max_tokens=10, temperature=0)
                answer = response.lower().strip()

                # Boost or penalize based on LLM judgment
                if "yes" in answer:
                    boost = 2.0
                    logger.debug(f"LLM: {result.doc_id[:50]} → YES (boost 2x)")
                else:
                    boost = 0.3
                    logger.debug(f"LLM: {result.doc_id[:50]} → NO (penalize 0.3x)")

                result.score = getattr(result, "score", 1.0) * boost
                scored_results.append(result)

            except Exception as e:
                logger.warning(f"LLM rerank failed for {result.doc_id}: {e}")
                scored_results.append(result)  # Keep original score

        # Add remaining results without LLM (to save cost)
        scored_results.extend(results[max_results:])

        # Re-sort by adjusted score
        scored_results.sort(key=lambda x: getattr(x, "score", 0), reverse=True)

        logger.info(
            f"LLM rerank complete: top result = {scored_results[0].doc_id[:60]}"
        )

        return scored_results
