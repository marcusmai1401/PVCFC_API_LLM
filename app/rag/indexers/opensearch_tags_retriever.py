"""
OpenSearch Tags Retriever
Search sidecar tags index for instrument tag queries

Updated with:
- Component-based search (unit/prefix/suffix)
- SUFFIX-only search with multi-prefix handling
- Multi-prefix grouping and ambiguity warnings

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 8
"""

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from loguru import logger
from opensearchpy import OpenSearch

from app.config import get_config


class OpenSearchTagsRetriever:
    """
    Retriever for PID tags sidecar index

    Features:
    - Exact filter by unit/prefix/suffix (updated schema)
    - Component-based search for partial queries
    - SUFFIX-only search with multi-prefix grouping
    - Fuzzy fallback on tag text (n-gram)
    - Returns tag entities with bbox + crop_path
    """

    def __init__(self, index_name: Optional[str] = None):
        """
        Initialize tags retriever

        Args:
            index_name: Index name (default from config)
        """
        self.config = get_config()
        self.index_name = index_name or self.config.TAGS_INDEX_NAME

        # Create OpenSearch client
        host = os.environ.get("OPENSEARCH_HOST", "localhost")
        port = int(os.environ.get("OPENSEARCH_PORT", "9200"))

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            timeout=10,
            max_retries=2,
            retry_on_timeout=True,
        )

        logger.info(f"OpenSearch Tags Retriever initialized: {self.index_name}")

    def search(
        self,
        query: str,
        detected_tags: Optional[List[Dict]] = None,
        top_k: int = 50,
    ) -> List[Dict]:
        """
        Search tags index

        Args:
            query: Query string
            detected_tags: Pre-detected tags from PIDQueryEnhancer
                          [{"tag": "04 PSAL 2207", "parts": {...}}]
            top_k: Number of results to return

        Returns:
            List of tag results with bbox and crop info
        """
        if not self._check_index_exists():
            logger.warning(f"Tags index not found: {self.index_name}")
            return []

        try:
            # Build query
            if detected_tags:
                # Use structured search with detected tags
                opensearch_query = self._build_structured_query(detected_tags)
            else:
                # Fallback to text search
                opensearch_query = self._build_text_query(query)

            # Execute search
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": opensearch_query,
                    "size": top_k,
                    "_source": True,
                },
            )

            # Parse results
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]

                result = {
                    "chunk_id": f"tag_{hit['_id']}",  # Unique ID for fusion
                    "doc_id": source.get("doc_id"),
                    "page": source.get("page"),
                    "text": source.get("tag", ""),  # Tag as text
                    "score": hit["_score"],
                    "source": "tags_index",
                    "bbox": source.get("bbox"),
                    "crop_path": source.get("crop_path"),
                    "tag_parts": source.get("parts", {}),
                    "confidence": source.get("confidence", 1.0),
                }
                results.append(result)

            logger.info(
                f"Tags search returned {len(results)} results "
                f"(query: {query[:50]}...)"
            )

            return results

        except Exception as e:
            logger.error(f"Tags search failed: {e}")
            return []

    def _check_index_exists(self) -> bool:
        """Check if tags index exists"""
        try:
            return self.client.indices.exists(index=self.index_name)
        except Exception:
            return False

    def _build_structured_query(self, detected_tags: List[Dict]) -> Dict:
        """
        Build structured query from detected tag parts

        Args:
            detected_tags: List of detected tags with parts

        Returns:
            OpenSearch query dict
        """
        should_clauses = []

        for tag_info in detected_tags:
            parts = tag_info.get("parts", {})

            # Exact match on prefix + suffix (highest priority)
            prefix = parts.get("prefix")
            suffix = parts.get("suffix")
            unit = parts.get("unit")

            if prefix and suffix:
                must_clauses = [
                    {"term": {"parts.prefix.keyword": prefix}},
                    {"term": {"parts.suffix.keyword": suffix}},
                ]

                if unit:
                    must_clauses.append({"term": {"parts.unit.keyword": unit}})

                should_clauses.append(
                    {
                        "bool": {
                            "must": must_clauses,
                            "boost": 10.0,  # Exact match boost
                        }
                    }
                )

            # Fuzzy fallback on full tag text
            tag_text = tag_info.get("tag", "")
            if tag_text:
                should_clauses.append(
                    {
                        "match": {
                            "tag": {
                                "query": tag_text,
                                "fuzziness": "AUTO",
                                "boost": 5.0,
                            }
                        }
                    }
                )

        if should_clauses:
            return {"bool": {"should": should_clauses}}
        else:
            # Fallback to match_all
            return {"match_all": {}}

    def _build_text_query(self, query: str) -> Dict:
        """
        Build text-based query (fallback when no tags detected)

        Args:
            query: Query text

        Returns:
            OpenSearch query dict
        """
        return {
            "multi_match": {
                "query": query,
                "fields": ["tag^3", "parts.prefix^2", "parts.suffix^2"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }

    def search_by_components(
        self,
        unit: Optional[str] = None,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        variant: Optional[str] = None,
        top_k: int = 50,
    ) -> List[Dict]:
        """
        Search by individual components (flexible filtering)

        Args:
            unit: UNIT filter (e.g., "04")
            prefix: PREFIX filter (e.g., "PAHH")
            suffix: SUFFIX filter (e.g., "5153")
            variant: VARIANT filter (e.g., "A")
            top_k: Results limit

        Returns:
            List of matching tag entities
        """
        if not self._check_index_exists():
            logger.warning(f"Tags index not found: {self.index_name}")
            return []

        filters = []

        if unit:
            filters.append({"term": {"parts.unit.keyword": unit}})
        if prefix:
            filters.append({"term": {"parts.prefix.keyword": prefix}})
        if suffix:
            filters.append({"term": {"parts.suffix.keyword": suffix}})
        if variant:
            filters.append({"term": {"parts.variant.keyword": variant}})

        if not filters:
            logger.warning("No component filters provided for search")
            return []

        query = {"bool": {"filter": filters}}

        try:
            response = self.client.search(
                index=self.index_name, body={"query": query, "size": top_k}
            )

            results = self._parse_results(response)

            logger.info(
                f"Component search: unit={unit}, prefix={prefix}, suffix={suffix}, "
                f"variant={variant} → {len(results)} results"
            )

            return results

        except Exception as e:
            logger.error(f"Component search failed: {e}")
            return []

    def search_by_suffix(self, suffix: str, top_k: int = 50) -> Dict:
        """
        Search by SUFFIX only (handles multi-prefix cases)

        Boosting strategy:
        - Exact suffix match: score × 10.0
        - Sort by page (co-located tags)

        Args:
            suffix: SUFFIX value (e.g., "5153")
            top_k: Results limit

        Returns:
            Grouped results dict with multi-prefix warning
        """
        if not self._check_index_exists():
            logger.warning(f"Tags index not found: {self.index_name}")
            return {"total_tags": 0, "has_ambiguity": False, "groups": []}

        query = {
            "bool": {
                "should": [
                    {
                        "term": {
                            "parts.suffix.keyword": {"value": suffix, "boost": 10.0}
                        }
                    },
                    {"match": {"tag": {"query": suffix, "boost": 1.0}}},
                ]
            }
        }

        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": query,
                    "size": top_k,
                    "sort": [
                        {"_score": "desc"},
                        {"page": "asc"},  # Co-located tags first
                    ],
                },
            )

            results = self._parse_results(response)

            logger.info(f"SUFFIX search '{suffix}' → {len(results)} results")

            # Group by (unit, suffix) and add warnings
            grouped = self._group_and_warn_multi_prefix(results)

            return grouped

        except Exception as e:
            logger.error(f"SUFFIX search failed: {e}")
            return {"total_tags": 0, "has_ambiguity": False, "groups": []}

    def _parse_results(self, response: Dict) -> List[Dict]:
        """
        Parse OpenSearch response into result list

        Args:
            response: OpenSearch response

        Returns:
            List of result dicts
        """
        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]

            result = {
                "chunk_id": f"tag_{hit['_id']}",
                "doc_id": source.get("doc_id"),
                "page": source.get("page"),
                "text": source.get("tag", ""),
                "score": hit["_score"],
                "source": "tags_index",
                "bbox": source.get("bbox"),
                "crop_path": source.get("crop_path"),
                "confidence": source.get("confidence", 1.0),
                # Component fields
                "unit": source.get("unit"),
                "prefix": source.get("prefix"),
                "suffix": source.get("suffix"),
                "variant": source.get("variant"),
                "annotation": source.get("annotation"),
            }
            results.append(result)

        return results

    def _group_and_warn_multi_prefix(self, results: List[Dict]) -> Dict:
        """
        Group results by (unit, suffix) and detect multi-prefix cases

        Args:
            results: List of search results

        Returns:
            Grouped results dict with structure:
            {
                "total_tags": 4,
                "has_ambiguity": True,
                "groups": [
                    {
                        "unit": "04",
                        "suffix": "5153",
                        "prefixes": ["PAHH", "PALL", "PI", "PXT"],
                        "tags": [...],
                        "pages": [54],
                        "co_located": True,
                        "warning": "4 different prefixes found for suffix 5153"
                    }
                ]
            }
        """
        groups_dict = defaultdict(list)

        # Group by (unit, suffix)
        for result in results:
            key = (result.get("unit") or "", result.get("suffix") or "")
            groups_dict[key].append(result)

        groups = []
        has_ambiguity = False

        for (unit, suffix), tags in groups_dict.items():
            prefixes = sorted(
                list(set(t.get("prefix") for t in tags if t.get("prefix")))
            )
            pages = sorted(set(t.get("page") for t in tags if t.get("page")))

            is_ambiguous = len(prefixes) > 1
            if is_ambiguous:
                has_ambiguity = True

            groups.append(
                {
                    "unit": unit if unit else None,
                    "suffix": suffix,
                    "prefixes": prefixes,
                    "tags": tags,
                    "pages": pages,
                    "co_located": len(pages) == 1,  # All on same page
                    "warning": (
                        f"{len(prefixes)} different prefixes found for suffix {suffix}"
                        if is_ambiguous
                        else None
                    ),
                }
            )

        return {
            "total_tags": len(results),
            "has_ambiguity": has_ambiguity,
            "groups": groups,
        }

    def health_check(self) -> Dict[str, Any]:
        """Check index health and stats"""
        try:
            if not self._check_index_exists():
                return {
                    "status": "not_found",
                    "index": self.index_name,
                }

            # Get stats
            stats = self.client.indices.stats(index=self.index_name)
            index_stats = stats["indices"][self.index_name]

            doc_count = index_stats["total"]["docs"]["count"]
            size_bytes = index_stats["total"]["store"]["size_in_bytes"]
            size_mb = round(size_bytes / (1024 * 1024), 2)

            return {
                "status": "healthy",
                "index": self.index_name,
                "doc_count": doc_count,
                "size_mb": size_mb,
            }

        except Exception as e:
            return {
                "status": "error",
                "index": self.index_name,
                "error": str(e),
            }
