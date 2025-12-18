"""
Deep Discovery Search Service
Keyword-based document search using OpenSearch Aggregation

Features:
- Keyword-based search (no vector similarity)
- Returns ALL documents containing keyword
- Aggregation by doc_id for unique documents
- Optional filtering by category/doc_type
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from loguru import logger

from app.config.pipeline_config import get_config


@dataclass
class DeepSearchResult:
    """Single document result from deep search"""

    doc_id: str
    filename: str
    category: str
    doc_type: str
    occurrence_count: int
    first_page: int
    pdf_path: str
    snippet: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "category": self.category,
            "doc_type": self.doc_type,
            "occurrence_count": self.occurrence_count,
            "occurrence_count": self.occurrence_count,
            "first_page": self.first_page,
            "pdf_path": self.pdf_path,
            "snippet": self.snippet,
        }


@dataclass
class DeepSearchResponse:
    """Response from deep search endpoint"""

    query: str
    total_documents: int
    results: List[DeepSearchResult] = field(default_factory=list)
    results_by_category: Dict[str, List[DeepSearchResult]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "query": self.query,
            "total_documents": self.total_documents,
            "results": [r.to_dict() for r in self.results],
            "results_by_category": {
                cat: [r.to_dict() for r in results]
                for cat, results in self.results_by_category.items()
            },
        }


class OpenSearchClientProtocol(Protocol):
    """Protocol for OpenSearch client"""

    def search(self, index: str, body: dict) -> dict:
        """Execute search query"""
        ...


class DeepSearchService:
    """
    Deep Discovery Search using OpenSearch Aggregation

    Features:
    - Keyword-based search (no vector similarity)
    - Returns ALL documents containing keyword
    - Aggregation by doc_id for unique documents
    - Optional filtering by category/doc_type
    """

    def __init__(
        self,
        opensearch_client: Optional[OpenSearchClientProtocol] = None,
        index_name: str = "rag_chunks",
    ):
        """
        Initialize service

        Args:
            opensearch_client: OpenSearch client instance
            index_name: Name of the index to search
        """
        self.client = opensearch_client
        self.index_name = index_name

    def search(
        self,
        keyword: str,
        category_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
        max_documents: int = 10000,
    ) -> DeepSearchResponse:
        """
        Search for all documents containing keyword

        Args:
            keyword: Search keyword
            category_filter: Optional category filter
            doc_type_filter: Optional doc_type filter
            max_documents: Maximum documents to return

        Returns:
            DeepSearchResponse with all matching documents
        """
        if not keyword or not keyword.strip():
            logger.warning("Empty keyword provided for deep search")
            return DeepSearchResponse(
                query=keyword or "",
                total_documents=0,
                results=[],
                results_by_category={},
            )

        keyword = keyword.strip()

        logger.info(
            f"Deep search: keyword='{keyword}', "
            f"category={category_filter}, doc_type={doc_type_filter}"
        )

        # Build filters
        filters = {}
        if category_filter:
            filters["category"] = category_filter
        if doc_type_filter:
            filters["doc_type"] = doc_type_filter

        # Build and execute query
        query = self._build_aggregation_query(keyword, filters, max_documents)

        try:
            response = self._execute_search(query)
            results = self._parse_response(response, keyword)

            # Group results by category
            results_by_category = self._group_by_category(results)

            logger.info(f"Deep search found {len(results)} documents for '{keyword}'")

            return DeepSearchResponse(
                query=keyword,
                total_documents=len(results),
                results=results,
                results_by_category=results_by_category,
            )

        except Exception as e:
            logger.error(f"Deep search failed: {e}")
            raise

    def _build_aggregation_query(
        self, keyword: str, filters: Dict[str, str], max_documents: int
    ) -> Dict[str, Any]:
        """
        Build OpenSearch aggregation query

        Args:
            keyword: Search keyword
            filters: Category/doc_type filters
            max_documents: Maximum document buckets

        Returns:
            OpenSearch query body

        Note: Fields are at root level in rag_chunks index:
            - text, doc_id, category, doc_type, page, file_name
        """
        # Use match query for flexible keyword search
        # match is more flexible than match_phrase_prefix for equipment tags
        must_clauses = [{"match": {"text": {"query": keyword, "operator": "and"}}}]

        # Add filters - fields are at root level, not in metadata
        filter_clauses = []
        if "category" in filters:
            filter_clauses.append({"term": {"category": filters["category"]}})
        if "doc_type" in filters:
            filter_clauses.append({"term": {"doc_type": filters["doc_type"]}})

        # Build query - use doc_id at root level for aggregation
        query = {
            "size": 0,  # We only want aggregations
            "query": {"bool": {"must": must_clauses}},
            "aggs": {
                "unique_documents": {
                    "terms": {
                        "field": "doc_id",  # Root level field
                        "size": max_documents,
                    },
                    "aggs": {
                        "doc_info": {
                            "top_hits": {
                                "size": 1,
                                "_source": ["*"],
                                "sort": [
                                    {
                                        "page": {
                                            "order": "asc",
                                            "unmapped_type": "integer",
                                        }
                                    },
                                    {
                                        "page_start": {
                                            "order": "asc",
                                            "unmapped_type": "integer",
                                        }
                                    },
                                ],
                            }
                        },
                        "occurrence_count": {"value_count": {"field": "_id"}},
                    },
                }
            },
        }

        # Add filters if present
        if filter_clauses:
            query["query"]["bool"]["filter"] = filter_clauses

        return query

    def _execute_search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search query against OpenSearch"""
        if not self.client:
            raise RuntimeError("OpenSearch client not configured")

        return self.client.search(index=self.index_name, body=query)

    def _parse_response(
        self, response: Dict[str, Any], keyword: str
    ) -> List[DeepSearchResult]:
        """
        Parse OpenSearch response to DeepSearchResult list

        Args:
            response: OpenSearch response
            keyword: Original search keyword

        Returns:
            List of DeepSearchResult

        Note: Fields are at root level in rag_chunks index
        """
        results = []

        buckets = (
            response.get("aggregations", {})
            .get("unique_documents", {})
            .get("buckets", [])
        )

        for bucket in buckets:
            doc_id = bucket.get("key", "")
            occurrence_count = int(bucket.get("occurrence_count", {}).get("value", 0))

            # Get document info from top_hits
            hits = bucket.get("doc_info", {}).get("hits", {}).get("hits", [])
            if not hits:
                continue

            # Fields are at root level, not in metadata
            source = hits[0].get("_source", {})

            # DEBUG: Log available keys to find the correct path field
            if len(results) == 0:
                logger.info(f"DEBUG: OpenSearch source keys: {list(source.keys())}")
                logger.info(f"DEBUG: OpenSearch source sample: {source}")

            # Extract snippet around keyword
            text = source.get("text", "")
            snippet = self._extract_snippet(text, keyword)

            # Handle page field - try page first, then page_start
            first_page = source.get("page") or source.get("page_start") or 1

            # Get PDF path from file_path or source, or search recursively
            pdf_path = source.get("file_path") or source.get("source")
            if not pdf_path:
                # Fallback: Search recursively in documents dir
                try:
                    config = get_config()
                    file_name = source.get("file_name", "")
                    if file_name:
                        # Search recursively for the file
                        pdf_path = self._find_pdf_recursive(
                            config.DOCUMENTS_DIR, file_name
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not find PDF for {source.get('file_name')}: {e}"
                    )
                    pdf_path = ""

            results.append(
                DeepSearchResult(
                    doc_id=doc_id,
                    filename=source.get("file_name", ""),
                    category=source.get("category", "UNCATEGORIZED"),
                    doc_type=source.get("doc_type", "Unknown"),
                    occurrence_count=occurrence_count,
                    first_page=first_page,
                    pdf_path=pdf_path,
                    snippet=snippet,
                )
            )

        return results

    def _extract_snippet(
        self, text: str, keyword: str, context_chars: int = 100
    ) -> Optional[str]:
        """
        Extract snippet around keyword occurrence

        Args:
            text: Full text
            keyword: Keyword to find
            context_chars: Characters of context on each side

        Returns:
            Snippet string or None
        """
        if not text or not keyword:
            return None

        keyword_lower = keyword.lower()
        text_lower = text.lower()

        pos = text_lower.find(keyword_lower)
        if pos == -1:
            return None

        start = max(0, pos - context_chars)
        end = min(len(text), pos + len(keyword) + context_chars)

        snippet = text[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def _group_by_category(
        self, results: List[DeepSearchResult]
    ) -> Dict[str, List[DeepSearchResult]]:
        """
        Group results by category

        Args:
            results: List of search results

        Returns:
            Dictionary mapping category to results
        """
        grouped: Dict[str, List[DeepSearchResult]] = {}

        for result in results:
            category = result.category
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(result)

        return grouped

    def _find_pdf_recursive(self, base_dir: Path, filename: str) -> str:
        """
        Recursively search for a PDF file by filename in base_dir.
        Uses a cache to avoid repeated filesystem scans.

        Args:
            base_dir: Base directory to search from (e.g., D:/Data_Raw)
            filename: Filename to search for (e.g., 113_3N4-S4275360.pdf)

        Returns:
            Full path to the file if found, empty string otherwise
        """
        # Use module-level cache for file mapping (built once per session)
        cache_key = f"pdf_path_cache_{base_dir}"

        if not hasattr(self, "_pdf_cache"):
            self._pdf_cache = {}

        # Build cache if not exists
        if cache_key not in self._pdf_cache:
            logger.info(f"Building PDF path cache from {base_dir}...")
            path_map = {}
            try:
                for pdf_file in base_dir.rglob("*.pdf"):
                    # Map filename to full path
                    path_map[pdf_file.name] = str(pdf_file)
                self._pdf_cache[cache_key] = path_map
                logger.info(f"PDF path cache built: {len(path_map)} files indexed")
            except Exception as e:
                logger.error(f"Failed to build PDF cache: {e}")
                self._pdf_cache[cache_key] = {}

        # Lookup from cache
        path_map = self._pdf_cache.get(cache_key, {})
        return path_map.get(filename, "")
