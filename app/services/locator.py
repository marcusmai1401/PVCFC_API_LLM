"""
Locator service for finding entities/symbols in documents.
Optimized for P&ID and technical drawings with bbox support.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from app.rag.schemas import LocationHit

logger = logging.getLogger(__name__)


class LocatorService:
    """Service for locating entities in documents."""

    def __init__(self):
        """Initialize locator service."""
        self.entity_patterns = {
            "equipment": re.compile(r"\b[A-Z]{2,3}\d{5}\b"),  # e.g., KT06101
            "valve": re.compile(r"\b[A-Z]V-?\d{3,5}\b"),  # e.g., XV-101, PV101
            "instrument": re.compile(r"\b[A-Z]{2,3}-?\d{3,5}\b"),  # e.g., PT-101
            "line": re.compile(r'\b\d{1,2}"-[A-Z]{2,3}-\d{3,5}\b'),  # e.g., 4"-HC-10001
        }

    async def locate(
        self,
        query: str,
        retriever: Any,  # HybridRetriever instance
        filters: Optional[Dict[str, List[str]]] = None,
        max_hits: int = 10,
    ) -> Dict[str, Any]:
        """
        Locate entities in documents.

        Args:
            query: Entity/text to locate
            retriever: Retriever instance
            filters: Optional document filters
            max_hits: Maximum hits to return

        Returns:
            Location results with hits and metadata
        """
        try:
            # Detect entity type
            entity_type = self._detect_entity_type(query)

            # Adjust retrieval strategy based on entity type
            if entity_type:
                # For known entities, use exact match first
                results = await self._locate_entity(
                    query, retriever, filters, max_hits * 2
                )
            else:
                # For general text, use hybrid search
                results = await self._locate_text(
                    query, retriever, filters, max_hits * 2
                )

            # Process and rank hits
            hits = self._process_hits(results, query, max_hits)

            return {
                "hits": hits,
                "total_found": len(hits),
                "entity_type": entity_type,
                "query": query,
            }

        except Exception as e:
            logger.error(f"Location failed: {e}")
            raise

    def _detect_entity_type(self, query: str) -> Optional[str]:
        """Detect if query is a known entity type."""
        query_upper = query.upper()

        for entity_type, pattern in self.entity_patterns.items():
            if pattern.match(query_upper):
                logger.debug(f"Detected entity type: {entity_type}")
                return entity_type

        return None

    async def _locate_entity(
        self,
        entity: str,
        retriever: Any,
        filters: Optional[Dict[str, List[str]]],
        k: int,
    ) -> Dict[str, Any]:
        """Locate a specific entity (equipment ID, valve, etc)."""
        # Use BM25 for exact match preference
        results = await retriever.retrieve(
            query=entity,
            k=k,
            filters=filters,
            method="bm25",  # Prefer BM25 for exact matches
            expand_parent=False,  # No expansion for location
        )

        return results

    async def _locate_text(
        self, text: str, retriever: Any, filters: Optional[Dict[str, List[str]]], k: int
    ) -> Dict[str, Any]:
        """Locate general text using hybrid search."""
        results = await retriever.retrieve(
            query=text, k=k, filters=filters, method="hybrid", expand_parent=False
        )

        return results

    def _process_hits(
        self, results: Dict[str, Any], query: str, max_hits: int
    ) -> List[LocationHit]:
        """Process retrieval results into location hits."""
        hits = []
        seen_locations = set()  # Deduplicate by (doc_id, page)

        if not results or not results.get("chunks"):
            return hits

        for chunk, score in zip(results["chunks"], results["scores"]):
            # Extract location info
            doc_id = chunk.get("doc_id", "unknown")
            page = chunk.get("page", 1)
            bbox = chunk.get("bbox")

            # Create location key for deduplication
            loc_key = (doc_id, page, tuple(bbox) if bbox else None)

            if loc_key in seen_locations:
                continue
            seen_locations.add(loc_key)

            # Extract snippet around match
            content = chunk.get("content", "")
            snippet = self._extract_snippet(content, query, window=50)

            # Create hit
            hit = LocationHit(
                doc_id=doc_id,
                page=page,
                bbox=bbox,
                score=score,
                snippet=snippet,
                chunk_id=chunk.get("chunk_id"),
            )
            hits.append(hit)

            if len(hits) >= max_hits:
                break

        # Sort by score
        hits.sort(key=lambda x: x.score, reverse=True)

        return hits

    def _extract_snippet(self, content: str, query: str, window: int = 50) -> str:
        """Extract a snippet around the query match."""
        if not content:
            return ""

        # Case-insensitive search
        query_lower = query.lower()
        content_lower = content.lower()

        # Find query position
        pos = content_lower.find(query_lower)

        if pos == -1:
            # Query not found exactly, return beginning
            return content[: window * 2] + ("..." if len(content) > window * 2 else "")

        # Extract window around match
        start = max(0, pos - window)
        end = min(len(content), pos + len(query) + window)

        snippet = content[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet
