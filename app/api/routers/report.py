"""
Report router for generating structured reports from multiple queries.
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import Settings
from app.core.metrics import MetricsCollector
from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryIntent, QueryTransformer
from app.rag.reranker import Reranker
from app.rag.retriever import HybridRetriever
from app.rag.schemas import (
    Citation,
    ErrorResponse,
    ReportRequest,
    ReportResponse,
    ReportSection,
)
from app.services.llm import LLMService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["RAG"])


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
    response_model=ReportResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
        503: {"model": ErrorResponse, "description": "Service Unavailable"},
    },
)
async def generate_report(
    request: ReportRequest,
    http_request: Request,
    retriever: HybridRetriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
) -> ReportResponse:
    """
    Generate a structured report from multiple sub-queries.

    Features:
    - Process multiple sub-queries in parallel
    - Generate sections with citations for each query
    - Create executive summary
    - Support markdown and JSON formats

    Use cases:
    - Equipment summary reports
    - Operational parameter compilations
    - Safety guideline summaries
    - Multi-aspect technical reviews
    """
    start_time = time.time()
    trace_id = "unknown"  # get_trace_id() not implemented yet

    logger.info(f"[{trace_id}] Processing report request: {request.topic}")
    logger.debug(f"[{trace_id}] Sub-queries: {len(request.sub_queries)}")

    try:
        # Initialize components
        query_transformer = QueryTransformer(enable_hyde=False)
        reranker = Reranker()
        generator_config = GeneratorConfig(
            llm_tier="heavy",  # Use heavy model for reports
            language=request.language,
            max_answer_length=800,  # Longer for report sections
        )
        generator = ResponseGenerator(config=generator_config)
        llm_service = LLMService(settings=settings)

        # Process each sub-query
        sections = []
        all_citations = []

        for idx, sub_query in enumerate(request.sub_queries):
            # Transform sub-query
            transformed_query = query_transformer.transform(
                query=sub_query, filters=request.filters, language=request.language
            )
            transformed_query.intent = QueryIntent.REPORT

            # Search for relevant documents
            search_results = retriever.search(transformed_query)

            # Rerank results
            reranked = reranker.rerank(query=sub_query, results=search_results)[
                :8
            ]  # Use top 8 for each section

            # Generate answer for sub-query
            generated_answer = generator.generate(
                query=transformed_query, retrieved_docs=reranked
            )

            # Create section
            section_citations = []
            for citation in generated_answer.citations:
                section_citations.append(
                    Citation(
                        doc_id=citation.doc_id,
                        page=citation.page,
                        bbox=None,
                        confidence=citation.relevance_score,
                    )
                )
                all_citations.append(citation)

            section = ReportSection(
                heading=f"{idx + 1}. {sub_query.replace('?', '')}",
                content=generated_answer.answer,
                citations=section_citations,
                sub_query=sub_query,
            )
            sections.append(section)

        # Generate summary
        summary = ""
        if sections:
            summary_prompt = (
                f"Tóm tắt ngắn gọn (2-3 câu) cho báo cáo về: {request.topic}\n"
            )
            summary_prompt += "Các điểm chính:\n"
            for section in sections[:3]:  # Use first 3 sections
                summary_prompt += f"- {section.content[:100]}...\n"

            try:
                summary = await llm_service.complete(
                    prompt=summary_prompt, max_tokens=150, tier="light"
                )
            except:
                summary = f"Báo cáo về {request.topic} với {len(sections)} phần."

        # Deduplicate citations
        unique_citations = {}
        for citation in all_citations:
            key = (citation.doc_id, citation.page)
            if key not in unique_citations:
                unique_citations[key] = citation

        # Calculate latency
        total_latency = (time.time() - start_time) * 1000

        # Set request.state for logging middleware
        http_request.state.timing_breakdown = {
            "total_ms": round(total_latency),
            "sections_count": len(sections),
        }
        http_request.state.citations = list(unique_citations.values())

        # Record metrics
        MetricsCollector.record_request(endpoint="/report", status="success")
        MetricsCollector.record_latency(
            endpoint="/report", step="total", duration=total_latency / 1000
        )
        MetricsCollector.record_pipeline_step("report_generation", total_latency / 1000)

        has_citations = len(unique_citations) > 0
        MetricsCollector.record_citation_metrics("/report", has_citations)

        # Build response
        title = (
            f"Báo cáo: {request.topic}"
            if request.language == "vi"
            else f"Report: {request.topic}"
        )

        return ReportResponse(
            title=title,
            sections=sections,
            summary=summary,
            meta={
                "total_latency_ms": round(total_latency),
                "sections_count": len(sections),
                "total_citations": len(unique_citations),
                "format": request.format,
                "language": request.language,
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
