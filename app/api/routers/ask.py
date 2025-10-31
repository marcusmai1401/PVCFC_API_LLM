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
from app.rag.weaviate_retriever import WeaviateRetriever

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ask", tags=["RAG"])


# Dependencies will be injected from main app
async def get_retriever(request: Request):
    """Get retriever from app state (HybridRetriever or WeaviateRetriever)."""
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
    retriever=Depends(get_retriever),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    """
    Answer a question using RAG pipeline.

    Pipeline:
    1. Query transformation (normalize, HyDE)
    2. Hybrid retrieval (Weaviate vector + OpenSearch BM25 + BGE reranking if enabled)
    3. Legacy reranking (cross-encoder, only if BGE disabled)
    4. Generation with citations
    5. Chain-of-Verification (optional, controlled by ENABLE_COVE)

    Note: When BGE reranking is enabled, step 3 is skipped (reranking happens in step 2).
    """
    start_time = time.time()
    trace_id = "unknown"  # get_trace_id() not implemented yet

    logger.info(f"[{trace_id}] Processing ask request: {request.query[:100]}...")

    try:
        # Validate query
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=422, detail="Query must not be empty")

        # ===== Conversation Management =====
        # Get or create conversation
        conversation_manager = getattr(
            http_request.app.state, "conversation_manager", None
        )
        conv_id = request.conversation_id
        is_new_conversation = False
        conversation_history = []
        conversation_summary = None

        if conversation_manager:
            try:
                if not conv_id:
                    # Create new conversation
                    conv_id = conversation_manager.create_conversation(
                        user_id=request.user_id, language=request.language
                    )
                    is_new_conversation = True
                    logger.info(f"[{trace_id}] Created new conversation: {conv_id}")

                    # Record metric
                    from app.core.metrics import conversation_created

                    conversation_created.labels(language=request.language).inc()
                else:
                    # Fetch existing history
                    conversation_history = conversation_manager.get_history(
                        conv_id, max_turns=10
                    )
                    logger.info(
                        f"[{trace_id}] Retrieved {len(conversation_history)} turns for conv {conv_id}"
                    )

                    # Check if we need to summarize
                    meta = conversation_manager.get_metadata(conv_id)
                    if meta:
                        from app.core.conversation.summarizer import (
                            ConversationSummarizer,
                        )

                        summarizer = ConversationSummarizer(
                            summarize_every_n_turns=settings.summarize_every_n_turns
                        )

                        if summarizer.should_summarize(
                            meta["total_turns"], meta.get("last_summarized_turn", 0)
                        ):
                            # Summarize oldest turns
                            conversation_summary = summarizer.summarize_history(
                                conversation_history[:6],  # Summarize first 6 turns
                                model_tier="light",
                                language=request.language,
                            )
                            if conversation_summary:
                                conversation_manager.update_summarization_marker(
                                    conv_id, meta["total_turns"]
                                )
                                logger.info(f"[{trace_id}] Summarized conversation")

                                # Record metric
                                from app.core.metrics import conversation_summarizations

                                conversation_summarizations.labels(
                                    language=request.language
                                ).inc()

            except Exception as e:
                logger.warning(f"[{trace_id}] Conversation management error: {e}")
                # Fall back to single-turn mode
                conv_id = None
                is_new_conversation = True
                conversation_history = []
        else:
            # No conversation manager available
            logger.debug(f"[{trace_id}] Conversation manager not available")
            conv_id = None
            is_new_conversation = True

        # Initialize components
        query_transformer = QueryTransformer(enable_hyde=request.hyde)
        # Configure reranker: avoid cross-encoder for non-English to prevent NaN scores and empty results
        from app.rag.reranker import RerankConfig

        # Determine rerank top_k based on degrade mode (will be calculated after retrieval)
        # For now, use settings.top_rerank as initial value
        rerank_method = "cross_encoder" if request.language == "en" else "score"

        # Configure generator based on execution mode
        if request.execution_mode == "production":
            generator_tier = "heavy"
        elif request.execution_mode == "light_only":
            generator_tier = "light"
        else:  # heavy_only
            generator_tier = "heavy"

        # Calculate effective vision flag: settings AND request
        # Vision is enabled only if BOTH settings allow it AND request doesn't disable it
        effective_vision_enabled = settings.vision_page_selector_enabled and (
            request.enable_vision_generation
            if hasattr(request, "enable_vision_generation")
            else True
        )

        generator_config = GeneratorConfig(
            llm_tier=generator_tier,
            language=request.language,
            confidence_mode=request.confidence_mode
            if hasattr(request, "confidence_mode") and request.confidence_mode
            else "legacy",
            enable_vision_generation=effective_vision_enabled,
        )
        generator = ResponseGenerator(config=generator_config)
        cove = ChainOfVerification(settings=settings)

        # Step 1: Query Transformation (sync) with optional query_type override
        transform_start = time.time()
        transformed_query = query_transformer.transform(
            query=request.query,
            filters=request.filters,
            language=request.language,
            query_type_override=getattr(
                request, "query_type", None
            ),  # NEW: pass override if present
        )
        transform_time = (time.time() - transform_start) * 1000

        logger.debug(f"[{trace_id}] Query transformed in {transform_time:.0f}ms")

        # Step 2: Hybrid Retrieval using search() (with cache)
        # Try cache first
        from app.core.cache_manager import get_retrieval_cache

        cache = get_retrieval_cache()
        # BUG-022 FIX: Include query_type in cache key to prevent collision
        # Previously, 'pid' and 'technical_doc' queries with same text shared cache,
        # causing wrong results (e.g., P&ID query returns technical doc cached results)
        cache_key_data = (
            transformed_query.normalized,
            request.query_type,  # CRITICAL: Separate cache per query type
            request.filters,
            request.max_context,
        )

        cached_results = cache.get(*cache_key_data)
        cache_hit = cached_results is not None

        if cache_hit:
            # Cache HIT - skip retrieval and rerank
            logger.info(f"[{trace_id}] Cache HIT - skipping retrieval & rerank")
            reranked_results = cached_results
            retrieve_time = 0
            rerank_time = 0
            # Still need to check degrade mode from cached results
            retrieval_results = cached_results  # For degrade check
        else:
            # Cache MISS - perform retrieval with smart routing
            retrieve_start = time.time()

            # Query type routing (REQUIRED: user must select pid or technical_doc)
            user_query_type = request.query_type  # Now required, no default

            if user_query_type == "pid":
                # User explicitly selected P&ID mode
                logger.info(f"[{trace_id}] User-selected P&ID retrieval mode")
                tags_retriever = getattr(http_request.app.state, "tags_retriever", None)
                if tags_retriever:
                    retrieval_results = tags_retriever.search(transformed_query)
                else:
                    # BUG-001 FIX: Enhanced warning when P&ID retriever unavailable
                    logger.warning(
                        f"[{trace_id}] ⚠️ P&ID tags retriever not available (initialization failed or disabled). "
                        f"Falling back to default hybrid retriever. P&ID-specific features may be degraded."
                    )
                    retrieval_results = retriever.search(transformed_query)

            elif user_query_type == "technical_doc":
                # User explicitly selected Technical Doc mode
                logger.info(f"[{trace_id}] User-selected Technical Doc retrieval mode")

                # Use technical doc retriever if available
                tech_doc_retriever = getattr(
                    http_request.app.state, "tech_doc_retriever", None
                )
                if tech_doc_retriever:
                    retrieval_results = tech_doc_retriever.search(transformed_query)
                else:
                    # BUG-001 FIX: Enhanced warning when technical doc retriever unavailable
                    logger.warning(
                        f"[{trace_id}] ⚠️ Technical document retriever not available (initialization failed or disabled). "
                        f"Falling back to default hybrid retriever. Query-time enhancements may be unavailable."
                    )
                    retrieval_results = retriever.search(transformed_query)

            else:
                # Invalid query_type (should not happen due to Pydantic validation)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid query_type: {user_query_type}. Must be 'pid' or 'technical_doc'",
                )

            retrieve_time = (time.time() - retrieve_start) * 1000

            logger.debug(
                f"[{trace_id}] Retrieved {len(retrieval_results)} results in {retrieve_time:.0f}ms"
            )

        # Check for degrade mode from retrieval results
        degrade_mode = any(
            result.metadata.get("degrade_mode", False) if result.metadata else False
            for result in retrieval_results
        )
        degrade_reason = None
        if degrade_mode:
            for result in retrieval_results:
                if result.metadata and result.metadata.get("degrade_mode"):
                    degrade_reason = result.metadata.get("degrade_reason")
                    break
            logger.warning(
                f"[{trace_id}] Operating in degrade mode: {degrade_reason[:100] if degrade_reason else 'unknown'}"
            )

        # Step 3: Reranking (sync) - skip if cache hit
        if not cache_hit:
            # If BGE reranking was already applied inside retriever, skip route-level rerank
            if getattr(settings, "enable_bge_rerank", False):
                logger.info(
                    f"[{trace_id}] BGE reranking enabled at retriever level; skipping route-level rerank"
                )
                # Use retrieval_results directly (already reranked by BGE)
                reranked_results = retrieval_results[: request.max_context]
                rerank_time = 0
                # Define rerank_top_k for downstream meta (use BGE top_k if available)
                try:
                    rerank_top_k = settings.bge_rerank_top_k
                except Exception:
                    rerank_top_k = len(reranked_results)

                # Cache the results
                cache.set(
                    cache_key_data[0],  # query (normalized)
                    reranked_results,  # results to cache
                    cache_key_data[1],  # filters (dict or None)
                    cache_key_data[2],  # k (max_context)
                )
                logger.info(
                    f"[{trace_id}] Cache MISS - cached {len(reranked_results)} results (BGE rerank)"
                )
            else:
                # Determine rerank top_k based on degrade mode
                rerank_top_k = (
                    settings.rerank_top_n_when_degrade
                    if degrade_mode
                    else settings.top_rerank
                )

                # Create reranker with appropriate top_k
                reranker = Reranker(
                    config=RerankConfig(method=rerank_method, top_k=rerank_top_k)
                )
                rerank_start = time.time()
                reranked_results = reranker.rerank(
                    query=request.query, results=retrieval_results
                )

                # DIAGNOSTIC: Log rerank results
                logger.info(
                    f"[DIAGNOSTIC] Rerank input: {len(retrieval_results)} results, "
                    f"method={rerank_method}, top_k={rerank_top_k}"
                )
                logger.info(
                    f"[DIAGNOSTIC] Rerank output: {len(reranked_results)} results"
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
                            config=_RerankConfig(
                                method="score", top_k=request.max_context
                            )
                        )
                        reranked_results = _fallback_reranker.rerank(
                            query=request.query, results=retrieval_results
                        )
                        logger.info(
                            f"[DIAGNOSTIC] Fallback rerank output: {len(reranked_results)} results"
                        )
                    except Exception as _:
                        # Keep as empty; downstream will handle
                        pass

                # Apply max_context limit
                reranked_results = reranked_results[: request.max_context]
                rerank_time = (time.time() - rerank_start) * 1000

                # Cache the reranked results for future requests
                cache.set(
                    cache_key_data[0],  # query (normalized)
                    reranked_results,  # results to cache
                    cache_key_data[1],  # filters (dict or None)
                    cache_key_data[2],  # k (max_context)
                )
                logger.info(
                    f"[{trace_id}] Cache MISS - cached {len(reranked_results)} results"
                )

        logger.debug(
            f"[{trace_id}] Reranked to {len(reranked_results)} results in {rerank_time:.0f}ms"
        )

        # Step 3.5: Check if this is a P&ID tag location query (special handling)
        from app.rag.pid_tag_handler import get_tag_handler

        tag_handler = get_tag_handler()
        tag_detection = tag_handler.detect_tag_query(request.query)

        if tag_detection.is_tag_query and tag_detection.tag_name:
            # Special handling for tag location queries - bypass LLM
            logger.info(
                f"[{trace_id}] Tag location query detected: {tag_detection.tag_name}. "
                f"Using direct answer from retrieval."
            )

            answer_text, tag_citations = tag_handler.create_tag_location_answer(
                tag_name=tag_detection.tag_name,
                retrieval_results=reranked_results,
                language=request.language,
            )

            # Create a mock generated_answer structure
            from dataclasses import dataclass, field
            from typing import Any, Dict
            from typing import List as ListType

            @dataclass
            class TagAnswer:
                answer: str
                confidence: float
                citations: ListType
                metadata: Dict[str, Any] = field(default_factory=dict)

            generated_answer = TagAnswer(
                answer=answer_text,
                confidence=0.95,  # High confidence for direct matches
                citations=tag_citations,
                metadata={
                    "tag_location_query": True,
                    "tag_name": tag_detection.tag_name,
                },
            )
            generate_time = 0  # No LLM generation time

            logger.info(
                f"[{trace_id}] Tag answer generated: {len(tag_citations)} citations, "
                f"pages: {[c.page for c in tag_citations[:5] if hasattr(c, 'page')]}"
            )
        else:
            # Normal LLM generation
            # Step 4: Generation (sync)
            generate_start = time.time()

            # Build conversation-aware prompt if we have history
            if conversation_history or conversation_summary:
                from app.core.conversation.prompt_builder import (
                    build_conversation_aware_prompt,
                )
                from app.core.token_budget import TokenBudgetManager

                # Enforce token budget before building prompt
                token_manager = TokenBudgetManager(
                    max_tokens=settings.max_conversation_context_tokens
                )

                # Build context text from retrieved docs
                context_text = "\n---\n".join(
                    [doc.text for doc in reranked_results[:8]]
                )

                # Trim history to fit token budget
                trimmed_history = token_manager.trim_to_budget(
                    history=conversation_history,
                    context_text=context_text,
                    reserved_for_response=1000,
                )

                # BUG-031 FIX: Validate total tokens don't overflow model limit
                is_budget_valid = token_manager.validate_total_budget(
                    trimmed_history=trimmed_history,
                    context_text=context_text,
                    current_query=request.query,
                    reserved_for_response=1000,
                    model_max_tokens=settings.max_conversation_context_tokens,
                )

                if not is_budget_valid:
                    # Token overflow - further trim history or warn
                    logger.error(
                        f"[{trace_id}] Token budget overflow after trimming! "
                        f"Trimmed history may still exceed model limits."
                    )
                    # Emergency fallback: use only last 2 turns
                    trimmed_history = (
                        trimmed_history[-2:]
                        if len(trimmed_history) > 2
                        else trimmed_history
                    )
                    logger.info(
                        f"[{trace_id}] Emergency trim: reduced to last {len(trimmed_history)} turns"
                    )

                logger.debug(
                    f"[{trace_id}] Token budget: trimmed history from "
                    f"{len(conversation_history)} to {len(trimmed_history)} turns"
                )

                # Record trim metric if history was trimmed
                if len(trimmed_history) < len(conversation_history):
                    from app.core.metrics import conversation_token_trims

                    conversation_token_trims.inc()

                # Build prompt with trimmed history
                conversation_prompt = build_conversation_aware_prompt(
                    current_query=request.query,
                    history=trimmed_history,  # Use trimmed history
                    retrieved_docs=reranked_results,
                    language=request.language,
                    summary=conversation_summary,
                )

                # Create a modified query object with conversation-aware prompt
                from dataclasses import replace

                conv_aware_query = replace(
                    transformed_query, original=conversation_prompt
                )
                generated_answer = generator.generate(
                    query=conv_aware_query, retrieved_docs=reranked_results
                )
            else:
                # Standard single-turn generation
                generated_answer = generator.generate(
                    query=transformed_query, retrieved_docs=reranked_results
                )

            generate_time = (time.time() - generate_start) * 1000

        logger.debug(f"[{trace_id}] Generated answer in {generate_time:.0f}ms")

        # Step 5: Chain-of-Verification (optional)
        warnings = []
        final_answer = generated_answer.answer
        cove_time = 0.0  # Initialize cove_time

        # Run CoVe only if enabled in settings AND not in light_only mode
        if settings.enable_cove and request.execution_mode != "light_only":
            cove_start = time.time()
            # Pass global_confidence from generation to CoVe for smart warning logic
            verification_result = await cove.run_verification(
                answer=final_answer,
                retriever=retriever,
                max_claims=3,
                global_confidence=generated_answer.confidence,  # Pass generation confidence
            )
            cove_time = (time.time() - cove_start) * 1000

            # Update answer and collect warnings
            final_answer = verification_result["adjusted_answer"]
            warnings = verification_result.get("warnings", [])

            logger.debug(
                f"[{trace_id}] CoVe verification in {cove_time:.0f}ms "
                f"(global_conf={generated_answer.confidence:.2f}, verification_rate={verification_result.get('verification_rate', 0):.0%})"
            )

        # Calculate total latency
        total_latency = (time.time() - start_time) * 1000

        # Set request.state for logging middleware
        timing_breakdown = {
            "transform_ms": round(transform_time),
            "retrieve_ms": round(retrieve_time),
            "rerank_ms": round(rerank_time),
            "generate_ms": round(generate_time),
        }
        if settings.enable_cove and request.execution_mode != "light_only":
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

        if settings.enable_cove and request.execution_mode != "light_only":
            MetricsCollector.record_pipeline_step("cove_verification", cove_time / 1000)

        # Build metadata lookup from reranked_results (for enriching citations with tags)
        metadata_lookup = {}  # (doc_id, page) -> metadata
        if reranked_results:
            for r in reranked_results:
                key = (r.doc_id, r.page)
                if r.metadata:
                    metadata_lookup[key] = r.metadata

        # Convert citations to response format
        citations_list = []
        for citation in generated_answer.citations:
            # Ensure page has a valid value (default to 1 if None)
            page_num = citation.page if citation.page is not None else 1

            # Clamp confidence score to [0, 1] range
            confidence = None
            # Handle both RetrievalResult (score) and GeneratedCitation (relevance_score)
            score_value = None
            if (
                hasattr(citation, "relevance_score")
                and citation.relevance_score is not None
            ):
                score_value = citation.relevance_score
            elif hasattr(citation, "score") and citation.score is not None:
                score_value = citation.score

            if score_value is not None:
                try:
                    score = float(score_value)
                    confidence = max(0.0, min(1.0, score))
                except (ValueError, TypeError):
                    confidence = None

            # Extract pdf_path with multi-layer fallback
            pdf_path_value = None

            # Layer 1: From citation object directly
            try:
                if hasattr(citation, "pdf_path") and citation.pdf_path:
                    pdf_path_value = citation.pdf_path
            except Exception:
                pass

            # Layer 2: From metadata_lookup (retrieval results)
            if not pdf_path_value:
                lookup_key = (citation.doc_id, page_num)
                if lookup_key in metadata_lookup:
                    retrieved_meta = metadata_lookup[lookup_key]
                    pdf_path_value = retrieved_meta.get("pdf_path")

            # Layer 3: From app.state.doc_id_map
            if not pdf_path_value:
                try:
                    if hasattr(http_request.app.state, "doc_id_map"):
                        doc_info = http_request.app.state.doc_id_map.get(
                            citation.doc_id
                        )
                        if isinstance(doc_info, dict):
                            pdf_path_value = doc_info.get("pdf_path")
                        elif isinstance(doc_info, str):
                            # Legacy format: doc_id -> pdf_path string directly
                            pdf_path_value = doc_info
                except Exception as e:
                    logger.debug(
                        f"Failed to lookup pdf_path for {citation.doc_id}: {e}"
                    )

            # Set kwargs
            kwargs = {}
            if pdf_path_value:
                kwargs["pdf_path"] = pdf_path_value

            # Extract bbox if available
            bbox_data = None
            try:
                if hasattr(citation, "bbox") and citation.bbox:
                    bbox_data = citation.bbox
            except Exception:
                pass

            # Get metadata: prioritize from citation object, fallback to lookup
            citation_metadata = None

            # First check if citation already has metadata (from generator)
            if hasattr(citation, "metadata") and citation.metadata:
                citation_metadata = citation.metadata
            else:
                # Fallback: lookup from reranked_results
                lookup_key = (citation.doc_id, page_num)
                if lookup_key in metadata_lookup:
                    retrieved_meta = metadata_lookup[lookup_key]
                    # Extract relevant fields for citation metadata
                    citation_metadata = {}
                    if "tags" in retrieved_meta:
                        citation_metadata["tags"] = retrieved_meta["tags"]
                    if "equipment_type" in retrieved_meta:
                        citation_metadata["equipment_type"] = retrieved_meta[
                            "equipment_type"
                        ]
                    if "doc_type" in retrieved_meta:
                        citation_metadata["doc_type"] = retrieved_meta["doc_type"]
                    # Only include if not empty
                    if not citation_metadata:
                        citation_metadata = None

            citations_list.append(
                Citation(
                    doc_id=citation.doc_id,
                    page=page_num,
                    bbox=bbox_data,
                    confidence=confidence,
                    metadata=citation_metadata,
                    **kwargs,
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

                    # Enrich pdf_path with multi-layer fallback (same as generator citations)
                    pdf_path_value = None

                    # Layer 1: From retrieval result metadata
                    if r.metadata and r.metadata.get("pdf_path"):
                        pdf_path_value = r.metadata.get("pdf_path")

                    # Layer 2: From app.state.doc_id_map
                    if not pdf_path_value:
                        try:
                            if hasattr(http_request.app.state, "doc_id_map"):
                                _map = http_request.app.state.doc_id_map
                                _docid = r.doc_id or (
                                    r.metadata.get("doc_id") if r.metadata else None
                                )
                                if _docid and _docid in _map:
                                    # Extract pdf_path from doc_info dict
                                    doc_info = _map[_docid]
                                    if isinstance(doc_info, dict):
                                        pdf_path_value = doc_info.get("pdf_path")
                                    elif isinstance(doc_info, str):
                                        # Legacy format: direct string path
                                        pdf_path_value = doc_info
                        except Exception:
                            pass

                    # Extract metadata for fallback citations
                    fallback_metadata = None
                    if r.metadata:
                        fallback_metadata = {}
                        if "tags" in r.metadata:
                            fallback_metadata["tags"] = r.metadata["tags"]
                        if "equipment_type" in r.metadata:
                            fallback_metadata["equipment_type"] = r.metadata[
                                "equipment_type"
                            ]
                        if "doc_type" in r.metadata:
                            fallback_metadata["doc_type"] = r.metadata["doc_type"]
                        if not fallback_metadata:
                            fallback_metadata = None

                    citations_list.append(
                        Citation(
                            doc_id=r.doc_id
                            or (r.metadata.get("doc_id") if r.metadata else "unknown"),
                            page=page_num,
                            bbox=None,
                            confidence=confidence,
                            pdf_path=pdf_path_value,  # Already enriched above
                            metadata=fallback_metadata,
                        )
                    )
                except Exception:
                    # Ensure robust fallback even if some fields are missing
                    page_num = (
                        r.page if hasattr(r, "page") and r.page is not None else 1
                    )

                    # Enrich pdf_path even in exception path
                    exception_pdf_path = None
                    try:
                        _docid = r.doc_id if hasattr(r, "doc_id") else None
                        if _docid and hasattr(http_request.app.state, "doc_id_map"):
                            doc_info = http_request.app.state.doc_id_map.get(_docid)
                            if isinstance(doc_info, dict):
                                exception_pdf_path = doc_info.get("pdf_path")
                            elif isinstance(doc_info, str):
                                exception_pdf_path = doc_info
                    except Exception:
                        pass

                    # Try to extract metadata even in exception path
                    exception_metadata = None
                    try:
                        if hasattr(r, "metadata") and r.metadata:
                            exception_metadata = {}
                            if "tags" in r.metadata:
                                exception_metadata["tags"] = r.metadata["tags"]
                            if "equipment_type" in r.metadata:
                                exception_metadata["equipment_type"] = r.metadata[
                                    "equipment_type"
                                ]
                            if "doc_type" in r.metadata:
                                exception_metadata["doc_type"] = r.metadata["doc_type"]
                            if not exception_metadata:
                                exception_metadata = None
                    except Exception:
                        pass

                    citations_list.append(
                        Citation(
                            doc_id=r.doc_id
                            if hasattr(r, "doc_id") and r.doc_id
                            else "unknown",
                            page=page_num,
                            bbox=None,
                            confidence=None,
                            pdf_path=exception_pdf_path,
                            metadata=exception_metadata,
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
        # Determine current k values (may be different if in degrade mode)
        # For bm25_k_current: use actual retriever config or degrade value
        # Handle different retriever types
        from app.rag.hybrid_weaviate_opensearch_retriever import (
            HybridWeaviateOpenSearchRetriever,
        )

        if isinstance(retriever, WeaviateRetriever):
            # Weaviate mode: use its config
            bm25_k_current = (
                retriever.config.retrieval_limit if hasattr(retriever, "config") else 50
            )
        elif isinstance(retriever, HybridWeaviateOpenSearchRetriever):
            # Modern Hybrid mode: use opensearch_limit
            bm25_k_current = (
                retriever.config.opensearch_limit
                if hasattr(retriever, "config")
                else 50
            )
        else:
            # FAISS mode: use HybridRetriever config or degrade value
            bm25_k_current = (
                settings.bm25_k_when_degrade
                if degrade_mode
                else (
                    retriever.config.k_bm25
                    if hasattr(retriever, "config")
                    and hasattr(retriever.config, "k_bm25")
                    else 50
                )
            )
        # For top_rerank_current: use actual reranker config if available
        top_rerank_current = rerank_top_k if not cache_hit else settings.top_rerank

        # Prepare meta dict with comprehensive Phase 2 fields
        meta_dict = {
            # Base fields
            "latency_ms": round(total_latency),
            "breakdown": {
                "transform_ms": round(transform_time),
                "retrieve_ms": round(retrieve_time),
                "rerank_ms": round(rerank_time),
                "generate_ms": round(generate_time),
            },
            "k": request.max_context,
            "execution_mode": request.execution_mode,
            "trace_id": trace_id,
            # Model information
            "model_generation": generated_answer.metadata.get(
                "model", settings.llm_model_heavy
            )
            if isinstance(generated_answer.metadata, dict)
            else settings.llm_model_heavy,
            "model_query_transform": settings.llm_model_light or "gemini-2.5-flash",
            "embed_model": settings.embedding_model or "gemini-embedding-001",
            # Degrade mode information
            "degrade_mode": degrade_mode,
            "degrade_reason": degrade_reason if degrade_mode else None,
            # Current k values (adjusted for degrade mode)
            "bm25_k_current": bm25_k_current,
            "top_rerank_current": top_rerank_current,
            # Feature flags (reflect effective runtime values)
            "vision_page_selector_enabled": effective_vision_enabled,
            "text_range_scan_enabled": settings.text_range_scan_enabled,
            # Cache
            "cache_hit": cache_hit,
            # Query type (user-selected, no auto-detect)
            "query_type": request.query_type,
        }

        # Backward compatibility: add "model" alias for "model_generation"
        meta_dict["model"] = meta_dict["model_generation"]

        # Include vision generation metadata if present (Phase 2 - Day 11 & 12)
        if isinstance(generated_answer.metadata, dict):
            vision_meta = generated_answer.metadata.get("vision_generation")
            if vision_meta is not None:
                meta_dict["vision_generation"] = vision_meta

                # Add vision skip metrics (Day 12)
                strategy_meta = vision_meta.get("vision_strategy", {})
                if strategy_meta:
                    meta_dict["vision_skip_metrics"] = {
                        "vision_used": vision_meta.get("pages_used") is not None
                        and len(vision_meta.get("pages_used", [])) > 0,
                        "vision_skipped": strategy_meta.get("should_use_vision")
                        is False,
                        "skip_reason": strategy_meta.get("reason"),
                        "keywords_matched": strategy_meta.get("keywords_matched", []),
                        "prioritize_visual": strategy_meta.get(
                            "prioritize_visual", False
                        ),
                    }
            elif effective_vision_enabled:
                # Vision was enabled but not used (no strategy metadata)
                meta_dict["vision_skip_metrics"] = {
                    "vision_used": False,
                    "vision_skipped": True,
                    "skip_reason": "no_pages_available",
                    "keywords_matched": [],
                    "prioritize_visual": False,
                }

        # Build debug details for UI
        # 1. Retrieval details (separate BM25 and FAISS results, or Weaviate)
        # Always populate, even on cache hit (use cached results in that case)
        retrieval_details = None
        if retrieval_results:  # Will have results either from retrieval or cache
            # Check if using Weaviate (Phase 4) or FAISS (legacy)
            is_weaviate = any(
                hasattr(r, "source") and r.source and "weaviate" in r.source.lower()
                for r in retrieval_results
            )

            if is_weaviate:
                # Weaviate mode: show all results as one list
                weaviate_docs = [
                    {
                        "chunk_id": r.chunk_id,
                        "text": r.text[:200] + "..." if len(r.text) > 200 else r.text,
                        "score": round(r.score, 4) if r.score else 0.0,
                        "doc_id": r.doc_id,
                        "page": r.page,
                    }
                    for r in retrieval_results
                ][
                    :10
                ]  # Top 10 for UI
                retrieval_details = {
                    "weaviate": weaviate_docs,
                    "total_retrieved": len(retrieval_results),
                    "retriever_type": "weaviate",
                    "from_cache": cache_hit,
                }
            else:
                # FAISS mode (legacy): separate BM25 and FAISS
                bm25_docs = [
                    {
                        "chunk_id": r.chunk_id,
                        "text": r.text[:200] + "..." if len(r.text) > 200 else r.text,
                        "score": round(r.score, 4) if r.score else 0.0,
                        "doc_id": r.doc_id,
                        "page": r.page,
                    }
                    for r in retrieval_results
                    if hasattr(r, "source") and r.source == "bm25"
                ][
                    :10
                ]  # Top 10 for UI
                faiss_docs = [
                    {
                        "chunk_id": r.chunk_id,
                        "text": r.text[:200] + "..." if len(r.text) > 200 else r.text,
                        "score": round(r.score, 4) if r.score else 0.0,
                        "doc_id": r.doc_id,
                        "page": r.page,
                    }
                    for r in retrieval_results
                    if hasattr(r, "source") and r.source == "faiss"
                ][
                    :10
                ]  # Top 10 for UI
                retrieval_details = {
                    "bm25": bm25_docs,
                    "faiss": faiss_docs,
                    "total_retrieved": len(retrieval_results),
                    "retriever_type": "faiss",
                    "degrade_mode": degrade_mode,
                    "from_cache": cache_hit,  # Indicate if these came from cache
                }

        # 2. Reranking details
        # Always populate, even on cache hit (results are same, just from cache)
        reranking_details = None
        if reranked_results:
            reranking_details = {
                "method": rerank_method,
                "input_count": len(retrieval_results) if retrieval_results else 0,
                "output_count": len(reranked_results),
                "top_k": top_rerank_current,
                "from_cache": cache_hit,  # Indicate if these came from cache
                "results": [
                    {
                        "rank": idx + 1,
                        "chunk_id": r.chunk_id,
                        "score": round(r.score, 4) if r.score else 0.0,
                        "text": r.text[:150] + "..." if len(r.text) > 150 else r.text,
                        "doc_id": r.doc_id,
                        "page": r.page,
                    }
                    for idx, r in enumerate(reranked_results[:10])
                ],  # Top 10 for UI
            }

        # 3. Generation details
        generation_details = {
            "model": meta_dict["model_generation"],
            "tier": generator_tier,
            "language": request.language,
            "execution_mode": request.execution_mode,
            "vision_enabled": effective_vision_enabled,
            "cove_enabled": settings.enable_cove
            and request.execution_mode != "light_only",
            "answer_length": len(final_answer),
            "citations_count": len(citations_list),
            "confidence": generated_answer.confidence,
        }
        if isinstance(generated_answer.metadata, dict):
            generation_details["metadata"] = generated_answer.metadata

        # VALIDATION: Assert confidence is in valid range [0, 1]
        # Log error if invalid (helps catch bugs early), but allow to proceed with clamping
        # to avoid breaking production requests due to edge cases
        final_confidence = generated_answer.confidence
        if final_confidence is None or not (0 <= final_confidence <= 1):
            # Extract confidence mode from metadata if available
            conf_mode = "unknown"
            if isinstance(generated_answer.metadata, dict):
                conf_mode = generated_answer.metadata.get("confidence_mode", "unknown")

            logger.error(
                f"[{trace_id}] Invalid confidence value detected: {final_confidence}. "
                f"This indicates a bug in confidence calculation. Clamping to valid range.",
                extra={
                    "confidence_raw": final_confidence,
                    "confidence_mode": conf_mode,
                    "num_citations": len(citations_list),
                    "num_docs": len(reranked_results),
                },
            )
            # Clamp as last resort for production stability, but we've logged the issue
            final_confidence = max(0.0, min(1.0, float(final_confidence or 0.0)))

        # Save conversation turns (with PII redaction if enabled)
        conversation_turn_count = 0
        if conversation_manager and conv_id:
            try:
                from app.utils.redaction import PIIRedactor

                redactor = PIIRedactor(enabled=settings.enable_pii_redaction)

                # Save user turn
                user_content = redactor.redact(request.query)
                conversation_manager.add_turn(
                    conversation_id=conv_id,
                    role="user",
                    content=user_content,
                    metadata={"language": request.language},
                )

                # Record metric
                from app.core.metrics import conversation_turns

                conversation_turns.labels(role="user").inc()

                # Save assistant turn
                assistant_content = redactor.redact(final_answer)
                conversation_manager.add_turn(
                    conversation_id=conv_id,
                    role="assistant",
                    content=assistant_content,
                    metadata={
                        "model": meta_dict.get("model_generation"),
                        "citations_count": len(citations_list),
                        "confidence": final_confidence,
                        "latency_ms": round(total_latency),
                    },
                )

                # Record metric
                conversation_turns.labels(role="assistant").inc()

                # Get updated turn count
                meta = conversation_manager.get_metadata(conv_id)
                if meta:
                    conversation_turn_count = meta.get("total_turns", 0)

                logger.debug(
                    f"[{trace_id}] Saved conversation turns: total={conversation_turn_count}"
                )

            except Exception as e:
                logger.warning(f"[{trace_id}] Failed to save conversation turns: {e}")

        return AskResponse(
            answer=final_answer,
            citations=citations_list,
            context_used=[result.chunk_id for result in reranked_results],
            confidence=final_confidence,
            meta=meta_dict,
            warnings=warnings if warnings else None,
            conversation_id=conv_id,
            is_new_conversation=is_new_conversation if conv_id else None,
            conversation_turn_count=conversation_turn_count if conv_id else None,
            retrieval_details=retrieval_details,
            reranking_details=reranking_details,
            generation_details=generation_details,
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
