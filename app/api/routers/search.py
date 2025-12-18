"""
Deep Discovery Search API Router
Provides keyword-based document search endpoints

Features:
- Keyword-based search (no LLM or vector search)
- Returns all unique documents containing keyword
- Optional filtering by category and doc_type
- Results grouped by category
- PDF file serving for viewer

Requirements: 5.1, 5.7, 6.4
"""
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.config.pipeline_config import get_config
from app.services.deep_search import DeepSearchResponse, DeepSearchService

router = APIRouter(prefix="/api/search", tags=["search"])


# Response models
class DeepSearchResultModel(BaseModel):
    """Single document result from deep search"""

    doc_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    category: str = Field(..., description="Document category")
    doc_type: str = Field(..., description="Document type within category")
    occurrence_count: int = Field(..., description="Number of keyword occurrences")
    first_page: int = Field(..., description="First page containing keyword")
    pdf_path: str = Field(..., description="Path to PDF file")
    snippet: Optional[str] = Field(None, description="Text snippet around keyword")


class DeepSearchResponseModel(BaseModel):
    """Response from deep search endpoint"""

    query: str = Field(..., description="Original search query")
    total_documents: int = Field(..., description="Total unique documents found")
    results: list[DeepSearchResultModel] = Field(..., description="All search results")
    results_by_category: dict[str, list[DeepSearchResultModel]] = Field(
        ..., description="Results grouped by category"
    )


# Dependency to get DeepSearchService with OpenSearch client from app state
def get_deep_search_service(request: Request) -> DeepSearchService:
    """
    Get DeepSearchService instance with OpenSearch client from app state

    The OpenSearch client is initialized during app startup and stored in app.state.
    This ensures we use the same client connection pool across all requests.
    """
    opensearch_client = None

    # Try to get OpenSearch client from app state
    if hasattr(request.app.state, "opensearch_client"):
        opensearch_client = request.app.state.opensearch_client
        logger.debug("Using OpenSearch client from app state")
    else:
        logger.warning(
            "OpenSearch client not found in app state. "
            "Deep search will fail until OpenSearch is configured."
        )

    return DeepSearchService(opensearch_client=opensearch_client)


# Cache for PDF file paths (built on first request)
_pdf_path_cache: dict[str, str] = {}


def _find_pdf_in_documents(filename: str) -> Optional[Path]:
    """
    Find PDF file by filename in DOCUMENTS_DIR recursively.
    Uses caching for performance.
    """
    global _pdf_path_cache

    # Check cache first
    if filename in _pdf_path_cache:
        cached_path = Path(_pdf_path_cache[filename])
        if cached_path.exists():
            return cached_path

    # Build cache if empty
    if not _pdf_path_cache:
        try:
            config = get_config()
            logger.info(f"Building PDF path cache from {config.DOCUMENTS_DIR}...")
            for pdf_file in config.DOCUMENTS_DIR.rglob("*.pdf"):
                _pdf_path_cache[pdf_file.name] = str(pdf_file)
            logger.info(f"PDF path cache built: {len(_pdf_path_cache)} files")
        except Exception as e:
            logger.error(f"Failed to build PDF cache: {e}")
            return None

    # Lookup from cache
    if filename in _pdf_path_cache:
        return Path(_pdf_path_cache[filename])

    return None


@router.get(
    "/pdf/{filename:path}",
    summary="Serve PDF file",
    description="Serve PDF file from DOCUMENTS_DIR for viewer",
    response_class=FileResponse,
)
async def serve_pdf(filename: str):
    """
    Serve PDF file by filename.

    The file is searched recursively in DOCUMENTS_DIR.
    This endpoint is used by PDF.js viewer for fast rendering.
    """
    # URL decode the filename
    decoded_filename = unquote(filename)

    # Find the file
    pdf_path = _find_pdf_in_documents(decoded_filename)

    if not pdf_path or not pdf_path.exists():
        logger.warning(f"PDF not found: {decoded_filename}")
        raise HTTPException(
            status_code=404, detail=f"PDF not found: {decoded_filename}"
        )

    logger.debug(f"Serving PDF: {pdf_path}")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=decoded_filename,
        headers={
            "Content-Disposition": f'inline; filename="{decoded_filename}"',
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
        },
    )


@router.get(
    "/documents",
    response_model=DeepSearchResponseModel,
    summary="Deep Discovery Search",
    description="""
    Search for all documents containing a specific keyword.

    Unlike RAG search, this returns ALL matching documents without
    vector similarity or top_k limitation. Uses OpenSearch aggregation
    to find unique documents containing the keyword.

    Features:
    - Keyword-based search (no LLM or vector search)
    - Returns all unique documents containing keyword
    - Optional filtering by category and doc_type
    - Results grouped by category

    Requirements: 5.1, 5.7, 6.4
    """,
)
async def deep_search_documents(
    request: Request,
    keyword: str = Query(
        ..., min_length=1, max_length=200, description="Search keyword (required)"
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by category (e.g., ENGINEERING_DESIGN, VENDOR_EQUIPMENT)",
    ),
    doc_type: Optional[str] = Query(
        None, description="Filter by document type (e.g., P&ID, Datasheet)"
    ),
    max_results: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Maximum number of documents to return (default 1000, max 10000)",
    ),
) -> DeepSearchResponseModel:
    """
    Deep Discovery Search - Find all documents containing keyword

    This endpoint performs keyword-based document discovery using OpenSearch
    aggregation. Unlike RAG search, it returns ALL documents containing the
    keyword without vector similarity or top_k limitation.

    Args:
        request: FastAPI request object (for accessing app state)
        keyword: Search keyword (required, 1-200 characters)
        category: Optional category filter (ENGINEERING_DESIGN, VENDOR_EQUIPMENT, etc.)
        doc_type: Optional document type filter (P&ID, Datasheet, etc.)
        max_results: Maximum documents to return (default 1000, max 10000)

    Returns:
        DeepSearchResponseModel with all matching documents grouped by category

    Raises:
        HTTPException 400: Invalid keyword (empty or too long)
        HTTPException 503: Search service unavailable (OpenSearch not configured)
        HTTPException 500: Internal search error
    """
    logger.info(
        f"Deep search request: keyword='{keyword}', "
        f"category={category}, doc_type={doc_type}, max={max_results}"
    )

    # Get service with OpenSearch client from app state
    service = get_deep_search_service(request)

    try:
        response = service.search(
            keyword=keyword,
            category_filter=category,
            doc_type_filter=doc_type,
            max_documents=max_results,
        )

        return DeepSearchResponseModel(
            query=response.query,
            total_documents=response.total_documents,
            results=[
                DeepSearchResultModel(
                    doc_id=r.doc_id,
                    filename=r.filename,
                    category=r.category,
                    doc_type=r.doc_type,
                    occurrence_count=r.occurrence_count,
                    first_page=r.first_page,
                    pdf_path=r.pdf_path,
                    snippet=r.snippet,
                )
                for r in response.results
            ],
            results_by_category={
                cat: [
                    DeepSearchResultModel(
                        doc_id=r.doc_id,
                        filename=r.filename,
                        category=r.category,
                        doc_type=r.doc_type,
                        occurrence_count=r.occurrence_count,
                        first_page=r.first_page,
                        pdf_path=r.pdf_path,
                        snippet=r.snippet,
                    )
                    for r in results
                ]
                for cat, results in response.results_by_category.items()
            },
        )

    except RuntimeError as e:
        logger.error(f"Deep search service error: {e}")
        raise HTTPException(
            status_code=503, detail=f"Search service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Deep search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
