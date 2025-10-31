"""
Spatial Tag Searcher
Search for tags using spatial proximity of components
"""
from typing import List, Set

from loguru import logger

from app.rag.spatial.component_clusterer import ComponentClusterer
from app.rag.spatial.component_indexer import SpatialComponentIndexer
from app.rag.spatial.schemas import Component, SearchResult


class SpatialTagSearcher:
    """Search for tags using spatial component proximity"""

    def __init__(
        self,
        max_distance_mm: float = 25.0,
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

        # Step 1: Find pages containing ALL components
        pages_with_unit = self._get_pages_with_component(unit, "unit", doc_id)
        pages_with_prefix = self._get_pages_with_component(prefix, "prefix", doc_id)
        pages_with_suffix = self._get_pages_with_component(suffix, "suffix", doc_id)

        candidate_pages = pages_with_unit & pages_with_prefix & pages_with_suffix

        if not candidate_pages:
            logger.warning(
                f"No pages found with all components: {unit}, {prefix}, {suffix}"
            )
            return []

        logger.debug(f"Candidate pages: {sorted(candidate_pages)}")

        # Step 2: For each page, get components and find clusters
        results = []

        for page in candidate_pages:
            # Get all components on this page
            page_units = self._get_components_on_page(unit, "unit", doc_id, page)
            page_prefixes = self._get_components_on_page(prefix, "prefix", doc_id, page)
            page_suffixes = self._get_components_on_page(suffix, "suffix", doc_id, page)

            # Find clusters
            clusters = self.clusterer.find_tag_clusters(
                units=page_units, prefixes=page_prefixes, suffixes=page_suffixes
            )

            # Convert clusters to search results
            for cluster in clusters:
                result = SearchResult(
                    page=page,
                    doc_id=doc_id,
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
                results.append(result)

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)

        logger.info(
            f"Spatial search found {len(results)} results across {len(candidate_pages)} pages"
        )

        return results

    def _get_pages_with_component(
        self, component_text: str, component_type: str, doc_id: str
    ) -> Set[int]:
        """Get set of pages containing a specific component"""
        components = self.indexer.search_components(
            component_text=component_text,
            component_type=component_type,
            doc_id=doc_id,
            size=1000,  # Get all occurrences
        )

        pages = {comp["page"] for comp in components}
        return pages

    def _get_components_on_page(
        self, component_text: str, component_type: str, doc_id: str, page: int
    ) -> List[Component]:
        """Get all components of specific type on a page"""
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
