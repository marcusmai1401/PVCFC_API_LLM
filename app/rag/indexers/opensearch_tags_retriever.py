"""
OpenSearch Tags Retriever
Search sidecar tags index for instrument tag queries

Spec: PVCFC_CADlike_Tag_Extraction_Handoff.md Section 8
"""

import os
from typing import Any, Dict, List, Optional

from loguru import logger
from opensearchpy import OpenSearch

from app.config import get_config


class OpenSearchTagsRetriever:
    """
    Retriever for PID tags sidecar index

    Features:
    - Exact filter by code/num/area
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

            # Exact match on code + num (highest priority)
            code = parts.get("code")
            num = parts.get("num")
            area = parts.get("area")

            if code and num:
                must_clauses = [
                    {"term": {"code": code}},
                    {"term": {"num": num}},
                ]

                if area:
                    must_clauses.append({"term": {"area": area}})

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
                "fields": ["tag^3", "code^2", "num^2"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
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
