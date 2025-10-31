"""
Technical Document Retriever
Optimized retrieval pipeline for manuals, datasheets, specifications, and performance curves
Separate from P&ID retrieval for better accuracy on technical queries

NEW: HYBRID 2-TIER query-time enhancement
- Tier 1: Fast keyword boosting (no metadata needed)
- Tier 2: LLM reranking for low-confidence cases
"""

from typing import List, Optional

from loguru import logger

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridModernConfig,
    HybridWeaviateOpenSearchRetriever,
)
from app.rag.query_time_enhancer import LLMReranker, QueryTimeEnhancer
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult


class TechnicalDocConfig(HybridModernConfig):
    """
    Configuration optimized for technical document retrieval

    Differences from default:
    - Higher BM25 weight (keywords matter more in manuals)
    - More aggressive reranking
    - Equipment model extraction and boosting
    """

    def __init__(self):
        super().__init__()

        # Boost BM25 for keyword matching (equipment models, specs)
        self.opensearch_limit = 100  # Get more BM25 candidates
        self.weaviate_limit = 50  # Less semantic candidates

        # DISABLE BGE rerank to avoid conflicts - use score-based instead
        self.enable_bge_rerank = False

        # RRF weights favor keywords
        self.rrf_k = 60  # Standard RRF parameter


class TechnicalDocRetriever:
    """
    Retriever optimized for technical documentation queries

    Features:
    - Equipment model extraction and boosting
    - Document type awareness (manual, datasheet, curve)
    - BM25-heavy for precise keyword matching
    - No PID tags routing (pure semantic + BM25)

    Use cases:
    - "What are the setpoints for HCD025 gear unit?"
    - "What is the 100% operating speed in the performance curve?"
    - "According to the manual, what is the alarm threshold?"
    """

    def __init__(
        self,
        config: Optional[TechnicalDocConfig] = None,
        enable_llm_rerank: bool = False,
    ):
        """Initialize technical doc retriever with optimized config"""
        self.config = config or TechnicalDocConfig()

        # Use standard hybrid retriever with custom config
        self.retriever = HybridWeaviateOpenSearchRetriever(self.config)

        # HYBRID 2-TIER components
        self.enhancer = QueryTimeEnhancer(boost_factor=3)
        self.llm_reranker = (
            LLMReranker(confidence_threshold=0.7) if enable_llm_rerank else None
        )

        logger.info(
            f"TechnicalDocRetriever initialized: "
            f"BM25_limit={self.config.opensearch_limit}, "
            f"Semantic_limit={self.config.weaviate_limit}, "
            f"BGE_rerank={self.config.enable_bge_rerank}, "
            f"QueryTimeEnhancement=ON, LLM_rerank={'ON' if enable_llm_rerank else 'OFF'}"
        )

    def search(
        self, transformed_query: TransformedQuery, top_k: int = 10, **kwargs
    ) -> List[RetrievalResult]:
        """
        Search technical documents with HYBRID 2-TIER enhancement

        Pipeline:
        1. TIER 1: Query enhancement (keyword boosting)
           - Extract equipment tags from query
           - Boost query with repeated tags
        2. BM25 + Semantic search with enhanced query
        3. RRF fusion
        4. Post-filter by equipment tag (if confident)
        5. TIER 2: LLM reranking (if low confidence & enabled)

        Args:
            transformed_query: Transformed query
            top_k: Number of results to return
            **kwargs: Additional retrieval parameters

        Returns:
            List of RetrievalResult objects
        """
        query_text = transformed_query.original

        # === TIER 1: Query Enhancement ===
        enhanced_query_text, enhancement_metadata = self.enhancer.enhance(query_text)

        # Create enhanced transformed query
        # IMPORTANT: also enhance the normalized form so BM25/semantic search uses boosted terms
        tags_for_boost = enhancement_metadata.get("equipment_tags", []) or []
        if tags_for_boost:
            boost_terms = []
            for t in tags_for_boost:
                # Include simple variants (base, hyphen, space) in normalized form as well
                variants = self.enhancer._generate_tag_variants(t)
                for _ in range(self.enhancer.boost_factor):
                    boost_terms.extend([v.lower() for v in variants])
            enhanced_normalized = (
                transformed_query.normalized + " " + " ".join(boost_terms)
            ).strip()
        else:
            enhanced_normalized = transformed_query.normalized

        enhanced_query = TransformedQuery(
            original=enhanced_query_text,
            normalized=enhanced_normalized,
            intent=transformed_query.intent,
            filters=transformed_query.filters,  # Pass through filters
            hyde_queries=transformed_query.hyde_queries,
            language=transformed_query.language,
            metadata={
                **(transformed_query.metadata or {}),
                "query_enhancement": enhancement_metadata,
                "equipment_tags": enhancement_metadata.get("equipment_tags", []),
            },
        )

        # Search with enhanced query
        results = self.retriever.search(
            enhanced_query, top_k * 2, **kwargs
        )  # Get 2x for filtering

        # Post-filter by equipment tags
        filtered_results = self.enhancer.post_filter_results(
            results, enhancement_metadata
        )

        # Trim to top_k
        filtered_results = filtered_results[:top_k]

        # === TIER 2: LLM Reranking (if needed) ===
        if self.llm_reranker and self.llm_reranker.should_rerank(
            filtered_results, enhancement_metadata
        ):
            logger.info("Tier 1 confidence low, applying Tier 2 LLM reranking...")
            # Note: rerank is async, but we'll call it sync for now
            # In production, this should be async
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                filtered_results = loop.run_until_complete(
                    self.llm_reranker.rerank(
                        query_text, filtered_results, enhancement_metadata
                    )
                )
            except Exception as e:
                logger.warning(f"LLM reranking failed: {e}, using Tier 1 results")

        return filtered_results

    def _extract_equipment_models(self, query: str) -> List[str]:
        """
        Extract equipment model codes from query

        Patterns:
        - HCD025, KT06101, E-06140 (letters + numbers)
        - 3N4-S4279947 (technical doc codes)

        Args:
            query: Query text

        Returns:
            List of extracted equipment models
        """
        import re

        models = []

        # Pattern 1: Letter prefix + numbers (HCD025, KT06101)
        pattern1 = r"\b[A-Z]{2,}[-]?\d{3,}\b"
        models.extend(re.findall(pattern1, query, re.IGNORECASE))

        # Pattern 2: Technical doc codes (3N4-S4279947)
        pattern2 = r"\b\d+[A-Z]+[-]\w+\b"
        models.extend(re.findall(pattern2, query, re.IGNORECASE))

        return list(set(models))  # Remove duplicates

    def _boost_equipment_matches(
        self, results: List[RetrievalResult], equipment_models: List[str]
    ) -> List[RetrievalResult]:
        """
        Boost results that match equipment models in doc_id or text

        Args:
            results: Retrieval results
            equipment_models: List of equipment models to match

        Returns:
            Results with boosted scores
        """
        boosted = []

        for result in results:
            boost_factor = 1.0

            # Check if equipment model appears in doc_id
            doc_id_lower = result.doc_id.lower()
            for model in equipment_models:
                if model.lower() in doc_id_lower:
                    boost_factor = 1.5  # 50% boost
                    logger.debug(f"Boosted {result.doc_id[:50]} for model {model}")
                    break

            # Apply boost
            if boost_factor > 1.0:
                result.score *= boost_factor

            boosted.append(result)

        # Re-sort by boosted scores
        boosted.sort(key=lambda x: x.score, reverse=True)

        return boosted
