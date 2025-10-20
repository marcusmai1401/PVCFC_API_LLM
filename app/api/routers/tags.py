"""
Tags router - Get available tags from OpenSearch
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tags", tags=["Metadata"])


class TagsResponse(BaseModel):
    """Response model for /tags endpoint"""

    tags: List[str]
    count: int


@router.get("", response_model=TagsResponse)
async def get_tags(request: Request) -> TagsResponse:
    """
    Get all unique tags available in the system.

    Returns a sorted list of all tags present in indexed documents.
    This is a simple aggregation query on OpenSearch - no LLM involved.
    """
    try:
        # Get OpenSearch client from app state
        if not hasattr(request.app.state, "opensearch_client"):
            raise HTTPException(
                status_code=503, detail="OpenSearch client not available"
            )

        os_client = request.app.state.opensearch_client

        # Get index name from settings
        from app.core.config import Settings

        settings = (
            request.app.state.settings
            if hasattr(request.app.state, "settings")
            else Settings()
        )
        index_name = settings.opensearch_index

        # Aggregation query to get unique tags
        query = {
            "size": 0,  # Don't return documents, only aggregation
            "aggs": {
                "unique_tags": {
                    "terms": {
                        "field": "tags.keyword",  # Use keyword subfield for aggregation
                        "size": 1000,  # Max tags to return
                        "order": {"_key": "asc"},  # Sort alphabetically
                    }
                }
            },
        }

        response = os_client.search(index=index_name, body=query)

        # Extract tags from aggregation buckets
        buckets = (
            response.get("aggregations", {}).get("unique_tags", {}).get("buckets", [])
        )
        tags = [bucket["key"] for bucket in buckets if bucket.get("key")]

        logger.info(f"Retrieved {len(tags)} unique tags from OpenSearch")

        return TagsResponse(tags=tags, count=len(tags))

    except Exception as e:
        logger.error(f"Error retrieving tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve tags: {str(e)}"
        )
