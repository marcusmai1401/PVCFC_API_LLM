"""
Stage-2 Domain-Specific Reranker

Applies task-specific domain logic to boost relevant results.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DomainReranker:
    """
    Stage-2 reranker with domain-specific boost factors.

    Boosts based on:
    - Equipment tag matches
    - Document type relevance
    - P&ID diagram content
    - Recent documents
    - Header matches
    - Table content
    """

    def __init__(
        self,
        equipment_tag_boost: float = 0.2,
        doc_type_boost: float = 0.15,
        pid_boost: float = 0.1,
        recent_doc_boost: float = 0.05,
        header_match_boost: float = 0.08,
        table_boost: float = 0.12,
        recent_threshold_months: int = 6,
    ):
        """
        Initialize domain reranker.

        Args:
            equipment_tag_boost: Boost for equipment tag matches
            doc_type_boost: Boost for relevant document types
            pid_boost: Boost for P&ID diagrams
            recent_doc_boost: Boost for recent documents
            header_match_boost: Boost for header matches
            table_boost: Boost for table content
            recent_threshold_months: Threshold for "recent" documents
        """
        self.equipment_tag_boost = equipment_tag_boost
        self.doc_type_boost = doc_type_boost
        self.pid_boost = pid_boost
        self.recent_doc_boost = recent_doc_boost
        self.header_match_boost = header_match_boost
        self.table_boost = table_boost
        self.recent_threshold_months = recent_threshold_months

        # Query intent keywords
        self.intent_keywords = {
            "torque": ["datasheet", "specification", "mechanical"],
            "pressure": ["datasheet", "specification", "operating"],
            "diagram": ["pid", "drawing", "schematic"],
            "procedure": ["procedure", "manual", "guide"],
            "specification": ["datasheet", "specification", "technical"],
        }

        logger.info("DomainReranker initialized")

    def rerank(
        self, query: str, results: List[Dict[str, Any]], top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply domain-specific reranking.

        Args:
            query: Search query
            results: Results with 'rerank_score' from Stage-1
            top_k: Number of top results to return

        Returns:
            Reranked results with 'final_score' and 'boost_breakdown'
        """
        if not results:
            return []

        # Extract query features
        query_tags = self._extract_equipment_tags(query)
        query_intent = self._classify_query_intent(query)
        query_terms = query.lower().split()

        reranked_results = []

        for result in results:
            # Start with Stage-1 score (or original score if not available)
            base_score = result.get("rerank_score", result.get("score", 0.0))

            # Calculate boosts
            boosts = {}
            total_boost = 0.0

            # 1. Equipment tag match
            chunk_tags = result.get("metadata", {}).get("equipment_tags", [])
            if chunk_tags and query_tags:
                matches = set(query_tags) & set(chunk_tags)
                if matches:
                    boost = self.equipment_tag_boost
                    boosts["equipment_tag"] = boost
                    total_boost += boost
                    logger.debug(f"Equipment tag match: {matches}")

            # 2. Document type relevance
            doc_type = result.get("metadata", {}).get("doc_type", "").lower()
            if query_intent and doc_type:
                if self._is_relevant_doc_type(query_intent, doc_type):
                    boost = self.doc_type_boost
                    boosts["doc_type"] = boost
                    total_boost += boost

            # 3. P&ID diagram boost
            chunk_type = result.get("metadata", {}).get("chunk_type", "")
            if chunk_type == "pid":
                boost = self.pid_boost
                boosts["pid_diagram"] = boost
                total_boost += boost

            # 4. Recent document boost
            doc_age = self._get_document_age_months(result.get("metadata", {}))
            if doc_age is not None and doc_age < self.recent_threshold_months:
                boost = self.recent_doc_boost
                boosts["recent_doc"] = boost
                total_boost += boost

            # 5. Header match boost
            headers = result.get("metadata", {}).get("headers", [])
            if headers and self._has_header_match(headers, query_terms):
                boost = self.header_match_boost
                boosts["header_match"] = boost
                total_boost += boost

            # 6. Table content boost
            if chunk_type == "table":
                boost = self.table_boost
                boosts["table_content"] = boost
                total_boost += boost

            # Calculate final score
            final_score = base_score + total_boost

            # Build result with boost breakdown
            reranked_result = result.copy()
            reranked_result["base_score"] = base_score
            reranked_result["boost_total"] = total_boost
            reranked_result["boost_breakdown"] = boosts
            reranked_result["final_score"] = final_score

            reranked_results.append(reranked_result)

        # Sort by final score
        reranked_results.sort(key=lambda x: x["final_score"], reverse=True)

        # Apply top_k
        if top_k:
            reranked_results = reranked_results[:top_k]

        logger.info(
            f"Domain reranked {len(results)} results "
            f"(top boost: +{reranked_results[0]['boost_total']:.2f})"
        )

        return reranked_results

    def _extract_equipment_tags(self, text: str) -> List[str]:
        """
        Extract equipment tags from text.

        Patterns: P-101, HX-202, C-301, etc.
        """
        pattern = r"\b[A-Z]{1,3}-\d{2,4}[A-Z]?\b"
        matches = re.findall(pattern, text)
        return list(set(matches))

    def _classify_query_intent(self, query: str) -> Optional[str]:
        """
        Classify query intent based on keywords.

        Returns:
            Intent category (torque, pressure, diagram, etc.) or None
        """
        query_lower = query.lower()

        for intent, keywords in self.intent_keywords.items():
            if intent in query_lower:
                return intent

        return None

    def _is_relevant_doc_type(self, intent: str, doc_type: str) -> bool:
        """
        Check if document type is relevant for query intent.
        """
        relevant_types = self.intent_keywords.get(intent, [])
        return any(dtype in doc_type for dtype in relevant_types)

    def _get_document_age_months(self, metadata: Dict[str, Any]) -> Optional[int]:
        """
        Get document age in months.

        Returns:
            Age in months or None if not available
        """
        # Try to get document date from metadata
        doc_date_str = metadata.get("document_date") or metadata.get("created_at")

        if not doc_date_str:
            return None

        try:
            # Parse date (ISO format)
            if isinstance(doc_date_str, str):
                doc_date = datetime.fromisoformat(doc_date_str.replace("Z", "+00:00"))
            else:
                doc_date = doc_date_str

            # Calculate age
            now = datetime.now(doc_date.tzinfo)
            age_days = (now - doc_date).days
            age_months = age_days // 30

            return age_months

        except Exception as e:
            logger.debug(f"Failed to parse document date: {e}")
            return None

    def _has_header_match(self, headers: List[str], query_terms: List[str]) -> bool:
        """
        Check if any header contains query terms.
        """
        for header in headers:
            header_lower = header.lower()
            if any(term in header_lower for term in query_terms):
                return True
        return False


class TwoTierReranker:
    """
    Combined 2-tier reranking pipeline.

    Stage-1: Vertex AI Semantic Reranker
    Stage-2: Domain-specific reranking
    """

    def __init__(
        self,
        stage1_reranker,
        stage2_reranker: Optional[DomainReranker] = None,
        stage1_enabled: bool = True,
        stage2_enabled: bool = True,
        stage1_top_k: int = 50,
        stage2_top_k: int = 10,
    ):
        """
        Initialize 2-tier reranker.

        Args:
            stage1_reranker: Stage-1 reranker (Vertex AI or mock)
            stage2_reranker: Stage-2 reranker (domain logic)
            stage1_enabled: Enable Stage-1 reranking
            stage2_enabled: Enable Stage-2 reranking
            stage1_top_k: Top-K for Stage-1
            stage2_top_k: Top-K for Stage-2
        """
        self.stage1_reranker = stage1_reranker
        self.stage2_reranker = stage2_reranker or DomainReranker()
        self.stage1_enabled = stage1_enabled
        self.stage2_enabled = stage2_enabled
        self.stage1_top_k = stage1_top_k
        self.stage2_top_k = stage2_top_k

        logger.info(
            f"TwoTierReranker initialized: "
            f"Stage-1={stage1_enabled}, Stage-2={stage2_enabled}"
        )

    def rerank(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply 2-tier reranking pipeline.

        Args:
            query: Search query
            results: Initial retrieval results

        Returns:
            Final reranked results
        """
        if not results:
            return []

        logger.info(
            f"Starting 2-tier reranking for query: '{query}' "
            f"({len(results)} initial results)"
        )

        # Stage-1: Semantic reranking
        if self.stage1_enabled:
            logger.info(f"[Stage-1] Semantic reranking (top {self.stage1_top_k})...")
            results = self.stage1_reranker.rerank(
                query, results, top_k=self.stage1_top_k
            )
            logger.info(f"[Stage-1] Complete: {len(results)} results")

        # Stage-2: Domain-specific reranking
        if self.stage2_enabled:
            logger.info(f"[Stage-2] Domain reranking (top {self.stage2_top_k})...")
            results = self.stage2_reranker.rerank(
                query, results, top_k=self.stage2_top_k
            )
            logger.info(f"[Stage-2] Complete: {len(results)} results")

        logger.info(
            f"2-tier reranking complete: {len(results)} final results "
            f"(top score: {results[0]['final_score']:.4f})"
        )

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get combined metrics from both stages."""
        metrics = {}

        if hasattr(self.stage1_reranker, "get_metrics"):
            metrics["stage1"] = self.stage1_reranker.get_metrics()

        return metrics


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    # Test Stage-2 reranker
    reranker = DomainReranker()

    query = "P-101 pump torque curve"

    # Simulated Stage-1 results
    results = [
        {
            "text": "P-101 centrifugal pump torque specifications with curve data",
            "rerank_score": 0.95,
            "metadata": {
                "equipment_tags": ["P-101"],
                "doc_type": "datasheet",
                "chunk_type": "text",
            },
        },
        {
            "text": "Pump operating parameters and pressure settings",
            "rerank_score": 0.87,
            "metadata": {"chunk_type": "text"},
        },
        {
            "text": "P-101 equipment diagram showing connections",
            "rerank_score": 0.82,
            "metadata": {"equipment_tags": ["P-101", "HX-201"], "chunk_type": "pid"},
        },
    ]

    print("\n=== Testing Stage-2 Domain Reranker ===")
    print(f"Query: {query}")
    print(f"Input: {len(results)} results with Stage-1 scores\n")

    reranked = reranker.rerank(query, results, top_k=3)

    print("\nFinal Reranked Results:")
    for i, r in enumerate(reranked, 1):
        print(f"\n{i}. [Final Score: {r['final_score']:.4f}]")
        print(f"   Base: {r['base_score']:.2f}, Boost: +{r['boost_total']:.2f}")
        print(f"   Boost breakdown: {r['boost_breakdown']}")
        print(f"   Text: {r['text'][:60]}...")
