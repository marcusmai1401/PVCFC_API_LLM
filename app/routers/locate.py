"""
Locate router for finding entities in documents
"""
import logging
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_retriever
from app.rag.retriever import HybridRetriever
from app.rag.schemas import ErrorResponse, LocateRequest, LocateResponse, LocationInfo
from app.utils.metrics import track_request_metrics
from app.utils.tracing import trace_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/locate", tags=["locate"])


@router.post("/", response_model=LocateResponse, status_code=status.HTTP_200_OK)
async def locate_entity(
    request: LocateRequest, retriever: HybridRetriever = Depends(get_retriever)
) -> LocateResponse:
    """
    Locate specific entities or information in documents

    Args:
        request: Locate request with entity query
        retriever: Hybrid retriever dependency

    Returns:
        LocateResponse with found locations
    """
    start_time = time.time()
    trace_id = trace_request("locate", request.query)

    try:
        logger.info(
            f"Locate request: query='{request.query}', type={request.entity_type}"
        )

        # Enhance query based on entity type
        search_query = _enhance_query_for_entity(request.query, request.entity_type)

        # Search for relevant documents
        search_results = await retriever.search(
            query=search_query,
            top_k=request.top_k,
            filters=request.filters,
            use_hyde=False,  # Direct search for locate
        )

        if not search_results:
            logger.warning(f"No locations found for: {request.query}")
            return LocateResponse(
                query=request.query,
                entity_type=request.entity_type,
                locations=[],
                total_found=0,
                trace_id=trace_id,
            )

        # Extract locations from search results
        locations = _extract_locations(
            search_results, request.query, request.entity_type
        )

        # Track metrics
        generation_time = (time.time() - start_time) * 1000
        track_request_metrics("locate", generation_time, len(locations))

        return LocateResponse(
            query=request.query,
            entity_type=request.entity_type,
            locations=locations[: request.top_k],
            total_found=len(locations),
            metadata={
                "search_enhanced": search_query != request.query,
                "num_searched": len(search_results),
            },
            trace_id=trace_id,
        )

    except Exception as e:
        logger.error(f"Error processing locate request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to locate entity: {str(e)}",
        )


@router.post("/tables", response_model=LocateResponse)
async def locate_tables(
    request: LocateRequest, retriever: HybridRetriever = Depends(get_retriever)
) -> LocateResponse:
    """
    Locate tables in documents
    """
    request.entity_type = "table"
    return await locate_entity(request, retriever)


@router.post("/figures", response_model=LocateResponse)
async def locate_figures(
    request: LocateRequest, retriever: HybridRetriever = Depends(get_retriever)
) -> LocateResponse:
    """
    Locate figures/images in documents
    """
    request.entity_type = "figure"
    return await locate_entity(request, retriever)


@router.post("/sections", response_model=LocateResponse)
async def locate_sections(
    request: LocateRequest, retriever: HybridRetriever = Depends(get_retriever)
) -> LocateResponse:
    """
    Locate document sections
    """
    request.entity_type = "section"
    return await locate_entity(request, retriever)


@router.post("/definitions", response_model=LocateResponse)
async def locate_definitions(
    request: LocateRequest, retriever: HybridRetriever = Depends(get_retriever)
) -> LocateResponse:
    """
    Locate term definitions
    """
    request.entity_type = "definition"
    # Enhance query for definition search
    request.query = f"definition of {request.query} OR {request.query} is defined as"
    return await locate_entity(request, retriever)


def _enhance_query_for_entity(query: str, entity_type: Optional[str]) -> str:
    """
    Enhance search query based on entity type
    """
    if not entity_type:
        return query

    entity_type_lower = entity_type.lower()

    if entity_type_lower == "table":
        return f"{query} table data statistics"
    elif entity_type_lower == "figure":
        return f"{query} figure image diagram chart"
    elif entity_type_lower == "section":
        return f"{query} section chapter part"
    elif entity_type_lower == "definition":
        return f"definition {query} meaning term"
    elif entity_type_lower == "formula":
        return f"{query} formula equation calculation"
    elif entity_type_lower == "reference":
        return f"{query} reference citation source"
    else:
        return query


def _extract_locations(
    search_results: List[dict], query: str, entity_type: Optional[str]
) -> List[LocationInfo]:
    """
    Extract location information from search results
    """
    locations = []
    query_terms = set(query.lower().split())

    for result in search_results:
        text = result.get("text", "")
        text_lower = text.lower()

        # Calculate relevance score
        relevance_score = _calculate_relevance(text_lower, query_terms, entity_type)

        if relevance_score > 0.1:  # Threshold for inclusion
            # Extract snippet around match
            snippet = _extract_snippet(text, query_terms, max_length=200)

            locations.append(
                LocationInfo(
                    doc_id=result.get("doc_id", "unknown"),
                    page=result.get("page", 0),
                    bbox=result.get("bbox"),
                    text_snippet=snippet,
                    confidence=min(relevance_score, 1.0),
                    metadata={
                        "chunk_id": result.get("chunk_id"),
                        "section": result.get("metadata", {}).get("section"),
                        "match_type": _determine_match_type(text_lower, entity_type),
                    },
                )
            )

    # Sort by confidence
    locations.sort(key=lambda x: x.confidence, reverse=True)

    return locations


def _calculate_relevance(
    text: str, query_terms: set, entity_type: Optional[str]
) -> float:
    """
    Calculate relevance score for text
    """
    score = 0.0

    # Check for query term matches
    for term in query_terms:
        if term in text:
            score += 0.3
            # Bonus for exact match
            if f" {term} " in f" {text} ":
                score += 0.2

    # Entity type specific scoring
    if entity_type:
        if entity_type.lower() == "table" and "table" in text:
            score += 0.3
        elif entity_type.lower() == "figure" and any(
            word in text for word in ["figure", "fig", "image"]
        ):
            score += 0.3
        elif entity_type.lower() == "definition" and any(
            word in text for word in ["defined", "definition", "means"]
        ):
            score += 0.4

    return score


def _extract_snippet(text: str, query_terms: set, max_length: int = 200) -> str:
    """
    Extract relevant snippet from text
    """
    # Find first occurrence of any query term
    first_match_pos = len(text)
    for term in query_terms:
        pos = text.lower().find(term)
        if pos != -1 and pos < first_match_pos:
            first_match_pos = pos

    if first_match_pos == len(text):
        # No match found, return beginning
        return text[:max_length] + ("..." if len(text) > max_length else "")

    # Extract around match
    start = max(0, first_match_pos - max_length // 2)
    end = min(len(text), first_match_pos + max_length // 2)

    snippet = text[start:end]

    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def _determine_match_type(text: str, entity_type: Optional[str]) -> str:
    """
    Determine the type of match found
    """
    if entity_type:
        return entity_type.lower()

    # Try to infer type from content
    if "table" in text:
        return "table"
    elif any(word in text for word in ["figure", "fig", "image", "diagram"]):
        return "figure"
    elif any(word in text for word in ["section", "chapter", "part"]):
        return "section"
    elif any(word in text for word in ["defined", "definition", "means"]):
        return "definition"
    else:
        return "text"


# Export router
__all__ = ["router"]
