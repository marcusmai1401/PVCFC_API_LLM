"""
Locate router for finding entities/symbols in documents.
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import Settings
from app.core.metrics import MetricsCollector
from app.rag.query_transform import QueryIntent, QueryTransformer
from app.rag.retriever import HybridRetriever
from app.rag.schemas import ErrorResponse, LocateRequest, LocateResponse, LocationHit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/locate", tags=["RAG"])


async def get_retriever(request: Request) -> HybridRetriever:
    """Get retriever from app state."""
    if not hasattr(request.app.state, "retriever"):
        raise HTTPException(status_code=503, detail="Retriever not initialized")
    return request.app.state.retriever


async def get_settings(request: Request) -> Settings:
    """Get settings from app state."""
    if not hasattr(request.app.state, "settings"):
        return Settings()
    return request.app.state.settings


@router.post(
    "",
    response_model=LocateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
        503: {"model": ErrorResponse, "description": "Service Unavailable"},
    },
)
async def locate_entity(
    request: LocateRequest,
    http_request: Request,
    retriever: HybridRetriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
) -> LocateResponse:
    """
    Locate entities/symbols in documents.

    Optimized for:
    - Equipment IDs (e.g., KT06101)
    - Valve tags (e.g., XV-101)
    - Instrument tags (e.g., PT-101)
    - Line numbers (e.g., 4"-HC-10001)
    - General text search

    Returns locations with page numbers and bounding boxes (if available).
    """
    start_time = time.time()
    trace_id = "unknown"  # get_trace_id() not implemented yet

    logger.info(f"[{trace_id}] Processing locate request: {request.query}")

    try:
        # Initialize query transformer with LOCATE intent
        query_transformer = QueryTransformer(
            enable_hyde=False
        )  # No HyDE for location queries

        # Transform query
        transformed_query = query_transformer.transform(
            query=request.query, filters=request.filters
        )

        # Force LOCATE intent for this endpoint
        transformed_query.intent = QueryIntent.LOCATE

        # Perform search
        search_results = retriever.search(transformed_query)

        # Convert results to location hits
        hits = []
        seen_locations = set()  # Deduplicate by (doc_id, page)

        for result in search_results[: request.max_hits]:
            # Create location key for deduplication
            loc_key = (result.doc_id, result.page)

            if loc_key in seen_locations:
                continue
            seen_locations.add(loc_key)

            # Extract snippet around match
            snippet = (
                result.text[:200] + "..." if len(result.text) > 200 else result.text
            )

            # Create hit
            hit = LocationHit(
                doc_id=result.doc_id or "unknown",
                page=result.page or 1,
                bbox=result.bbox,
                score=result.score,
                snippet=snippet,
                chunk_id=result.chunk_id,
            )
            hits.append(hit)

        # Calculate latency
        total_latency = (time.time() - start_time) * 1000

        # Set request.state for logging middleware
        http_request.state.timing_breakdown = {
            "search_ms": round(total_latency),
        }
        http_request.state.citations = []  # Locate doesn't have citations

        # Record metrics
        MetricsCollector.record_request(endpoint="/locate", status="success")
        MetricsCollector.record_latency(
            endpoint="/locate", step="total", duration=total_latency / 1000
        )
        MetricsCollector.record_pipeline_step("search", total_latency / 1000)

        # Detect entity type from query
        import re

        entity_type = None
        if re.search(r"\b[A-Z]{2,3}\d{5}\b", request.query.upper()):
            entity_type = "equipment"
        elif re.search(r"\b[A-Z]V-?\d{3,5}\b", request.query.upper()):
            entity_type = "valve"
        elif re.search(r"\b[A-Z]{2,3}-?\d{3,5}\b", request.query.upper()):
            entity_type = "instrument"

        # Build response
        return LocateResponse(
            hits=hits,
            total_found=len(hits),
            meta={
                "latency_ms": round(total_latency),
                "search_method": "hybrid",
                "entity_type": entity_type,
                "query": request.query,
                "trace_id": trace_id,
            },
        )

    except ValueError as e:
        logger.error(f"[{trace_id}] Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError as e:
        logger.error(f"[{trace_id}] Timeout error: {e}")
        raise HTTPException(status_code=503, detail="Request timeout")
    except Exception as e:
        logger.error(f"[{trace_id}] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
