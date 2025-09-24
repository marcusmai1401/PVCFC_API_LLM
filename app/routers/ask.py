"""
Ask router for RAG question-answering
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.dependencies import get_generator, get_retriever
from app.rag.generator import ResponseGenerator
from app.rag.retriever import HybridRetriever
from app.rag.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    ErrorResponse,
    QueryIntent,
)
from app.utils.metrics import track_request_metrics
from app.utils.tracing import trace_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("/", response_model=AskResponse, status_code=status.HTTP_200_OK)
async def ask_question(
    request: AskRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: ResponseGenerator = Depends(get_generator),
) -> AskResponse:
    """
    Answer questions based on document corpus

    Args:
        request: Ask request with query and parameters
        retriever: Hybrid retriever dependency
        generator: Response generator dependency

    Returns:
        AskResponse with answer and citations
    """
    start_time = time.time()
    trace_id = trace_request("ask", request.query)

    try:
        # Log request
        logger.info(
            f"Ask request: query='{request.query[:100]}...', top_k={request.top_k}"
        )

        # Detect query intent
        intent = _detect_intent(request.query)
        logger.debug(f"Detected intent: {intent}")

        # Retrieve relevant documents
        search_results = await retriever.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            use_hyde=request.enable_hyde,
        )

        if not search_results:
            logger.warning(f"No documents found for query: {request.query}")
            return AskResponse(
                query=request.query,
                answer="I couldn't find relevant information to answer your question.",
                confidence=0.0,
                citations=[],
                intent=intent,
                generation_time_ms=(time.time() - start_time) * 1000,
                trace_id=trace_id,
            )

        # Generate response
        response_text, confidence = await generator.generate(
            query=request.query,
            context=search_results,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            enable_cove=request.enable_cove,
        )

        # Format citations
        citations = _format_citations(search_results, request.citation_style)

        # Apply citation style to response
        if request.citation_style == "inline":
            response_text = _add_inline_citations(response_text, citations)
        elif request.citation_style == "footnote":
            response_text = _add_footnote_citations(response_text, citations)

        # Track metrics
        generation_time = (time.time() - start_time) * 1000
        track_request_metrics("ask", generation_time, len(citations))

        return AskResponse(
            query=request.query,
            answer=response_text,
            confidence=confidence,
            citations=citations,
            intent=intent,
            metadata={
                "num_retrieved": len(search_results),
                "hyde_enabled": request.enable_hyde,
                "cove_enabled": request.enable_cove,
            },
            generation_time_ms=generation_time,
            trace_id=trace_id,
        )

    except Exception as e:
        logger.error(f"Error processing ask request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question: {str(e)}",
        )


@router.post("/explain", response_model=AskResponse)
async def explain_concept(
    request: AskRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: ResponseGenerator = Depends(get_generator),
) -> AskResponse:
    """
    Explain a concept based on documents
    """
    # Modify query for explanation
    request.query = f"Explain: {request.query}"
    return await ask_question(request, retriever, generator)


@router.post("/summarize", response_model=AskResponse)
async def summarize_topic(
    request: AskRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: ResponseGenerator = Depends(get_generator),
) -> AskResponse:
    """
    Summarize information about a topic
    """
    # Modify query for summarization
    request.query = f"Summarize: {request.query}"
    request.top_k = min(request.top_k * 2, 20)  # Get more docs for summary
    return await ask_question(request, retriever, generator)


def _detect_intent(query: str) -> QueryIntent:
    """Detect query intent from text"""
    query_lower = query.lower()

    if any(
        word in query_lower for word in ["what", "who", "when", "where", "why", "how"]
    ):
        return QueryIntent.ASK
    elif any(word in query_lower for word in ["explain", "describe", "clarify"]):
        return QueryIntent.EXPLAIN
    elif any(word in query_lower for word in ["summarize", "summary", "overview"]):
        return QueryIntent.SUMMARIZE
    elif any(word in query_lower for word in ["find", "locate", "search", "show"]):
        return QueryIntent.LOCATE
    elif any(word in query_lower for word in ["compare", "difference", "versus"]):
        return QueryIntent.COMPARE
    elif any(word in query_lower for word in ["report", "analysis", "detail"]):
        return QueryIntent.REPORT
    else:
        return QueryIntent.UNKNOWN


def _format_citations(search_results, style: str) -> list[Citation]:
    """Format search results as citations"""
    citations = []
    for idx, result in enumerate(search_results):
        citations.append(
            Citation(
                chunk_id=result.get("chunk_id", f"chunk_{idx}"),
                doc_id=result.get("doc_id", "unknown"),
                page=result.get("page"),
                text=result.get("text", "")[:200],  # Truncate long text
                score=result.get("score", 0.0),
                metadata=result.get("metadata", {}),
            )
        )
    return citations


def _add_inline_citations(text: str, citations: list[Citation]) -> str:
    """Add inline citations to response text"""
    # Simple implementation - append citation markers
    for i, citation in enumerate(citations, 1):
        marker = f"[{i}]"
        # Add marker after relevant sentences (simplified)
        if i == 1:
            # Add first citation after first sentence
            sentences = text.split(". ")
            if len(sentences) > 0:
                sentences[0] += f" {marker}"
                text = ". ".join(sentences)
    return text


def _add_footnote_citations(text: str, citations: list[Citation]) -> str:
    """Add footnote citations to response text"""
    footnotes = "\n\n---\nReferences:\n"
    for i, citation in enumerate(citations, 1):
        footnotes += f"[{i}] {citation.doc_id}, p.{citation.page or 'N/A'}\n"
    return text + footnotes


# Export router
__all__ = ["router"]
