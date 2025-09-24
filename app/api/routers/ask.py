"""
Ask router for RAG question-answering endpoint.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.metrics import MetricsCollector
from app.rag.cove import ChainOfVerification
from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryTransformer
from app.rag.reranker import Reranker
from app.rag.retriever import HybridRetriever
from app.rag.schemas import AskRequest, AskResponse, Citation, ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ask", tags=["RAG"])


# Dependencies will be injected from main app
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
    response_model=AskResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
        503: {"model": ErrorResponse, "description": "Service Unavailable"},
    },
)
async def ask_question(
    request: AskRequest,
    http_request: Request,
    retriever: HybridRetriever = Depends(get_retriever),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    """
    Answer a question using RAG pipeline.

    Pipeline:
    1. Query transformation (normalize, HyDE)
    2. Hybrid retrieval (BM25 + FAISS)
    3. Reranking (cross-encoder)
    4. Generation with citations
    5. Chain-of-Verification (optional)
    """
    start_time = time.time()
    trace_id = "unknown"  # get_trace_id() not implemented yet

    logger.info(f"[{trace_id}] Processing ask request: {request.query[:100]}...")

    try:
        # Validate query
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=422, detail="Query must not be empty")

        # Initialize components
        query_transformer = QueryTransformer(enable_hyde=request.hyde)
        # Configure reranker: avoid cross-encoder for non-English to prevent NaN scores and empty results
        from app.rag.reranker import RerankConfig

        rerank_method = "cross_encoder" if request.language == "en" else "score"
        reranker = Reranker(
            config=RerankConfig(method=rerank_method, top_k=request.max_context)
        )

        # Configure generator based on execution mode
        if request.execution_mode == "production":
            generator_tier = "heavy"
        elif request.execution_mode == "light_only":
            generator_tier = "light"
        else:  # heavy_only
            generator_tier = "heavy"

        generator_config = GeneratorConfig(
            llm_tier=generator_tier, language=request.language
        )
        generator = ResponseGenerator(config=generator_config)
        cove = ChainOfVerification(settings=settings)

        # Step 1: Query Transformation (sync)
        transform_start = time.time()
        transformed_query = query_transformer.transform(
            query=request.query, filters=request.filters, language=request.language
        )
        transform_time = (time.time() - transform_start) * 1000

        logger.debug(f"[{trace_id}] Query transformed in {transform_time:.0f}ms")

        # Step 2: Hybrid Retrieval using search()
        retrieve_start = time.time()
        retrieval_results = retriever.search(transformed_query)
        retrieve_time = (time.time() - retrieve_start) * 1000

        logger.debug(
            f"[{trace_id}] Retrieved {len(retrieval_results)} results in {retrieve_time:.0f}ms"
        )

        # Step 3: Reranking (sync)
        rerank_start = time.time()
        reranked_results = reranker.rerank(
            query=request.query, results=retrieval_results
        )

        # Safety fallback: if cross-encoder produced zero results, retry with score-based reranker
        if (
            len(reranked_results) == 0
            and len(retrieval_results) > 0
            and reranker.config.method == "cross_encoder"
        ):
            logger.warning(
                f"[{trace_id}] Cross-encoder reranking returned 0 results; falling back to score-based rerank"
            )
            try:
                from app.rag.reranker import RerankConfig as _RerankConfig

                _fallback_reranker = Reranker(
                    config=_RerankConfig(method="score", top_k=request.max_context)
                )
                reranked_results = _fallback_reranker.rerank(
                    query=request.query, results=retrieval_results
                )
            except Exception as _:
                # Keep as empty; downstream will handle
                pass

        # Apply max_context limit
        reranked_results = reranked_results[: request.max_context]
        rerank_time = (time.time() - rerank_start) * 1000

        logger.debug(
            f"[{trace_id}] Reranked to {len(reranked_results)} results in {rerank_time:.0f}ms"
        )

        # Step 4: Generation (sync)
        generate_start = time.time()
        generated_answer = generator.generate(
            query=transformed_query, retrieved_docs=reranked_results
        )
        generate_time = (time.time() - generate_start) * 1000

        logger.debug(f"[{trace_id}] Generated answer in {generate_time:.0f}ms")

        # Step 5: Chain-of-Verification (optional)
        warnings = []
        final_answer = generated_answer.answer
        cove_time = 0.0  # Initialize cove_time

        if request.execution_mode != "light_only":  # Skip CoVe in light mode
            cove_start = time.time()
            verification_result = await cove.run_verification(
                answer=final_answer, retriever=retriever, max_claims=3
            )
            cove_time = (time.time() - cove_start) * 1000

            # Update answer and collect warnings
            final_answer = verification_result["adjusted_answer"]
            warnings = verification_result.get("warnings", [])

            logger.debug(f"[{trace_id}] CoVe verification in {cove_time:.0f}ms")

        # Calculate total latency
        total_latency = (time.time() - start_time) * 1000

        # Set request.state for logging middleware
        timing_breakdown = {
            "transform_ms": round(transform_time),
            "retrieve_ms": round(retrieve_time),
            "rerank_ms": round(rerank_time),
            "generate_ms": round(generate_time),
        }
        if request.execution_mode != "light_only":
            timing_breakdown["cove_ms"] = round(cove_time)

        http_request.state.timing_breakdown = timing_breakdown
        http_request.state.citations = generated_answer.citations

        # Record metrics
        MetricsCollector.record_request(endpoint="/ask", status="success")
        MetricsCollector.record_latency(
            endpoint="/ask", step="total", duration=total_latency / 1000
        )
        MetricsCollector.record_pipeline_step("query_transform", transform_time / 1000)
        MetricsCollector.record_pipeline_step("retrieval", retrieve_time / 1000)
        MetricsCollector.record_pipeline_step("rerank", rerank_time / 1000)
        MetricsCollector.record_pipeline_step("generation", generate_time / 1000)

        has_citations = len(generated_answer.citations) > 0
        MetricsCollector.record_citation_metrics("/ask", has_citations)
        MetricsCollector.record_generation(
            generated_answer.confidence, len(generated_answer.citations)
        )

        if request.execution_mode != "light_only":
            MetricsCollector.record_pipeline_step("cove_verification", cove_time / 1000)

        # Convert citations to response format
        citations_list = []
        for citation in generated_answer.citations:
            # Ensure page has a valid value (default to 1 if None)
            page_num = citation.page if citation.page is not None else 1

            # Clamp confidence score to [0, 1] range
            confidence = None
            if citation.relevance_score is not None:
                try:
                    score = float(citation.relevance_score)
                    confidence = max(0.0, min(1.0, score))
                except (ValueError, TypeError):
                    confidence = None

            citations_list.append(
                Citation(
                    doc_id=citation.doc_id,
                    page=page_num,
                    bbox=None,  # Add bbox if available in citation
                    confidence=confidence,
                )
            )

        # Fallback: if LLM did not include inline citations, use top reranked docs
        # Skip this fallback when generator explicitly used an uncited fallback answer
        if not citations_list and reranked_results:
            for r in reranked_results[: min(5, len(reranked_results))]:
                try:
                    # Ensure page has a valid value (default to 1 if None)
                    page_num = r.page if r.page is not None else 1

                    # Clamp confidence score to [0, 1] range for fallback citations
                    confidence = None
                    if r.score is not None:
                        try:
                            score = float(r.score)
                            confidence = max(0.0, min(1.0, score))
                        except (ValueError, TypeError):
                            confidence = None

                    citations_list.append(
                        Citation(
                            doc_id=r.doc_id
                            or (r.metadata.get("doc_id") if r.metadata else "unknown"),
                            page=page_num,
                            bbox=None,
                            confidence=confidence,
                        )
                    )
                except Exception:
                    # Ensure robust fallback even if some fields are missing
                    page_num = (
                        r.page if hasattr(r, "page") and r.page is not None else 1
                    )
                    citations_list.append(
                        Citation(
                            doc_id=r.doc_id
                            if hasattr(r, "doc_id") and r.doc_id
                            else "unknown",
                            page=page_num,
                            bbox=None,
                            confidence=None,
                        )
                    )

        # Final fallback: if answer is still empty, create one from top chunk
        if not final_answer or len(final_answer.strip()) < 10:
            logger.warning(
                f"[{trace_id}] Answer is empty after all attempts, creating fallback from top chunk"
            )

            if reranked_results and len(reranked_results) > 0:
                # Use top chunk to create a summary
                top_chunk = reranked_results[0]
                try:
                    # Try to create a simple summary using light tier
                    from app.services.llm_client import get_llm_client

                    fallback_client = get_llm_client(tier="light")
                    fallback_prompt = f"""Based on this technical document excerpt, provide a brief answer to the question.

Question: {request.query}

Document excerpt:
{top_chunk.text[:500]}

Provide a direct, helpful answer in 1-2 sentences:"""

                    fallback_response = fallback_client.generate(
                        prompt=fallback_prompt, temperature=0.3, max_tokens=150
                    )

                    if fallback_response and fallback_response.content:
                        final_answer = fallback_response.content.strip()
                        # Mark this as uncited fallback
                        generated_answer.metadata["uncited_fallback"] = True
                        warnings.append(
                            "Answer generated from document summary due to processing issues"
                        )
                        logger.info(
                            f"[{trace_id}] Created fallback answer from top chunk"
                        )
                    else:
                        final_answer = (
                            f"Based on the available documents, here is relevant information about your query: "
                            f"{top_chunk.text[:200]}... Please refer to the citations for more details."
                        )
                        warnings.append(
                            "Partial answer provided due to processing limitations"
                        )
                except Exception as e:
                    logger.error(f"[{trace_id}] Failed to create fallback answer: {e}")
                    final_answer = (
                        f"I found relevant information in the documents about '{request.query[:100]}...', "
                        f"but encountered an issue generating a complete answer. "
                        f"Please check the citations below for the source documents."
                    )
                    warnings.append(
                        "Answer generation encountered issues, showing relevant documents"
                    )
            else:
                # No documents at all
                final_answer = (
                    f"I couldn't find specific information about '{request.query[:100]}...' in the available documents. "
                    f"Please try rephrasing your question or check if the relevant documents are indexed."
                )
                warnings.append("No relevant documents found")

        # Build response
        return AskResponse(
            answer=final_answer,
            citations=citations_list,
            context_used=[result.chunk_id for result in reranked_results],
            confidence=generated_answer.confidence,
            meta={
                "latency_ms": round(total_latency),
                "breakdown": {
                    "transform_ms": round(transform_time),
                    "retrieve_ms": round(retrieve_time),
                    "rerank_ms": round(rerank_time),
                    "generate_ms": round(generate_time),
                },
                "model": generated_answer.metadata.get(
                    "model", settings.llm_model_heavy
                ),
                "k": request.max_context,
                "execution_mode": request.execution_mode,
                "trace_id": trace_id,
            },
            warnings=warnings if warnings else None,
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
