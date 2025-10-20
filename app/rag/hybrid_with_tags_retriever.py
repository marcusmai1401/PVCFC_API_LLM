"""
Hybrid Retriever with PID Tags Support
Extends existing hybrid retrieval with parallel tags sidecar search

UPDATED: Full integration with SUFFIX-only and component-based search
with multi-layer safety (context validation, fallback, metrics)

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 8
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import get_config
from app.core.pid_metrics import PIDQueryMetrics, log_pid_decision, log_pid_query
from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridModernConfig,
    HybridWeaviateOpenSearchRetriever,
)
from app.rag.query_processing.pid_context_validator import (
    PIDContextValidator,
    should_fallback_on_empty,
)
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult


class HybridWithTagsRetriever:
    """
    Extended hybrid retriever with PID tags sidecar

    Architecture:
    1. Check if PID tags enabled + tag intent detected
    2. Branch A: Tags retriever (if applicable)
    3. Branch B: Standard hybrid (Weaviate + OpenSearch chunks)
    4. RRF fusion of all branches
    5. Rerank
    6. Attach crop to tag results
    """

    def __init__(self, config: Optional[HybridModernConfig] = None):
        """Initialize hybrid retriever with tags support"""
        self.config = get_config()
        self.hybrid_config = config or HybridModernConfig()

        # Standard hybrid retriever (chunks)
        self.hybrid_retriever = HybridWeaviateOpenSearchRetriever(self.hybrid_config)

        # PID tags components (lazy init)
        self.tags_enabled = self.config.ENABLE_PID_TAGS
        self.tags_retriever = None
        self.pid_enhancer = None

        if self.tags_enabled:
            try:
                # Lazy import to avoid circular dependencies
                from app.rag.indexers.opensearch_tags_retriever import (
                    OpenSearchTagsRetriever,
                )
                from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer

                self.tags_retriever = OpenSearchTagsRetriever()
                self.pid_enhancer = PIDQueryEnhancer()
                logger.info("✓ PID tags retrieval enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize tags components: {e}")
                logger.warning("Falling back to standard hybrid retrieval")
                self.tags_enabled = False

    def search(
        self,
        transformed_query: TransformedQuery,
        top_k: int = 10,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Search with tags sidecar support

        Args:
            transformed_query: Transformed query
            top_k: Number of final results
            **kwargs: Additional args for hybrid retriever

        Returns:
            List of RetrievalResult objects (may include tag results with crop_path)
        """
        # Check if tags retrieval should be used
        use_tags = self.tags_enabled and self._should_use_tags(transformed_query)

        if use_tags:
            logger.info("Using tags-enhanced retrieval")
            return self._search_with_tags(transformed_query, top_k, **kwargs)
        else:
            # Standard hybrid retrieval
            logger.debug("Using standard hybrid retrieval (no tags)")
            return self.hybrid_retriever.search(transformed_query, top_k, **kwargs)

    def _should_use_tags(self, transformed_query: TransformedQuery) -> bool:
        """
        Determine if tags retrieval should be used

        UPDATED: Multi-layer validation with safety checks
        - Layer 1: Strategy detection
        - Layer 2: Context validation (false positive prevention)
        - Layer 3: Confidence threshold check
        - Layer 4: Exception handling

        Args:
            transformed_query: Transformed query

        Returns:
            True if tags retrieval applicable
        """
        if not self.pid_enhancer:
            log_pid_decision(
                transformed_query.original,
                "use_semantic",
                "PID enhancer not initialized",
            )
            return False

        try:
            # LAYER 1: Analyze query for P&ID patterns
            analysis = self.pid_enhancer.enhance(transformed_query.original)
            strategy = analysis.get("strategy")

            # NEW: Support new strategies (suffix_search, component_search)
            if strategy not in ["suffix_search", "component_search", "tag_focused"]:
                log_pid_decision(
                    transformed_query.original,
                    "use_semantic",
                    f"Strategy is '{strategy}', not P&ID-related",
                )
                return False

            # LAYER 2: Context validation (false positive prevention)
            validator = PIDContextValidator()
            validation = validator.validate(transformed_query.original, strategy)

            if not validation["is_valid"]:
                log_pid_decision(
                    transformed_query.original,
                    "use_semantic",
                    f"Context validation failed: {validation['reason']}",
                    {"confidence": validation["confidence"], "strategy": strategy},
                )
                return False

            # LAYER 3: Check validation confidence threshold
            min_confidence = 0.5  # TODO: Make configurable via settings
            if validation["confidence"] < min_confidence:
                log_pid_decision(
                    transformed_query.original,
                    "use_semantic",
                    f"Validation confidence too low: {validation['confidence']:.2f} < {min_confidence}",
                    {"strategy": strategy},
                )
                return False

            # PASSED all validation checks
            log_pid_decision(
                transformed_query.original,
                "use_pid",
                f"Strategy={strategy}, confidence={validation['confidence']:.2f}",
                {
                    "strategy": strategy,
                    "validation": validation,
                    "components": analysis.get("components")
                    or analysis.get("suffix")
                    or analysis.get("tags"),
                },
            )

            # Store validation and analysis for later use
            self._last_validation = validation
            self._last_analysis = analysis

            return True

        except Exception as e:
            # LAYER 4: Exception handling - always fallback safely
            logger.error(f"P&ID tag detection failed: {e}")
            log_pid_decision(
                transformed_query.original,
                "use_semantic",
                f"Exception during detection: {str(e)}",
            )
            return False

    def _search_with_tags(
        self,
        transformed_query: TransformedQuery,
        top_k: int,
        **kwargs,
    ) -> List[RetrievalResult]:
        """
        Search with parallel tags + chunks retrieval

        UPDATED: Handles new strategies with multi-layer safety
        - suffix_search: Search by SUFFIX only
        - component_search: Search by components (unit/prefix/suffix)
        - tag_focused: Existing behavior (backward compatible)

        Pipeline:
        1. Detect tags in query
        2. Search tags index (Branch A) - NEW: strategy-aware
        3. Search chunks (Branch B - standard hybrid)
        4. Empty results fallback (NEW)
        5. RRF fusion of both branches
        6. Metrics logging (NEW)

        Args:
            transformed_query: Transformed query
            top_k: Final results count
            **kwargs: Additional args

        Returns:
            Fused and reranked results (or semantic fallback)
        """
        start_time = time.time()

        # Get analysis from validation phase
        analysis = getattr(self, "_last_analysis", None) or self.pid_enhancer.enhance(
            transformed_query.original
        )

        strategy = analysis.get("strategy")
        tags_results = []
        fallback_reason = None

        logger.info(f"Executing P&ID search with strategy: {strategy}")

        # Branch A: P&ID Tags Retrieval (strategy-aware)
        try:
            if strategy == "suffix_search":
                # NEW: SUFFIX-only search
                suffix = analysis.get("suffix")
                logger.info(f"SUFFIX search: {suffix}")

                grouped_results = self.tags_retriever.search_by_suffix(suffix, top_k=50)
                tags_results = self._flatten_grouped_results(grouped_results)

                # Store grouped format for potential response formatting
                self._last_grouped_results = grouped_results

                logger.info(
                    f"SUFFIX search '{suffix}': {len(tags_results)} tags, "
                    f"ambiguity={grouped_results.get('has_ambiguity')}"
                )

            elif strategy == "component_search":
                # NEW: Component-based search
                components = analysis.get("components", {})
                logger.info(f"Component search: {components}")

                tags_results = self.tags_retriever.search_by_components(**components)

                logger.info(f"Component search {components}: {len(tags_results)} tags")

            elif strategy == "tag_focused":
                # OLD: Existing tag search (backward compatible)
                detected_tags = analysis.get("tags", [])
                parsed_tags = self._parse_detected_tags(detected_tags)

                tags_results = self.tags_retriever.search(
                    query=transformed_query.original,
                    detected_tags=parsed_tags,
                    top_k=50,
                )

                logger.info(f"Tag-focused search: {len(tags_results)} tags")

            else:
                logger.warning(f"Unknown P&ID strategy: {strategy}")
                fallback_reason = f"Unknown strategy: {strategy}"

        except Exception as e:
            logger.error(f"P&ID tags search exception: {e}")
            fallback_reason = f"Search exception: {str(e)}"
            tags_results = []

        # CRITICAL: Empty results fallback check
        if should_fallback_on_empty(tags_results, min_results=1):
            fallback_reason = (
                fallback_reason or f"Insufficient results ({len(tags_results)})"
            )

            logger.warning(
                f"P&ID search fallback triggered: {fallback_reason}. "
                "Using semantic search."
            )

            # Log fallback metrics
            log_pid_query(
                PIDQueryMetrics(
                    timestamp=datetime.now().isoformat(),
                    query=transformed_query.original,
                    strategy=strategy,
                    validation_confidence=getattr(self, "_last_validation", {}).get(
                        "confidence", 0
                    ),
                    tags_found=len(tags_results)
                    if isinstance(tags_results, list)
                    else 0,
                    fallback_triggered=True,
                    fallback_reason=fallback_reason,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            )

            # FALLBACK: Standard hybrid retrieval
            return self.hybrid_retriever.search(transformed_query, top_k, **kwargs)

        # SUCCESS: Tags found, continue with fusion
        # Branch B: Standard chunks retrieval
        chunks_results = self.hybrid_retriever.search(
            transformed_query, top_k=50, **kwargs
        )
        logger.info(f"Chunks branch returned {len(chunks_results)} results")

        # RRF Fusion
        if tags_results:
            fused_results = self._rrf_fusion(
                tags_results=tags_results,
                chunks_results=chunks_results,
                k=self.hybrid_config.rrf_k,
            )
            logger.info(f"RRF fusion: {len(fused_results)} combined results")
        else:
            # No tags results, use chunks only
            fused_results = chunks_results

        # Log success metrics
        log_pid_query(
            PIDQueryMetrics(
                timestamp=datetime.now().isoformat(),
                query=transformed_query.original,
                strategy=strategy,
                validation_confidence=getattr(self, "_last_validation", {}).get(
                    "confidence", 0.5
                ),
                tags_found=len(tags_results) if isinstance(tags_results, list) else 0,
                fallback_triggered=False,
                fallback_reason=None,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        )

        # Return top-k
        return fused_results[:top_k]

    def _flatten_grouped_results(self, grouped_results: Dict) -> List[Dict]:
        """
        Flatten grouped P&ID results into flat list for fusion

        Args:
            grouped_results: Dict from search_by_suffix() with structure:
                            {groups: [{tags: [...]}, ...], total_tags: N, ...}

        Returns:
            Flat list of tag result dicts for RRF fusion
        """
        flat_results = []

        for group in grouped_results.get("groups", []):
            flat_results.extend(group.get("tags", []))

        logger.debug(
            f"Flattened {len(flat_results)} tags from {len(grouped_results.get('groups', []))} groups"
        )

        return flat_results

    def _parse_detected_tags(self, tag_strings: List[str]) -> List[Dict]:
        """
        Parse detected tag strings into structured format

        UPDATED: Uses new schema (unit/prefix/suffix/variant)

        Args:
            tag_strings: List of tag strings (e.g., ["04 PSAL 2207", "PAL 2208"])

        Returns:
            List of dicts with tag and parts (new schema)
        """
        parsed = []

        for tag_str in tag_strings:
            try:
                # Try new TagNormalizer parser first
                from app.rag.normalizers.tag_normalizer import TagNormalizer

                normalizer = TagNormalizer()
                components = normalizer.parse_tag_components(tag_str)

                if components:
                    # Use new schema
                    parsed.append(
                        {
                            "tag": tag_str,
                            "parts": {
                                "unit": components.get("unit"),
                                "prefix": components.get("prefix"),
                                "suffix": components.get("suffix"),
                                "variant": components.get("variant"),
                            },
                        }
                    )
                else:
                    # Fallback: treat as full tag text
                    parsed.append({"tag": tag_str, "parts": {}})

            except Exception as e:
                logger.debug(f"Failed to parse tag '{tag_str}': {e}")
                # Fallback: treat as full tag text
                parsed.append({"tag": tag_str, "parts": {}})

        return parsed

    def _rrf_fusion(
        self,
        tags_results: List[Dict],
        chunks_results: List[RetrievalResult],
        k: int = 60,
    ) -> List[RetrievalResult]:
        """
        RRF fusion of tags and chunks results

        Args:
            tags_results: Results from tags retriever
            chunks_results: Results from chunks retriever
            k: RRF constant

        Returns:
            Fused results sorted by RRF score
        """
        rrf_scores = {}
        result_map = {}

        # Add tags results
        for rank, tag_result in enumerate(tags_results):
            chunk_id = tag_result["chunk_id"]
            rrf_scores[chunk_id] = 1.0 / (k + rank + 1)

            # Convert to RetrievalResult
            result_map[chunk_id] = RetrievalResult(
                chunk_id=chunk_id,
                text=tag_result["text"],
                doc_id=tag_result["doc_id"],
                page=tag_result["page"],
                score=tag_result["score"],
                metadata={
                    "source": "tags",
                    "bbox": tag_result.get("bbox"),
                    "crop_path": tag_result.get("crop_path"),
                    "tag_parts": tag_result.get("tag_parts"),
                    "tag_confidence": tag_result.get("confidence"),
                },
            )

        # Add chunks results
        for rank, chunk_result in enumerate(chunks_results):
            chunk_id = chunk_result.chunk_id

            if chunk_id in rrf_scores:
                # Already in tags results, add to score
                rrf_scores[chunk_id] += 1.0 / (k + rank + 1)
            else:
                rrf_scores[chunk_id] = 1.0 / (k + rank + 1)
                result_map[chunk_id] = chunk_result

        # Sort by RRF score
        sorted_ids = sorted(
            rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
        )

        fused_results = []
        for chunk_id in sorted_ids:
            result = result_map[chunk_id]
            # Attach RRF score
            result.fused_score = rrf_scores[chunk_id]
            fused_results.append(result)

        return fused_results

    def health_check(self) -> Dict[str, Any]:
        """Health check for all components"""
        health = {
            "retriever_type": "hybrid_with_tags",
            "components": {},
        }

        # Check hybrid retriever
        health["components"]["hybrid"] = self.hybrid_retriever.health_check()

        # Check tags retriever
        if self.tags_enabled and self.tags_retriever:
            health["components"]["tags"] = self.tags_retriever.health_check()
        else:
            health["components"]["tags"] = {"status": "disabled"}

        # Determine overall status
        hybrid_ok = health["components"]["hybrid"]["overall_status"] == "healthy"
        tags_status = health["components"]["tags"]["status"]

        if hybrid_ok:
            if tags_status in ["healthy", "disabled"]:
                health["overall_status"] = "healthy"
            else:
                health["overall_status"] = "degraded"  # Tags down but chunks OK
        else:
            health["overall_status"] = "critical"

        return health

    # Compatibility helpers for integration with existing startup code
    def get_statistics(self) -> Dict[str, Any]:
        """Delegate statistics to underlying hybrid retriever"""
        try:
            stats = self.hybrid_retriever.get_statistics()
        except Exception:
            stats = {"retriever_type": "hybrid_with_tags", "error": "stats_unavailable"}
        return stats

    @property
    def opensearch_retriever(self):
        """Expose underlying OpenSearch retriever for app wiring"""
        try:
            return getattr(self.hybrid_retriever, "opensearch_retriever", None)
        except Exception:
            return None
