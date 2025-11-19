"""
Hybrid Retriever with PID Tags Support
Extends existing hybrid retrieval with parallel tags sidecar search

UPDATED: Full integration with SUFFIX-only and component-based search
with multi-layer safety (context validation, fallback, metrics)

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 8
"""

import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import get_config
from app.core.pid_metrics import PIDQueryMetrics, log_pid_decision, log_pid_query
from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridModernConfig,
    HybridWeaviateOpenSearchRetriever,
)
from app.rag.query_transform import TransformedQuery
from app.rag.retriever import RetrievalResult

# Request-scoped context variables to prevent race conditions (BUG-021 FIX)
# Previously, instance variables were shared across concurrent requests, causing
# Request A to get Request B's cached analysis, leading to wrong retrieval results.
# ContextVar provides thread-safe, request-scoped storage in async contexts.
_request_analysis: ContextVar[Optional[Dict]] = ContextVar(
    "request_analysis", default=None
)
_request_grouped_results: ContextVar[Optional[Dict]] = ContextVar(
    "request_grouped_results", default=None
)


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
        self.spatial_searcher = None
        self.pid_enhancer = None
        self.text_tag_detector = None

        if self.tags_enabled:
            try:
                # Lazy import to avoid circular dependencies
                from app.rag.query_processing.pid_query_enhancer import PIDQueryEnhancer
                from app.rag.spatial.spatial_searcher import SpatialTagSearcher
                from app.rag.text_tag_detector import TextTagDetector

                # Level 2: Spatial clustering for absolute accuracy
                self.spatial_searcher = SpatialTagSearcher(
                    max_distance_mm=100.0,  # Increased to handle larger tag layouts
                    alignment_tolerance_mm=5.0,
                    min_cluster_score=0.6,
                )
                self.pid_enhancer = PIDQueryEnhancer()

                # Level 1: Text-only tag fallback (uses text_by_page.jsonl)
                if getattr(self.config, "ENABLE_TEXT_TAG_FALLBACK", True):
                    self.text_tag_detector = TextTagDetector(self.config)
                    logger.info("✓ TextTagDetector fallback enabled for P&ID tags")
                else:
                    logger.info("TextTagDetector fallback disabled via config")

                logger.info("✓ PID spatial search (Level 2) enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize spatial/text tag components: {e}")
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

    def _extract_doc_id(
        self, transformed_query: TransformedQuery, **kwargs
    ) -> Optional[str]:
        """
        Extract doc_id from request context for Level 2 spatial search

        Priority:
        1. kwargs['request'].doc_id (if provided)
        2. transformed_query.filters['doc_id'][0] (if present)
        3. None (triggers all-docs search)

        Args:
            transformed_query: Query with filters
            **kwargs: May contain 'request' object

        Returns:
            doc_id string if specified, None if not (triggers multi-document search)
        """
        # Priority 1: From request object
        request = kwargs.get("request")
        if request and hasattr(request, "doc_id") and request.doc_id:
            logger.debug(f"✓ Using doc_id from request: {request.doc_id}")
            return request.doc_id

        # Priority 2: From filters
        if (
            transformed_query.filters
            and hasattr(transformed_query.filters, "doc_ids")
            and transformed_query.filters.doc_ids
        ):
            doc_ids = transformed_query.filters.doc_ids
            if doc_ids:
                logger.debug(f"✓ Using doc_id from filters: {doc_ids[0]}")
                return doc_ids[0]

        # Priority 3: None (triggers multi-document search)
        logger.info("⚠️  doc_id not specified, will search all documents")
        return None

    def _convert_spatial_to_tags(
        self, spatial_results: List, components: Dict
    ) -> List[Dict]:
        """
        Convert Level 2 SearchResult objects to tags format for RRF fusion

        Args:
            spatial_results: List of SearchResult from SpatialTagSearcher
            components: Dict with unit, prefix, suffix

        Returns:
            List of tag dicts compatible with existing pipeline
        """
        tags_results = []

        # Build tag text from components
        unit = components.get("unit", "")
        prefix = components.get("prefix", "")
        suffix = components.get("suffix", "")
        tag_text = " ".join(filter(None, [unit, prefix, suffix]))

        for sr in spatial_results:
            tag_result = {
                "tag": tag_text,
                "doc_id": sr.doc_id,
                "page": sr.page,
                "bbox": sr.bbox,
                "score": sr.score,
                "source": "spatial_level2",
                "metadata": sr.metadata,
                "text": tag_text,  # For compatibility
                "chunk_id": f"{sr.doc_id}_p{sr.page}_tag_{tag_text.replace(' ', '_')}",
            }
            tags_results.append(tag_result)

        return tags_results

    def _should_use_tags(self, transformed_query: TransformedQuery) -> bool:
        """
        Simplified: User already selected pid mode, just parse tag components

        Args:
            transformed_query: Transformed query

        Returns:
            True if query has parseable P&ID tag patterns
        """
        if not self.pid_enhancer:
            logger.debug("PID enhancer not initialized")
            return False

        try:
            # Parse tag components from query
            analysis = self.pid_enhancer.enhance(transformed_query.original)
            strategy = analysis.get("strategy")

            # If valid P&ID strategy detected, use tags search
            if strategy in ["suffix_search", "component_search", "tag_focused"]:
                log_pid_decision(
                    transformed_query.original,
                    "use_pid",
                    f"P&ID pattern detected: {strategy}",
                    {
                        "strategy": strategy,
                        "components": analysis.get("components")
                        or analysis.get("suffix"),
                    },
                )

                # Store analysis in request context for _search_with_tags()
                _request_analysis.set(analysis)
                return True

            # No P&ID pattern detected - fallback to semantic search
            log_pid_decision(
                transformed_query.original,
                "use_semantic",
                f"No P&ID tag pattern detected (strategy={strategy})",
            )
            return False

        except Exception as e:
            logger.error(f"P&ID query analysis failed: {e}")
            log_pid_decision(
                transformed_query.original,
                "use_semantic",
                f"Analysis exception: {str(e)}",
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

        # Get analysis from request-scoped context (BUG-021 FIX)
        analysis = _request_analysis.get() or self.pid_enhancer.enhance(
            transformed_query.original
        )

        strategy = analysis.get("strategy")
        tags_results = []
        fallback_reason = None
        components_for_fallback: Optional[Dict] = None

        # Extract doc_id for Level 2 spatial search
        doc_id = self._extract_doc_id(transformed_query, **kwargs)

        logger.info(
            f"Executing P&ID spatial search (Level 2): strategy={strategy}, doc_id={doc_id}"
        )

        # Branch A: P&ID Spatial Search (Level 2)
        try:
            if strategy == "component_search":
                # Component-based spatial clustering
                components = analysis.get("components", {})
                components_for_fallback = components or None
                logger.info(f"Component spatial search: {components}")

                # Level 2: Spatial clustering with geometric validation
                # Handle None doc_id (multi-document search)
                if doc_id is None:
                    # Search all documents
                    logger.info("Performing multi-document spatial search")
                    all_doc_ids = self.spatial_searcher.indexer.get_all_doc_ids()

                    if not all_doc_ids:
                        logger.warning("No doc_ids found in spatial index")
                        spatial_results = []
                    else:
                        logger.info(
                            f"Searching {len(all_doc_ids)} documents: {all_doc_ids}"
                        )
                        all_spatial_results = []

                        for search_doc_id in all_doc_ids:
                            try:
                                results = self.spatial_searcher.search(
                                    unit=components.get("unit", ""),
                                    prefix=components.get("prefix", ""),
                                    suffix=components.get("suffix", ""),
                                    doc_id=search_doc_id,
                                )
                                all_spatial_results.extend(results)
                            except Exception as e:
                                logger.warning(
                                    f"Search failed for doc_id={search_doc_id}: {e}"
                                )
                                continue

                        # Sort by score and take top results
                        all_spatial_results.sort(key=lambda r: r.score, reverse=True)
                        spatial_results = all_spatial_results[
                            :50
                        ]  # Top 50 from all docs

                        logger.info(
                            f"Multi-doc spatial search: {len(all_spatial_results)} total results "
                            f"→ top {len(spatial_results)}"
                        )
                else:
                    # Single document search (existing logic)
                    spatial_results = self.spatial_searcher.search(
                        unit=components.get("unit", ""),
                        prefix=components.get("prefix", ""),
                        suffix=components.get("suffix", ""),
                        doc_id=doc_id,
                    )

                # Convert to tags format for RRF fusion
                tags_results = self._convert_spatial_to_tags(
                    spatial_results, components
                )

                logger.info(
                    f"Spatial search {components}: {len(tags_results)} spatial clusters found"
                )

            elif strategy == "suffix_search":
                # SUFFIX-only: NOT supported in Level 2 spatial search
                # Level 2 requires all three components (unit, prefix, suffix) for geometric clustering.
                # SUFFIX-only queries will fallback to semantic search.
                #
                # Why? Level 2 uses spatial proximity calculations which need complete tag structure.
                # Without unit and prefix positions, we cannot validate geometric alignment.
                #
                # Example: Query "5153" cannot be spatially clustered without knowing where
                #          the unit and prefix are located on the page.
                #
                # Workaround: User should provide full tag (e.g., "04 PAHH 5153") or at least
                #            partial components (e.g., "PAHH 5153")
                suffix = analysis.get("suffix")
                logger.warning(
                    f"⚠️  SUFFIX-only query '{suffix}' not supported in Level 2 (Spatial Search). "
                    f"Level 2 requires full tag components for geometric clustering. "
                    f"Falling back to semantic search. "
                    f"TIP: Provide full tag (e.g., '04 PAHH {suffix}') for better results."
                )
                fallback_reason = "Level 2 requires full components (unit+prefix+suffix), suffix-only not supported"
                tags_results = []

            elif strategy == "tag_focused":
                # Tag-focused: Parse complete tag and extract components
                detected_tags = analysis.get("tags", [])
                if detected_tags:
                    tag_str = (
                        detected_tags[0]
                        if isinstance(detected_tags, list)
                        else detected_tags
                    )

                    # Re-parse to get components
                    comp_analysis = self.pid_enhancer.enhance(tag_str)
                    if comp_analysis.get("strategy") == "component_search":
                        components = comp_analysis.get("components", {})
                        components_for_fallback = components or None

                        # Handle None doc_id (multi-document search)
                        if doc_id is None:
                            logger.info("Multi-doc search in tag_focused mode")
                            all_doc_ids = (
                                self.spatial_searcher.indexer.get_all_doc_ids()
                            )
                            all_spatial_results = []

                            for search_doc_id in all_doc_ids:
                                try:
                                    results = self.spatial_searcher.search(
                                        unit=components.get("unit", ""),
                                        prefix=components.get("prefix", ""),
                                        suffix=components.get("suffix", ""),
                                        doc_id=search_doc_id,
                                    )
                                    all_spatial_results.extend(results)
                                except Exception as e:
                                    logger.warning(
                                        f"Search failed for doc_id={search_doc_id}: {e}"
                                    )

                            all_spatial_results.sort(
                                key=lambda r: r.score, reverse=True
                            )
                            spatial_results = all_spatial_results[:50]
                        else:
                            spatial_results = self.spatial_searcher.search(
                                unit=components.get("unit", ""),
                                prefix=components.get("prefix", ""),
                                suffix=components.get("suffix", ""),
                                doc_id=doc_id,
                            )

                        tags_results = self._convert_spatial_to_tags(
                            spatial_results, components
                        )
                        logger.info(
                            f"Tag-focused spatial search: {len(tags_results)} results"
                        )
                    else:
                        logger.warning(f"Cannot parse tag '{tag_str}' into components")
                        fallback_reason = "Cannot parse tag into components"
                        tags_results = []
                else:
                    fallback_reason = "No tags detected"
                    tags_results = []

            else:
                logger.warning(f"Unknown P&ID strategy: {strategy}")
                fallback_reason = f"Unknown strategy: {strategy}"
                tags_results = []

        except Exception as e:
            logger.error(f"P&ID tags search exception: {e}")
            fallback_reason = f"Search exception: {str(e)}"
            tags_results = []

        # Text-based tag fallback (Level 1) when spatial returns no tags
        if (
            not tags_results
            and self.text_tag_detector is not None
            and components_for_fallback is not None
            and doc_id is not None
        ):
            try:
                unit = components_for_fallback.get("unit", "")
                prefix = components_for_fallback.get("prefix", "")
                suffix = components_for_fallback.get("suffix", "")

                if unit and prefix and suffix:
                    max_gap = getattr(self.config, "TEXT_TAG_MAX_GAP_TOKENS", 5)
                    text_hits = self.text_tag_detector.find_tag_hits(
                        doc_id=doc_id,
                        unit=unit,
                        prefix=prefix,
                        suffix=suffix,
                        max_gap_tokens=max_gap,
                    )

                    if text_hits:
                        logger.info(
                            f"TextTagDetector: using {len(text_hits)} hits as tag fallback for "
                            f"{unit} {prefix} {suffix} in doc_id={doc_id}"
                        )
                        tags_results = []
                        tag_text = " ".join([unit, prefix, suffix]).strip()
                        for hit in text_hits[:10]:
                            tags_results.append(
                                {
                                    "tag": tag_text,
                                    "doc_id": hit.doc_id,
                                    "page": hit.page,
                                    "bbox": None,
                                    "score": hit.score,
                                    "source": "text_tag_fallback",
                                    "metadata": {
                                        "tag_text": tag_text,
                                        "text_fallback": True,
                                        "context": hit.context,
                                    },
                                    "text": hit.context,
                                    "chunk_id": f"{hit.doc_id}_p{hit.page}_text_tag_"
                                    f"{unit}_{prefix}_{suffix}",
                                }
                            )
                    else:
                        logger.info(
                            "TextTagDetector: no hits found for components "
                            f"unit={unit}, prefix={prefix}, suffix={suffix}, doc_id={doc_id}"
                        )
                else:
                    logger.debug(
                        "TextTagDetector: components_for_fallback missing unit/prefix/suffix, "
                        "skipping text fallback"
                    )
            except Exception as e:
                logger.error(f"TextTagDetector fallback failed: {e}")

        # Empty results fallback check (simplified)
        if not tags_results:
            fallback_reason = (
                fallback_reason or f"Insufficient results ({len(tags_results)})"
            )

            logger.warning(
                f"P&ID search fallback triggered: {fallback_reason}. "
                "Using P&ID-aware semantic search."
            )

            # Log fallback metrics
            log_pid_query(
                PIDQueryMetrics(
                    timestamp=datetime.now().isoformat(),
                    query=transformed_query.original,
                    strategy=strategy,
                    validation_confidence=1.0,  # User-selected mode, full confidence
                    tags_found=len(tags_results)
                    if isinstance(tags_results, list)
                    else 0,
                    fallback_triggered=True,
                    fallback_reason=fallback_reason,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            )

            # FALLBACK: P&ID-aware enhanced semantic search
            # Check if feature is enabled
            if getattr(self.config, "pid_enable_semantic_fallback", True):
                try:
                    from app.rag.pid_fallback_enhancer import PIDFallbackEnhancer

                    enhancer = PIDFallbackEnhancer(
                        config={
                            "opensearch_weight": getattr(
                                self.config, "pid_opensearch_weight", 1.0
                            ),
                            "weaviate_weight": getattr(
                                self.config, "pid_weaviate_weight", 0.3
                            ),
                            "enable_tag_rerank": getattr(
                                self.config, "pid_enable_tag_rerank", True
                            ),
                            "enable_safety_check": getattr(
                                self.config, "pid_enable_safety_check", True
                            ),
                            "max_variants": getattr(
                                self.config, "pid_max_tag_variants", 4
                            ),
                        }
                    )

                    return enhancer.search_with_enhancements(
                        transformed_query=transformed_query,
                        analysis=analysis,
                        opensearch_retriever=self.hybrid_retriever.opensearch_retriever,
                        weaviate_retriever=self.hybrid_retriever.weaviate_retriever,
                        top_k=top_k,
                    )
                except Exception as e:
                    logger.error(
                        f"P&ID fallback enhancer failed: {e}, using standard fallback"
                    )
                    return self.hybrid_retriever.search(
                        transformed_query, top_k, **kwargs
                    )
            else:
                # Feature disabled, use standard fallback
                logger.info(
                    "P&ID semantic fallback disabled, using standard hybrid search"
                )
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
                validation_confidence=1.0,  # User-selected mode, full confidence
                tags_found=len(tags_results) if isinstance(tags_results, list) else 0,
                fallback_triggered=False,
                fallback_reason=None,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        )

        # Return top-k
        return fused_results[:top_k]

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
                source="tags",
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

        # Check spatial searcher (Level 2)
        if self.tags_enabled and self.spatial_searcher:
            health["components"]["spatial_search"] = {"status": "enabled", "level": 2}
        else:
            health["components"]["spatial_search"] = {"status": "disabled"}

        # Determine overall status
        hybrid_ok = health["components"]["hybrid"]["overall_status"] == "healthy"
        tags_status = health["components"]["spatial_search"]["status"]

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
