"""
Report router for generating comprehensive reports
"""
import asyncio
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_generator, get_retriever
from app.rag.generator import ResponseGenerator
from app.rag.retriever import HybridRetriever
from app.rag.schemas import (
    Citation,
    ErrorResponse,
    ReportRequest,
    ReportResponse,
    ReportSection,
)
from app.utils.metrics import track_request_metrics
from app.utils.tracing import trace_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["report"])


@router.post("/", response_model=ReportResponse, status_code=status.HTTP_200_OK)
async def generate_report(
    request: ReportRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    generator: ResponseGenerator = Depends(get_generator),
) -> ReportResponse:
    """
    Generate comprehensive report on a topic

    Args:
        request: Report request with topic and parameters
        retriever: Hybrid retriever dependency
        generator: Response generator dependency

    Returns:
        ReportResponse with structured sections and citations
    """
    start_time = time.time()
    trace_id = trace_request("report", request.topic)

    try:
        logger.info(
            f"Report request: topic='{request.topic}', sections={request.sections}"
        )

        # Determine sections to generate
        sections_to_generate = request.sections or _default_sections_for_topic(
            request.topic
        )
        sections_to_generate = sections_to_generate[: request.max_sections]

        # Generate sections in parallel
        section_tasks = []
        for section_title in sections_to_generate:
            task = _generate_section(
                section_title,
                request.topic,
                retriever,
                generator,
                request.section_max_tokens,
                request.filters,
            )
            section_tasks.append(task)

        # Wait for all sections
        section_results = await asyncio.gather(*section_tasks)

        # Filter out failed sections
        sections = [s for s in section_results if s is not None]

        # Generate summary if requested
        summary = None
        if request.include_summary:
            summary = await _generate_summary(request.topic, sections, generator)

        # Collect all citations
        all_citations = []
        for section in sections:
            all_citations.extend(section.citations)

        # Deduplicate citations
        unique_citations = _deduplicate_citations(all_citations)

        # Track metrics
        generation_time = (time.time() - start_time) * 1000
        track_request_metrics("report", generation_time, len(unique_citations))

        return ReportResponse(
            topic=request.topic,
            summary=summary,
            sections=sections,
            references=unique_citations if request.include_references else None,
            total_citations=len(unique_citations),
            generation_time_ms=generation_time,
            metadata={
                "sections_requested": len(sections_to_generate),
                "sections_generated": len(sections),
            },
            trace_id=trace_id,
        )

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )


@router.post("/outline", response_model=Dict[str, Any])
async def generate_outline(
    request: ReportRequest, retriever: HybridRetriever = Depends(get_retriever)
) -> Dict[str, Any]:
    """
    Generate report outline without full content
    """
    try:
        # Get relevant documents
        search_results = await retriever.search(
            query=request.topic, top_k=20, filters=request.filters
        )

        # Extract key topics from search results
        topics = _extract_key_topics(search_results)

        # Generate outline structure
        outline = {
            "topic": request.topic,
            "suggested_sections": _default_sections_for_topic(request.topic),
            "key_topics": topics,
            "estimated_citations": len(search_results),
        }

        return outline

    except Exception as e:
        logger.error(f"Error generating outline: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate outline: {str(e)}",
        )


async def _generate_section(
    section_title: str,
    topic: str,
    retriever: HybridRetriever,
    generator: ResponseGenerator,
    max_tokens: int,
    filters: Dict[str, Any] = None,
) -> ReportSection:
    """
    Generate a single report section
    """
    try:
        # Create section-specific query
        section_query = f"{topic} - {section_title}"

        # Retrieve relevant documents for this section
        search_results = await retriever.search(
            query=section_query, top_k=10, filters=filters, use_hyde=True
        )

        if not search_results:
            logger.warning(f"No documents found for section: {section_title}")
            return None

        # Generate section content
        prompt = f"Write a detailed section about '{section_title}' for a report on '{topic}'. Be comprehensive and cite sources."

        content, confidence = await generator.generate(
            query=prompt,
            context=search_results,
            temperature=0.5,  # Lower temperature for factual content
            max_tokens=max_tokens,
        )

        # Format citations for this section
        citations = []
        for idx, result in enumerate(search_results[:5]):  # Top 5 citations per section
            citations.append(
                Citation(
                    chunk_id=result.get("chunk_id", f"chunk_{idx}"),
                    doc_id=result.get("doc_id", "unknown"),
                    page=result.get("page"),
                    text=result.get("text", "")[:150],
                    score=result.get("score", 0.0),
                    metadata=result.get("metadata", {}),
                )
            )

        return ReportSection(
            title=section_title,
            content=content,
            citations=citations,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Error generating section '{section_title}': {str(e)}")
        return None


async def _generate_summary(
    topic: str, sections: List[ReportSection], generator: ResponseGenerator
) -> str:
    """
    Generate executive summary from report sections
    """
    try:
        # Combine section contents
        combined_content = "\n\n".join(
            [f"{s.title}: {s.content[:200]}..." for s in sections]
        )

        prompt = f"Write an executive summary for a report on '{topic}' based on the following sections:\n{combined_content}"

        summary, _ = await generator.generate(
            query=prompt, context=[], temperature=0.5, max_tokens=300
        )

        return summary

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return f"Report on {topic} covering {len(sections)} key areas."


def _default_sections_for_topic(topic: str) -> List[str]:
    """
    Generate default section titles based on topic
    """
    # Generic sections that work for most topics
    return [
        f"Overview of {topic}",
        f"Key Concepts and Definitions",
        f"Current State and Trends",
        f"Challenges and Opportunities",
        f"Best Practices and Recommendations",
        f"Future Outlook",
        f"Conclusion",
    ]


def _extract_key_topics(search_results: List[dict]) -> List[str]:
    """
    Extract key topics from search results
    """
    topics = set()

    for result in search_results[:10]:
        text = result.get("text", "").lower()
        # Simple keyword extraction (can be enhanced)
        words = text.split()
        for word in words:
            if len(word) > 5 and word.isalpha():
                topics.add(word)

    return list(topics)[:20]  # Return top 20 topics


def _deduplicate_citations(citations: List[Citation]) -> List[Citation]:
    """
    Remove duplicate citations based on chunk_id
    """
    seen = set()
    unique = []

    for citation in citations:
        if citation.chunk_id not in seen:
            seen.add(citation.chunk_id)
            unique.append(citation)

    # Sort by score
    unique.sort(key=lambda x: x.score, reverse=True)

    return unique


# Export router
__all__ = ["router"]
