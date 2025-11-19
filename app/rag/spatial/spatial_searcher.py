"""
Spatial Tag Searcher
Search for tags using spatial proximity of components
"""
from typing import List, Set

from loguru import logger

from app.core.config import settings
from app.rag.spatial.component_clusterer import ComponentClusterer
from app.rag.spatial.component_indexer import SpatialComponentIndexer
from app.rag.spatial.schemas import Component, SearchResult, TagCluster
from app.services.reranker import get_reranker_service


class TagVariantGenerator:
    """Generate OCR/formatting variants for tag components.

    This provides a lightweight, index-compatible form of "fuzzy" matching by
    trying common variations of unit/prefix/suffix instead of requiring changes
    to the OpenSearch mapping (which uses keyword fields).
    """

    @staticmethod
    def generate_variants(component_text: str, component_type: str) -> List[str]:
        if not component_text:
            return []

        base = component_text.strip()
        variants: Set[str] = {base}

        # Remove spaces and hyphens (e.g., "04 PA" -> "04PA")
        collapsed = base.replace(" ", "").replace("-", "")
        variants.add(collapsed)

        # Unit-specific variants (e.g., "4" -> "04", "004")
        if component_type == "unit" and base.isdigit() and len(base) <= 2:
            if len(base) == 1:
                variants.add(f"0{base}")
                variants.add(f"00{base}")
            # Also keep original for safety

        # Prefix casing variants
        if component_type == "prefix":
            variants.add(base.upper())
            variants.add(base.lower())

        # Common OCR confusions (O/0, I/1, S/5)
        ocr_pairs = [
            ("O", "0"),
            ("0", "O"),
            ("I", "1"),
            ("1", "I"),
            ("S", "5"),
            ("5", "S"),
        ]
        for old, new in ocr_pairs:
            if old in base:
                variants.add(base.replace(old, new))

        return list(variants)


class TagClusterReranker:
    """Rerank spatial tag clusters using BGE CrossEncoder scores.

    NOTE: This adds a semantic signal on top of spatial geometry, which can help
    when multiple candidate clusters exist across pages/docs. It reuses the
    global BGE reranker service so no extra model is loaded.
    """

    def __init__(self):
        self._reranker = get_reranker_service()

    def rerank(
        self, query_tag: str, clusters: List[TagCluster], top_k: int | None = None
    ) -> List[TagCluster]:
        if not clusters:
            return clusters

        # Build chunk-like payloads for the BGE reranker
        chunks = []
        for idx, cluster in enumerate(clusters):
            chunks.append(
                {
                    "chunk_id": f"{cluster.doc_id}_p{cluster.page}_cluster_{idx}",
                    "text": cluster.tag_text,
                    "metadata": {"cluster_index": idx},
                    "doc_id": cluster.doc_id,
                    "source": "spatial_cluster",
                    "original_score": float(cluster.score),
                }
            )

        effective_top_k = top_k or len(chunks)

        # Call BGE reranker (chunk-level)
        reranked = self._reranker.rerank_chunks(
            query=query_tag, chunks=chunks, top_k=effective_top_k
        )

        reranked_clusters: List[TagCluster] = []
        for chunk, bge_score in reranked:
            meta = chunk.get("metadata") or {}
            idx = meta.get("cluster_index")
            if idx is None or not (0 <= idx < len(clusters)):
                continue

            base_cluster = clusters[idx]
            # Combine spatial score (geometry) with BGE score (semantic)
            combined = 0.6 * float(base_cluster.score) + 0.4 * float(bge_score)
            base_cluster.score = combined
            reranked_clusters.append(base_cluster)

        # Fall back to original order if something went wrong
        if not reranked_clusters:
            return clusters

        reranked_clusters.sort(key=lambda c: c.score, reverse=True)
        return reranked_clusters


class SpatialTagSearcher:
    """Search for tags using spatial component proximity"""

    def __init__(
        self,
        max_distance_mm: float = 100.0,  # Increased from 25mm to handle larger tag layouts
        alignment_tolerance_mm: float = 5.0,
        min_cluster_score: float = 0.6,
    ):
        """
        Initialize searcher

        Args:
            max_distance_mm: Max distance between components
            alignment_tolerance_mm: Vertical alignment tolerance
            min_cluster_score: Minimum cluster quality score
        """
        self.indexer = SpatialComponentIndexer()
        self.clusterer = ComponentClusterer(
            max_distance_mm=max_distance_mm,
            alignment_tolerance_mm=alignment_tolerance_mm,
            min_cluster_score=min_cluster_score,
        )

    def search(
        self, unit: str, prefix: str, suffix: str, doc_id: str = "Ammonia"
    ) -> List[SearchResult]:
        """
        Search for tag by components

        Args:
            unit: Unit number (e.g., "04")
            prefix: Tag prefix (e.g., "TXI")
            suffix: Tag suffix (e.g., "2077")
            doc_id: Document ID

        Returns:
            List of SearchResult sorted by score
        """
        logger.info(f"Spatial search: {unit} {prefix} {suffix}")

        # Step 1: Find pages containing ALL components (with soft variants)
        pages_with_unit = self._get_pages_with_component_with_variants(
            unit, "unit", doc_id
        )
        pages_with_prefix = self._get_pages_with_component_with_variants(
            prefix, "prefix", doc_id
        )
        pages_with_suffix = self._get_pages_with_component_with_variants(
            suffix, "suffix", doc_id
        )

        candidate_pages = pages_with_unit & pages_with_prefix & pages_with_suffix

        if not candidate_pages:
            logger.warning(
                f"No pages found with all components: {unit}, {prefix}, {suffix}"
            )
            return []

        logger.debug(f"Candidate pages: {sorted(candidate_pages)}")

        # Step 2: For each page, get components and find clusters
        all_clusters: List[TagCluster] = []

        for page in candidate_pages:
            # Get all components on this page (with variants fallback)
            page_units = self._get_components_on_page_with_variants(
                unit, "unit", doc_id, page
            )
            page_prefixes = self._get_components_on_page_with_variants(
                prefix, "prefix", doc_id, page
            )
            page_suffixes = self._get_components_on_page_with_variants(
                suffix, "suffix", doc_id, page
            )

            # Find clusters
            clusters = self.clusterer.find_tag_clusters(
                units=page_units, prefixes=page_prefixes, suffixes=page_suffixes
            )

            all_clusters.extend(clusters)

        # Optional: semantic reranking of clusters using BGE CrossEncoder
        if all_clusters and settings.enable_bge_rerank:
            try:
                query_tag = f"{unit} {prefix} {suffix}".strip()
                reranker = TagClusterReranker()
                all_clusters = reranker.rerank(
                    query_tag=query_tag, clusters=all_clusters
                )
            except Exception as e:
                logger.error(f"BGE reranking for tag clusters failed: {e}")

        # Convert clusters to search results
        results: List[SearchResult] = []
        for cluster in all_clusters:
            results.append(
                SearchResult(
                    page=cluster.page,
                    doc_id=cluster.doc_id,
                    score=cluster.score,
                    bbox=cluster.bbox,
                    source="spatial",
                    metadata={
                        "tag_text": cluster.tag_text,
                        "unit": cluster.unit.text,
                        "prefix": cluster.prefix.text,
                        "suffix": cluster.suffix.text,
                    },
                )
            )

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)

        logger.info(
            f"Spatial search found {len(results)} results across {len(candidate_pages)} pages"
        )

        return results

    def _get_pages_with_component_with_variants(
        self, component_text: str, component_type: str, doc_id: str
    ) -> Set[int]:
        """Get pages containing a component, trying common variants if needed.

        This provides a soft form of fuzzy matching without changing index
        mappings by issuing multiple exact term queries for likely variants.
        """
        # First try exact text
        pages = self._get_pages_with_component(component_text, component_type, doc_id)
        if pages:
            return pages

        # If nothing found, try variants
        variant_pages: Set[int] = set()
        variants = TagVariantGenerator.generate_variants(component_text, component_type)
        for variant in variants:
            if not variant or variant == component_text:
                continue
            v_pages = self._get_pages_with_component(variant, component_type, doc_id)
            if v_pages:
                logger.info(
                    f"Spatial search: component '{component_text}' not found, "
                    f"using variant '{variant}' ({component_type})"
                )
                variant_pages |= v_pages

        return variant_pages

    def _get_pages_with_component(
        self, component_text: str, component_type: str, doc_id: str
    ) -> Set[int]:
        """Get set of pages containing a specific component using aggregation"""
        # Use aggregation to get unique pages - no 10k limit!
        from opensearchpy import OpenSearch

        client = OpenSearch(
            hosts=[{"host": "localhost", "port": 9200}],
            http_compress=True,
            use_ssl=False,
        )

        # Aggregation query to get unique pages
        query = {
            "size": 0,  # Don't return documents
            "query": {
                "bool": {
                    "must": [
                        {"term": {"doc_id": doc_id}},
                        {"term": {"component_type": component_type}},
                        {"term": {"component": component_text}},
                    ]
                }
            },
            "aggs": {
                "unique_pages": {
                    "terms": {
                        "field": "page",
                        "size": 10000,  # Max unique pages to retrieve
                    }
                }
            },
        }

        response = client.search(index="pvcfc_pid_spatial_components", body=query)

        # Extract unique pages from aggregation buckets
        buckets = (
            response.get("aggregations", {}).get("unique_pages", {}).get("buckets", [])
        )
        pages = {bucket["key"] for bucket in buckets}

        return pages

    def _get_components_on_page(
        self, component_text: str, component_type: str, doc_id: str, page: int
    ) -> List[Component]:
        """Get all components of specific type on a page (exact text only)."""
        comp_dicts = self.indexer.search_components(
            component_text=component_text,
            component_type=component_type,
            doc_id=doc_id,
            page=page,
            size=100,
        )

        # Convert to Component objects
        components = []
        for comp_dict in comp_dicts:
            bbox = comp_dict["bbox"]
            component = Component(
                text=comp_dict["component"],
                component_type=comp_dict["component_type"],
                bbox=[bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]],
                page=comp_dict["page"],
                doc_id=comp_dict["doc_id"],
                span_id=comp_dict.get("span_id"),
            )
            components.append(component)

        return components

    def _get_components_on_page_with_variants(
        self, component_text: str, component_type: str, doc_id: str, page: int
    ) -> List[Component]:
        """Get components on a page, trying common variants if the exact text fails."""
        components = self._get_components_on_page(
            component_text=component_text,
            component_type=component_type,
            doc_id=doc_id,
            page=page,
        )
        if components:
            return components

        variants = TagVariantGenerator.generate_variants(component_text, component_type)
        all_components: List[Component] = []
        for variant in variants:
            if not variant or variant == component_text:
                continue
            alt_components = self._get_components_on_page(
                component_text=variant,
                component_type=component_type,
                doc_id=doc_id,
                page=page,
            )
            if alt_components:
                logger.info(
                    f"Spatial search: components for '{component_text}' missing on page {page}, "
                    f"using variant '{variant}' ({component_type})"
                )
                all_components.extend(alt_components)

        return all_components
