"""
Page Range Expander Module
Groups retrieval results by document and expands context to include consecutive pages
"""
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger


@dataclass
class PageCluster:
    """Represents a cluster of consecutive pages from the same document"""

    doc_id: str
    start_page: int
    end_page: int
    pages: List[int]
    total_score: float
    chunk_ids: List[str]
    avg_score: float = 0.0

    def __post_init__(self):
        """Calculate average score after initialization"""
        if self.pages:
            self.avg_score = self.total_score / len(self.pages)

    @property
    def page_count(self) -> int:
        """Get number of pages in cluster"""
        return len(self.pages)

    @property
    def page_range(self) -> str:
        """Get readable page range string"""
        if self.start_page == self.end_page:
            return f"p{self.start_page}"
        return f"p{self.start_page}-{self.end_page}"


@dataclass
class PageRangeConfig:
    """Configuration for page range expansion"""

    max_pages_to_scan: int = 5  # Maximum pages to include in expansion
    min_cluster_score: float = 0.1  # Minimum total score for a cluster
    gap_tolerance: int = 1  # Max gap between pages to consider consecutive
    score_decay: float = 0.8  # Score decay for expanded pages
    enable_expansion: bool = True  # Enable/disable expansion


class PageRangeExpander:
    """
    Expands retrieval results to include consecutive page ranges
    for better context and comprehension
    """

    def __init__(self, config: Optional[PageRangeConfig] = None):
        """
        Initialize PageRangeExpander

        Args:
            config: Configuration for page range expansion
        """
        self.config = config or PageRangeConfig()
        self.chunk_loader = None  # Will be set when integrated

    def expand_results(
        self,
        results: List[Any],  # List[RetrievalResult]
        max_results: Optional[int] = None,
    ) -> List[Any]:
        """
        Expand retrieval results to include page ranges

        Args:
            results: List of retrieval results with doc_id and page metadata
            max_results: Maximum number of results to return

        Returns:
            Expanded results with page ranges
        """
        if not self.config.enable_expansion:
            return results

        # Group results by document
        doc_groups = self._group_by_document(results)

        # Find page clusters for each document
        all_clusters = []
        for doc_id, doc_results in doc_groups.items():
            clusters = self._find_page_clusters(doc_id, doc_results)
            all_clusters.extend(clusters)

        # Sort clusters by total score
        all_clusters.sort(key=lambda c: c.total_score, reverse=True)

        # Select top clusters within page limit
        selected_clusters = self._select_top_clusters(all_clusters)

        # Expand selected clusters to full page content
        expanded_results = self._expand_clusters(selected_clusters, results)

        # Limit results if specified
        if max_results:
            expanded_results = expanded_results[:max_results]

        logger.info(
            f"Page range expansion: {len(results)} chunks -> "
            f"{len(selected_clusters)} clusters -> {len(expanded_results)} expanded results"
        )

        return expanded_results

    def _group_by_document(self, results: List[Any]) -> Dict[str, List[Any]]:
        """Group results by doc_id"""
        doc_groups = defaultdict(list)

        for result in results:
            doc_id = getattr(result, "doc_id", None) or result.metadata.get("doc_id")
            if doc_id:
                doc_groups[doc_id].append(result)
            else:
                # Results without doc_id go to a special group
                doc_groups["_unknown"].append(result)

        return doc_groups

    def _find_page_clusters(
        self, doc_id: str, doc_results: List[Any]
    ) -> List[PageCluster]:
        """
        Find clusters of consecutive pages in a document

        Args:
            doc_id: Document ID
            doc_results: Results from this document

        Returns:
            List of page clusters
        """
        # Sort results by page number
        page_results = []
        for result in doc_results:
            page = getattr(result, "page", None) or result.metadata.get("page", 1)
            score = getattr(result, "score", 0.0)
            chunk_id = getattr(result, "chunk_id", "") or result.metadata.get(
                "chunk_id", ""
            )
            page_results.append((page, score, chunk_id, result))

        page_results.sort(key=lambda x: x[0])  # Sort by page

        # Build clusters of consecutive pages
        clusters = []
        current_cluster = None

        for page, score, chunk_id, result in page_results:
            if current_cluster is None:
                # Start new cluster
                current_cluster = PageCluster(
                    doc_id=doc_id,
                    start_page=page,
                    end_page=page,
                    pages=[page],
                    total_score=score,
                    chunk_ids=[chunk_id],
                )
            elif page <= current_cluster.end_page + self.config.gap_tolerance:
                # Add to current cluster (handle gaps and duplicates)
                if page not in current_cluster.pages:
                    current_cluster.pages.append(page)
                    current_cluster.pages.sort()
                    current_cluster.end_page = max(current_cluster.end_page, page)
                current_cluster.total_score += score
                current_cluster.chunk_ids.append(chunk_id)
            else:
                # Gap too large, save current cluster and start new one
                if current_cluster.total_score >= self.config.min_cluster_score:
                    clusters.append(current_cluster)

                current_cluster = PageCluster(
                    doc_id=doc_id,
                    start_page=page,
                    end_page=page,
                    pages=[page],
                    total_score=score,
                    chunk_ids=[chunk_id],
                )

        # Add final cluster
        if (
            current_cluster
            and current_cluster.total_score >= self.config.min_cluster_score
        ):
            clusters.append(current_cluster)

        # Post-process clusters to ensure they respect max_pages_to_scan
        processed_clusters = []
        for cluster in clusters:
            if cluster.page_count <= self.config.max_pages_to_scan:
                processed_clusters.append(cluster)
            else:
                # Split large clusters
                split_clusters = self._split_large_cluster(cluster)
                processed_clusters.extend(split_clusters)

        return processed_clusters

    def _split_large_cluster(self, cluster: PageCluster) -> List[PageCluster]:
        """
        Split a large cluster into smaller ones respecting max_pages_to_scan

        Args:
            cluster: Large cluster to split

        Returns:
            List of smaller clusters
        """
        max_pages = self.config.max_pages_to_scan
        split_clusters = []

        # Simple sliding window approach
        for i in range(0, len(cluster.pages), max_pages):
            sub_pages = cluster.pages[i : i + max_pages]
            if not sub_pages:
                break

            # Calculate score for this sub-cluster (proportional)
            sub_score = cluster.total_score * (len(sub_pages) / len(cluster.pages))
            sub_chunk_ids = cluster.chunk_ids[i : i + max_pages]

            sub_cluster = PageCluster(
                doc_id=cluster.doc_id,
                start_page=min(sub_pages),
                end_page=max(sub_pages),
                pages=sub_pages,
                total_score=sub_score,
                chunk_ids=sub_chunk_ids,
            )
            split_clusters.append(sub_cluster)

        return split_clusters

    def _select_top_clusters(self, clusters: List[PageCluster]) -> List[PageCluster]:
        """
        Select top clusters considering page limits

        Args:
            clusters: All clusters sorted by score

        Returns:
            Selected clusters within page limit
        """
        selected = []
        total_pages = 0

        for cluster in clusters:
            if total_pages + cluster.page_count <= self.config.max_pages_to_scan * 2:
                # Allow up to 2x max_pages across different documents
                selected.append(cluster)
                total_pages += cluster.page_count
            elif total_pages == 0:
                # Always include at least one cluster
                selected.append(cluster)
                break

        return selected

    def _expand_clusters(
        self, clusters: List[PageCluster], original_results: List[Any]
    ) -> List[Any]:
        """
        Expand clusters to include full page content

        Args:
            clusters: Selected page clusters
            original_results: Original retrieval results

        Returns:
            Expanded results with full page content
        """
        expanded_results = []
        seen_pages = set()  # Track (doc_id, page) to avoid duplicates

        # Create a map of original results for reference
        original_map = {}
        for result in original_results:
            doc_id = getattr(result, "doc_id", None) or result.metadata.get("doc_id")
            page = getattr(result, "page", None) or result.metadata.get("page", 1)
            key = (doc_id, page)
            if key not in original_map or result.score > original_map[key].score:
                original_map[key] = result

        for cluster in clusters:
            for page in cluster.pages:
                key = (cluster.doc_id, page)

                if key in seen_pages:
                    continue
                seen_pages.add(key)

                if key in original_map:
                    # Use original result
                    expanded_results.append(original_map[key])
                else:
                    # Need to load this page (expanded)
                    expanded_result = self._load_page_content(
                        cluster.doc_id,
                        page,
                        cluster.avg_score * self.config.score_decay,
                    )
                    if expanded_result:
                        expanded_results.append(expanded_result)

        return expanded_results

    def _load_page_content(self, doc_id: str, page: int, score: float) -> Optional[Any]:
        """
        Load full content for a specific page

        Args:
            doc_id: Document ID
            page: Page number
            score: Score to assign

        Returns:
            RetrievalResult with full page content or None
        """
        # Prefer external loader if provided (avoids circular imports)
        if callable(self.chunk_loader):
            try:
                return self.chunk_loader(doc_id=doc_id, page=page, score=score)
            except Exception as e:
                logger.warning(f"chunk_loader failed for {doc_id} p{page}: {e}")
                return None

        # Fallback built-in loader (best-effort)
        try:
            # Lazy import to avoid circular dependency
            import json
            import re
            from pathlib import Path

            import fitz  # PyMuPDF

            from app.rag.retriever import RetrievalResult  # type: ignore

            # Load doc_id_map lazily
            doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
            pdf_path = None
            if doc_id_map_path.exists():
                try:
                    with open(doc_id_map_path, "r", encoding="utf-8") as f:
                        mapping = json.load(f)
                        pdf_path = mapping.get(doc_id)
                except Exception:
                    pdf_path = None

            if not pdf_path:
                logger.debug(f"No pdf_path found for doc_id={doc_id}")
                return None

            p = Path(pdf_path)
            if not p.exists():
                logger.debug(f"PDF path does not exist: {p}")
                return None

            # Extract page text
            doc = fitz.open(str(p))
            if page < 1 or page > len(doc):
                doc.close()
                return None
            page_obj = doc[page - 1]
            raw_text = page_obj.get_text()
            doc.close()

            # Simple clean
            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
            text = re.sub(r"\s+", " ", "\n".join(lines)).strip()

            if not text:
                return None

            # Build RetrievalResult-like object
            metadata = {"doc_id": doc_id, "page": page, "pdf_path": str(p)}
            result = RetrievalResult(
                chunk_id=f"page_{doc_id}_{page}",
                text=text,
                score=float(score),
                source="page_expanded",
                metadata=metadata,
                doc_id=doc_id,
                page=page,
                bbox=None,
                parent_id=None,
            )
            return result
        except Exception as e:
            logger.warning(f"Fallback page loader failed for {doc_id} p{page}: {e}")
            return None

    def analyze_clusters(self, results: List[Any]) -> Dict[str, Any]:
        """
        Analyze page clustering for debugging/monitoring

        Args:
            results: Retrieval results

        Returns:
            Analysis statistics
        """
        doc_groups = self._group_by_document(results)

        stats = {
            "total_results": len(results),
            "unique_documents": len(doc_groups),
            "clusters": [],
        }

        for doc_id, doc_results in doc_groups.items():
            clusters = self._find_page_clusters(doc_id, doc_results)
            for cluster in clusters:
                stats["clusters"].append(
                    {
                        "doc_id": doc_id,
                        "page_range": cluster.page_range,
                        "page_count": cluster.page_count,
                        "total_score": round(cluster.total_score, 3),
                        "avg_score": round(cluster.avg_score, 3),
                    }
                )

        stats["total_clusters"] = len(stats["clusters"])
        stats["clusters"].sort(key=lambda c: c["total_score"], reverse=True)

        return stats
