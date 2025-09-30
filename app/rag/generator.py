"""
RAG Generator Module - Sprint 1.4
Generates answers with citations from retrieved documents
"""
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Literal, Optional, Tuple

from loguru import logger

from app.rag.query_transform import QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult
from app.services.llm_client import get_llm_client

# Lazy-loaded doc_id_map cache for citation enrichment
_DOC_ID_MAP_CACHE = None

# Constants for confidence calibration
MINMAX_EPS = 1e-6
UNCERTAINTY_PATTERNS = [
    r"\b(i think|not sure|uncertain|maybe|approximately|around)\b",
    r"\b(có thể|không chắc|ước chừng|khoảng|xấp xỉ)\b",
]


def _get_doc_id_map() -> Dict[str, str]:
    global _DOC_ID_MAP_CACHE
    if _DOC_ID_MAP_CACHE is not None:
        return _DOC_ID_MAP_CACHE
    try:
        import json
        from pathlib import Path

        path = Path("artifacts/ingestion/doc_id_map.json")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _DOC_ID_MAP_CACHE = json.load(f)
        else:
            _DOC_ID_MAP_CACHE = {}
    except Exception:
        _DOC_ID_MAP_CACHE = {}
    return _DOC_ID_MAP_CACHE


def _rescale_scores(
    raw_scores: List[float],
    method: str = "minmax",
    pct_low: float = 5.0,
    pct_high: float = 95.0,
) -> List[float]:
    """Rescale scores to 0..1 range using min-max or percentile fallback.

    Args:
        raw_scores: List of raw scores to rescale
        method: Rescaling method (currently only 'minmax' is used)
        pct_low: Lower percentile for fallback (default 5.0)
        pct_high: Upper percentile for fallback (default 95.0)

    Returns:
        List of rescaled scores in [0, 1] range
    """
    if not raw_scores:
        return []
    if len(raw_scores) == 1:
        return [0.5]  # Single score gets neutral confidence

    arr = raw_scores[:]
    min_v = min(arr)
    max_v = max(arr)
    range_v = max_v - min_v

    # Try min-max first
    if range_v > MINMAX_EPS:
        return [(s - min_v) / range_v for s in raw_scores]

    # Fallback: percentile window
    sorted_s = sorted(arr)

    def percentile(p: float) -> float:
        """Compute percentile without numpy"""
        k = (len(sorted_s) - 1) * p / 100.0
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(sorted_s[int(k)])
        return float(sorted_s[f] * (c - k) + sorted_s[c] * (k - f))

    lo = percentile(pct_low)
    hi = percentile(pct_high)
    rng = hi - lo

    if rng <= MINMAX_EPS:
        return [0.5 for _ in raw_scores]  # All similar scores

    return [max(0.0, min(1.0, (s - lo) / rng)) for s in raw_scores]


def _compute_calibrated_confidence(
    retrieval_results: List[RetrievalResult],
    citations: List["Citation"],
    answer_text: str,
    context_items: List[RetrievalResult],
    cfg: "GeneratorConfig",
    top_m: int = 5,
    length_threshold_chars: int = 200,
) -> Tuple[float, Dict[str, Any]]:
    """Compute calibrated confidence score with boosts and penalties.

    Args:
        retrieval_results: List of retrieval results (for scores)
        citations: Parsed citations with doc_id/page info
        answer_text: Generated answer text
        context_items: Context chunks passed to LLM (with metadata)
        cfg: Generator configuration
        top_m: Number of top results to use for base score (default 5)
        length_threshold_chars: Minimum answer length for boost (default 200)

    Returns:
        Tuple of (confidence_score, components_dict)
    """

    # 1) Extract best score from each retrieval result
    def best_score(item: RetrievalResult) -> Optional[float]:
        """Extract the best available score from a result"""
        # Try fused_score, rerank_score, then score
        for attr in ["fused_score", "rerank_score", "score"]:
            if hasattr(item, attr):
                v = getattr(item, attr)
                if v is not None:
                    return float(v)
        return None

    top = retrieval_results[:top_m] if retrieval_results else []
    raw_scores = [best_score(x) for x in top]
    raw_scores = [s for s in raw_scores if s is not None]

    # 2) Rescale and compute base confidence
    rescaled = _rescale_scores(raw_scores)
    base_conf = float(mean(rescaled)) if rescaled else 0.3  # Conservative default

    components = {
        "raw_top_scores": raw_scores,
        "rescaled_top_scores": rescaled,
        "base": round(base_conf, 4),
        "boosts": {},
        "penalties": {},
    }
    conf = base_conf

    # 3) Boost: full-page evidence
    full_page_used = any(
        getattr(ci, "metadata", {}).get("full_page", False)
        for ci in (context_items or [])
    )
    if full_page_used:
        conf += 0.10
        components["boosts"]["full_page"] = 0.10

    # 4) Boost: multiple consistent citations (same doc or clustered pages)
    same_doc_or_cluster = False
    if citations and len(citations) >= 2:
        # Normalize citations to (doc_id, page) tuples
        norm = []
        for c in citations:
            doc = c.doc_id
            page = c.page
            if doc:
                norm.append((str(doc), int(page) if isinstance(page, int) else None))

        if len(norm) >= 2:
            docs = [d for d, _ in norm]
            pages = [p for _, p in norm if p is not None]

            # Check if all from same doc
            if len(set(docs)) == 1:
                same_doc_or_cluster = True
            # Or if pages are clustered (within 2 pages)
            elif pages and len(pages) >= 2:
                pages_sorted = sorted(pages)
                same_doc_or_cluster = (pages_sorted[-1] - pages_sorted[0]) <= 2

    if same_doc_or_cluster:
        conf += 0.05
        components["boosts"]["multi_citation_consistency"] = 0.05

    # 5) Boost: adequate answer length
    if answer_text and len(answer_text.strip()) >= length_threshold_chars:
        conf += 0.05
        components["boosts"]["length"] = 0.05

    # 6) Penalty: uncited fallback
    uncited_fallback = any(
        getattr(ci, "metadata", {}).get("uncited_fallback", False)
        for ci in (context_items or [])
    )
    if uncited_fallback:
        conf -= 0.10
        components["penalties"]["uncited_fallback"] = -0.10

    # 7) Penalty: uncertainty phrases
    if answer_text:
        if any(
            re.search(p, answer_text, flags=re.IGNORECASE) for p in UNCERTAINTY_PATTERNS
        ):
            conf -= 0.07
            components["penalties"]["uncertainty_phrases"] = -0.07

    # 8) Penalty: short answer
    if answer_text and len(answer_text.strip()) < 80:
        conf -= 0.03
        components["penalties"]["short_answer"] = -0.03

    # 9) Clamp to [0, 1]
    conf = float(max(0.0, min(1.0, conf)))
    components["final"] = round(conf, 4)

    return conf, components


@dataclass
class Citation:
    """Citation for a piece of information"""

    doc_id: str
    source: str
    page: Optional[int] = None
    text_snippet: str = ""
    relevance_score: float = 0.0
    pdf_path: Optional[str] = None  # Full path to PDF file if available

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "doc_id": self.doc_id,
            "source": self.source,
            "page": self.page,
            "snippet": self.text_snippet[:100] + "..."
            if len(self.text_snippet) > 100
            else self.text_snippet,
            "score": round(self.relevance_score, 4),
        }
        # Include pdf_path if available
        if self.pdf_path:
            result["pdf_path"] = self.pdf_path
        return result


@dataclass
class GeneratedAnswer:
    """Generated answer with citations"""

    query: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": round(self.confidence, 2),
            "metadata": self.metadata,
            "generation_time_ms": round(self.generation_time_ms, 2),
        }


@dataclass
class GeneratorConfig:
    """Configuration for answer generation"""

    llm_tier: str = "standard"  # LLM tier to use
    # Max total context size in characters (approx). Increased to allow full-page scanning.
    max_context_length: int = 20000
    # Max answer length (tokens). Can be tuned per environment; default generous.
    max_answer_length: int = 2048
    temperature: float = 0.3  # Lower = more focused
    include_citations: bool = True
    citation_style: str = "inline"  # inline, footnote, or separate
    min_confidence: float = 0.5  # Minimum confidence to return answer
    language: str = "en"
    prompt_template: Optional[str] = None

    # Confidence computation mode
    confidence_mode: Literal[
        "legacy", "calibrated"
    ] = "legacy"  # Default to legacy for backward compatibility

    # Per-document/page limit to avoid a single page dominating context
    per_doc_max_chars: int = 6000

    # Fallback behavior
    allow_uncited_fallback: bool = (
        True  # Allow answering without citations if outside KB or LLM empty
    )
    general_answer_tier: str = (
        "light"  # Tier for generic answers when no context is available
    )

    # Advanced options
    use_chain_of_thought: bool = True  # Add reasoning steps
    verify_facts: bool = True  # Double-check facts against sources
    handle_contradictions: bool = True  # Handle conflicting information

    # Vision generation controls
    enable_vision_generation: bool = (
        True  # Enable multimodal answer generation if pages available
    )
    vision_model: str = "models/gemini-2.5-pro"  # Always use Gemini 2.5 Pro for vision
    vision_max_pages_total: int = 10  # Max total pages per question
    pdf_render_dpi: int = 200  # DPI for PDF rendering
    pdf_image_format: str = "jpeg"  # jpeg|png
    vision_timeout_sec: int = 20  # Not strictly enforced here; for future use
    vision_retry: int = 2  # For future use


class ResponseGenerator:
    """
    Generates answers from retrieved documents
    Handles citation tracking and answer formatting
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        """
        Initialize generator

        Args:
            config: Generator configuration
        """
        self.config = config or GeneratorConfig()
        # Apply ENV overrides for vision settings (optional)
        try:
            import os

            self.config.vision_model = os.getenv(
                "VISION_MODEL", self.config.vision_model
            )
            self.config.vision_max_pages_total = int(
                os.getenv("VISION_MAX_PAGES_TOTAL", self.config.vision_max_pages_total)
            )
            self.config.pdf_render_dpi = int(
                os.getenv("PDF_RENDER_DPI", self.config.pdf_render_dpi)
            )
            self.config.pdf_image_format = os.getenv(
                "PDF_IMAGE_FORMAT", self.config.pdf_image_format
            )
            self.config.vision_timeout_sec = int(
                os.getenv("VISION_TIMEOUT_SEC", self.config.vision_timeout_sec)
            )
            self.config.vision_retry = int(
                os.getenv("VISION_RETRY", self.config.vision_retry)
            )
        except Exception:
            pass
        self.llm_client = None
        self._init_llm()

        logger.info(f"RAG Generator initialized with tier: {self.config.llm_tier}")
        logger.info(f"Resolved vision model: {self.config.vision_model}")

    def _init_llm(self):
        """Initialize LLM client"""
        try:
            self.llm_client = get_llm_client(tier=self.config.llm_tier)
            logger.info("LLM client initialized for generation")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

    def generate(
        self,
        query: TransformedQuery,
        retrieved_docs: List[RetrievalResult],
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> GeneratedAnswer:
        """
        Generate answer from retrieved documents

        Args:
            query: Transformed query with intent
            retrieved_docs: Retrieved and ranked documents
            additional_context: Optional additional context

        Returns:
            Generated answer with citations
        """
        import time

        start_time = time.time()

        if not retrieved_docs:
            return self._generate_no_results_answer(query)

        try:
            # Prepare context from documents
            context, doc_mapping = self._prepare_context(retrieved_docs)

            # For bilingual support: use both original and normalized queries
            # normalized query is in English for matching with English docs
            # original query preserves the user's language for response
            is_translated = query.metadata and query.metadata.get("translated_from")
            generation_query = (
                query.normalized
            )  # Always use normalized for context matching
            original_query = query.original  # Keep original for language detection

            # Determine response language
            response_language = query.language if hasattr(query, "language") else "en"

            # Attempt multimodal (Vision) generation when enabled and pages available
            vision_answer = None
            vision_citations: List[Citation] = []
            metadata_extra = {}
            if self.config.enable_vision_generation:
                logger.info("Vision gating: ON (config enabled)")
                try:
                    vision_result = self._try_vision_generation(
                        english_query=generation_query,
                        original_query=original_query,
                        context=context,
                        doc_mapping=doc_mapping,
                        retrieved_docs=retrieved_docs,
                        language=response_language,
                    )
                    if vision_result:
                        vision_answer, vision_citations, vision_meta = vision_result
                        metadata_extra["vision_generation"] = vision_meta
                        # When Vision used, mark model
                        metadata_extra["model"] = "gemini-2.5-pro"
                        pages_used = vision_meta.get("pages_used", [])
                        pages_failed = vision_meta.get("pages_failed", [])
                        logger.info(
                            f"Vision pages: used={len(pages_used)}, failed={len(pages_failed)}, "
                            f"total_limit={self.config.vision_max_pages_total}, "
                            f"pages={[p.get('page') for p in pages_used]}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Vision gating: OFF (reason=exception: {str(e)[:100]})"
                    )
                    logger.warning(
                        f"Vision generation failed, falling back to text-only: {e}"
                    )
                    pass
            else:
                logger.info("Vision gating: OFF (reason=config_disabled)")

            # Generate answer based on intent; prefer Vision path if result exists
            if query.intent == QueryIntent.ASK:
                if vision_answer:
                    answer, citations = vision_answer, vision_citations
                else:
                    answer, citations = self._generate_ask_answer_bilingual(
                        generation_query,
                        original_query,
                        context,
                        doc_mapping,
                        response_language,
                    )
            elif query.intent == QueryIntent.EXPLAIN:
                if vision_answer:
                    answer, citations = vision_answer, vision_citations
                else:
                    # For simplicity, using same bilingual approach for EXPLAIN
                    answer, citations = self._generate_ask_answer_bilingual(
                        generation_query,
                        original_query,
                        context,
                        doc_mapping,
                        response_language,
                    )
            elif query.intent == QueryIntent.LOCATE:
                answer, citations = self._generate_locate_answer(
                    generation_query, retrieved_docs
                )
            elif query.intent == QueryIntent.REPORT:
                if vision_answer:
                    answer, citations = vision_answer, vision_citations
                else:
                    # For reports, also use bilingual approach
                    answer, citations = self._generate_ask_answer_bilingual(
                        generation_query,
                        original_query,
                        context,
                        doc_mapping,
                        response_language,
                    )
            else:
                # Default also uses bilingual; prefer vision if available
                if vision_answer:
                    answer, citations = vision_answer, vision_citations
                else:
                    answer, citations = self._generate_ask_answer_bilingual(
                        generation_query,
                        original_query,
                        context,
                        doc_mapping,
                        response_language,
                    )

            # If the LLM returned an empty/too short answer, or an apology/error, fall back to a general answer
            fallback_used = False
            apology_markers = [
                "i apologize",
                "i couldn't generate",
                "error generating response",
                "xin lỗi",
                "không thể",
            ]
            if (not answer or len(answer.strip()) < 10) or any(
                m in (answer or "").lower() for m in apology_markers
            ):
                try:
                    # Use original query for general answer to maintain language consistency
                    answer, citations = self._generate_general_answer(query.original)
                    fallback_used = True
                except Exception as _:
                    # Keep original empty answer; will be handled by post-processing
                    pass

            # Calculate confidence based on mode
            if self.config.confidence_mode == "calibrated":
                # Use new calibrated confidence with detailed components
                confidence, confidence_components = _compute_calibrated_confidence(
                    retrieval_results=retrieved_docs,
                    citations=citations,
                    answer_text=answer if answer else "",
                    context_items=retrieved_docs,
                    cfg=self.config,
                )
                # Store components for debugging/transparency
                if "metadata_extra" not in locals():
                    metadata_extra = {}
                metadata_extra["confidence_components"] = confidence_components

                logger.debug(
                    f"Calibrated confidence: {confidence:.3f} "
                    f"(base={confidence_components.get('base', 0):.3f}, "
                    f"boosts={sum(confidence_components.get('boosts', {}).values()):.3f}, "
                    f"penalties={sum(confidence_components.get('penalties', {}).values()):.3f})"
                )
            else:
                # Use legacy confidence calculation
                confidence = self._calculate_confidence(
                    answer if answer else "", citations, retrieved_docs
                )

            # Post-process answer
            final_answer = self._post_process_answer(answer, citations, confidence)

            generation_time = (time.time() - start_time) * 1000

            # Prepare metadata (may already have confidence_components from calibrated mode)
            if "metadata_extra" not in locals():
                metadata_extra = {}

            metadata_extra.update(
                {
                    "intent": query.intent.value,
                    "num_docs": len(retrieved_docs),
                    "has_filters": bool(query.filters),
                    "used_hyde": (len(query.hyde_queries) > 0)
                    if query.hyde_queries
                    else False,
                    "confidence_mode": self.config.confidence_mode,
                }
            )

            if "fallback_used" in locals() and fallback_used:
                metadata_extra["uncited_fallback"] = True

            return GeneratedAnswer(
                query=query.original,
                answer=final_answer,
                citations=citations,
                confidence=confidence,
                metadata=metadata_extra,
                generation_time_ms=generation_time,
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return self._generate_error_answer(query, str(e))

    def _prepare_context(
        self, docs: List[RetrievalResult]
    ) -> Tuple[str, Dict[int, RetrievalResult]]:
        """
        Prepare context from retrieved documents

        Returns:
            (context_string, doc_id_mapping)
        """
        context_parts = []
        doc_mapping = {}

        for i, doc in enumerate(docs):
            # Prefer full-page text if available; otherwise use chunk text
            text = doc.text or ""
            # Apply per-document cap to keep context balanced
            per_cap = max(500, getattr(self.config, "per_doc_max_chars", 6000))
            if len(text) > per_cap:
                text = text[:per_cap] + "..."

            # Add with clear separation and page info
            page_info = f" (Page {doc.page})" if doc.page else ""
            context_parts.append(f"[Doc {i+1}]{page_info} {text}")
            doc_mapping[i + 1] = doc

        # Join with clear separators
        context = "\n---\n".join(context_parts)

        # Truncate total context if too long
        if len(context) > self.config.max_context_length:
            context = context[: self.config.max_context_length] + "..."

        return context, doc_mapping

    def _call_llm_with_fallback(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call primary LLM, and if empty/apology/error, retry with light-tier model."""
        # First try with configured client
        response = self.llm_client.generate(
            prompt=prompt, temperature=temperature, max_tokens=max_tokens
        )
        content = (
            response.content if response and isinstance(response.content, str) else ""
        )
        content_l = (content or "").lower()
        # If not usable, try light-tier
        if (
            (not content.strip())
            or ("i apologize" in content_l)
            or ("error generating response" in content_l)
        ):
            try:
                fallback_client = get_llm_client(tier="light")
                resp2 = fallback_client.generate(
                    prompt=prompt,
                    temperature=max(0.2, temperature),
                    max_tokens=max_tokens,
                )
                if resp2 and isinstance(resp2.content, str) and resp2.content.strip():
                    return resp2.content.strip()
            except Exception:
                pass
        return (content or "").strip()

    def _generate_ask_answer_bilingual(
        self,
        english_query: str,
        original_query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        language: str = "en",
    ) -> Tuple[str, List[Citation]]:
        """Generate answer for ASK intent with bilingual support

        Args:
            english_query: Query in English (for matching with English documents)
            original_query: Query in original language (for determining response language)
            context: Document context (in English)
            doc_mapping: Mapping of doc numbers to results
            language: Target response language
        """

        # If Vietnamese, create bilingual prompt with strict citation rules
        if language == "vi":
            prompt = f"""Bạn là trợ lý kỹ thuật chính xác.

Câu hỏi gốc (Vietnamese): {original_query}
Bản dịch tiếng Anh: {english_query}

Ngữ cảnh từ tài liệu:
{context}

Hướng dẫn:
1. Bắt đầu bằng 1-2 câu trả lời trực tiếp cho câu hỏi
2. Trả lời bằng Tiếng Việt, giữ định dạng trích dẫn [Doc X, p.Y]
3. LUÔN thêm số trang khi trích dẫn giá trị/thông số cụ thể (ví dụ: [Doc 1, p.15])
4. Khi nêu số liệu, giữ nguyên giá trị và đơn vị như trong nguồn - không làm tròn trừ khi nguồn làm tròn
5. CHỈ sử dụng ngữ cảnh được cung cấp - không bịa đặt nội dung hoặc trích dẫn
6. Nếu ngữ cảnh không có câu trả lời, nêu rõ: "Không tìm thấy trong ngữ cảnh được cung cấp." và KHÔNG thêm trích dẫn
7. Giữ câu trả lời ngắn gọn và chính xác

Trả lời bằng Tiếng Việt:"""
        else:
            # English with strict citation rules
            prompt = f"""You are a precise technical assistant.

Question: {english_query}

Context:
{context}

Instructions:
1. Start with a direct answer in 1-2 sentences
2. ALWAYS include inline citations in the form [Doc X] or [Doc X, p.Y]
3. Include page numbers when citing specific values/specifications (e.g., [Doc 2, p.10])
4. When stating numbers, keep exact values and units as in the source - do not round unless the source rounds
5. ONLY use the provided context - do not fabricate citations or content
6. If the context does not contain the answer, explicitly say: "Not found in the provided context." and do NOT include any citation
7. Keep the answer concise and factual

Answer:"""

        # Call LLM with fallback to light-tier if needed
        answer = self._call_llm_with_fallback(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        # Extract citations
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_ask_answer(
        self,
        query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        language: str = "en",
    ) -> Tuple[str, List[Citation]]:
        """Generate answer for ASK intent"""

        # Add language instruction if Vietnamese is needed
        lang_instruction = ""
        if language == "vi":
            lang_instruction = "\n8. IMPORTANT: Respond in Vietnamese (Tiếng Việt) but keep citation markers [Doc X] or [Doc X, p.Y] as is"

        prompt = f"""Answer the following question based on the provided technical documents.

Question: {query}

Context:
{context}

Instructions:
1. IMPORTANT: Start with a direct 1-2 sentence answer to the question
2. Then provide supporting details from the documents
3. Cite sources using [Doc X] or [Doc X, p.Y] format inline with your statements
4. Include page numbers when citing specific values or specifications
5. If the context doesn't contain the answer, say so clearly
6. DO NOT just list citations without answering the question
7. Use information from the context to provide specific technical details{lang_instruction}

Answer:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        answer = (
            response.content
            if response
            and isinstance(response.content, str)
            and response.content.strip()
            else ""
        )

        # Extract citations
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_explain_answer(
        self, query: str, context: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate explanation for EXPLAIN intent"""

        prompt = f"""Explain the following technical concept based on the provided documents.

Topic: {query}

Context:
{context}

Instructions:
1. Begin with a brief 1-2 sentence definition or conclusion
2. Explain key principles and mechanisms with supporting details
3. Use [Doc X, p.Y] citations inline for each specific value/claim
4. When citing technical values, include exact numbers and units from the source
5. If a claim aggregates multiple sources, include multiple citations
6. If the context doesn't support the explanation, state this explicitly and avoid citations
7. Keep technical terms precise

Explanation:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        answer = response.content if response and response.content else ""
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_locate_answer(
        self, query: str, docs: List[RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate answer for LOCATE intent (finding equipment/documents)"""

        # Extract equipment tags or document references
        found_items = []
        citations = []

        for doc in docs[:5]:  # Check top 5 docs
            # Look for equipment tags (e.g., KT06101)
            tags = re.findall(r"\b[A-Z]{1,}[-]?\d{2,}[A-Z]?\b", doc.text.upper())
            if tags:
                for tag in tags:
                    found_items.append(
                        {
                            "tag": tag,
                            "source": doc.source,
                            "doc_id": doc.doc_id,
                            "context": doc.text[:200],
                        }
                    )

                    citations.append(
                        Citation(
                            doc_id=doc.doc_id,
                            source=doc.source,
                            page=doc.page,
                            text_snippet=doc.text[:100],
                            relevance_score=doc.score,
                        )
                    )

        if found_items:
            answer = f"Found the following related items:\n"
            for item in found_items[:3]:
                answer += f"\n• {item['tag']} - Located in {item['source']}"
        else:
            answer = f"Could not locate specific equipment or documents matching '{query}'. Please check the reference format."

        return answer, citations

    def _generate_report_answer(
        self, query: str, context: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate report/summary for REPORT intent"""

        prompt = f"""Generate a comprehensive report on the following topic based on the technical documents.

Topic: {query}

Context:
{context}

Instructions:
1. Start with a brief 1-2 sentence summary of key findings
2. Organize information into clear sections
3. Use [Doc X, p.Y] citations inline for each specific value/claim
4. Include exact specifications and parameters with units as in the source
5. When aggregating multiple sources, cite all relevant documents
6. Highlight critical values or requirements
7. If context lacks information for any section, state this explicitly without fabricating

Report:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length * 2,  # Allow longer reports
        )

        answer = response.content if response and response.content else ""
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_default_answer(
        self, query: str, context: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> Tuple[str, List[Citation]]:
        """Generate default answer when intent is unclear"""

        prompt = f"""Provide relevant information for the following query based on the technical documents.

Query: {query}

Context:
{context}

Instructions:
1. Identify the most relevant information
2. Provide a helpful response
3. Cite sources using [Doc X] or [Doc X, p.Y] format with page numbers

Response:"""

        response = self.llm_client.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        answer = response.content if response and response.content else ""
        citations = self._extract_citations(answer, doc_mapping)

        return answer, citations

    def _generate_general_answer(self, query: str) -> Tuple[str, List[Citation]]:
        """Generate a general answer without requiring citations.
        Used when there is no relevant context or the LLM returned empty content.
        """
        try:
            client = get_llm_client(tier=self.config.general_answer_tier)
            system_prompt = (
                "You are a knowledgeable technical assistant. Answer concisely and helpfully based on general "
                "domain knowledge when no specific document context is provided. Do not fabricate citations."
            )
            prompt = (
                f"Provide a concise overview answering the following query. "
                f"Use bullet points where appropriate.\n\nQuery: {query}\n\nAnswer:"
            )
            response = client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=max(0.2, self.config.temperature),
                max_tokens=max(300, self.config.max_answer_length),
            )

            # Extract answer from response
            if response and hasattr(response, "content") and response.content:
                generic_answer = response.content.strip()
            else:
                generic_answer = ""

            # If still empty, provide a fallback message
            if not generic_answer or len(generic_answer) < 10:
                logger.warning(
                    f"General answer generation failed or returned empty for query: {query[:100]}"
                )
                generic_answer = (
                    f"I understand you're asking about '{query[:100]}...'. "
                    f"Unfortunately, I couldn't generate a complete answer at this moment. "
                    f"Please try rephrasing your question or providing more context."
                )

            return generic_answer, []

        except Exception as e:
            logger.error(f"Failed to generate general answer: {e}")
            # Return a helpful fallback message
            return (
                f"I'm having trouble processing your question about '{query[:100]}...'. "
                f"Please try again or rephrase your question for better results."
            ), []

    def _extract_citations(
        self, answer: str, doc_mapping: Dict[int, RetrievalResult]
    ) -> List[Citation]:
        """Extract citations from answer text with enhanced page number support

        Supports multiple citation formats:
        - [Doc X] - basic format
        - [Doc X, p.Y] - with page number
        - [Doc X, page Y] - with page word
        - [Doc X, pp. Y-Z] - page range
        - [X] - footnote style
        """
        citations = []

        # Enhanced patterns for different citation formats
        patterns = [
            # [Doc X, p.Y] or [Doc X, page Y] or [Doc X, pp. Y-Z]
            r"\[Doc\s*(\d+)(?:,\s*(?:p\.?|page|pp\.)\s*(\d+)(?:[\-–](\d+))?)?\]",
            # Simple [X] format (footnote style)
            r"\[(\d+)\](?!\w)",  # Negative lookahead to avoid matching [1]st etc.
        ]

        seen_citations = set()

        for pattern in patterns:
            for match in re.finditer(pattern, answer, re.IGNORECASE):
                # Extract doc number and optional page info
                groups = match.groups()
                doc_num = int(groups[0])

                # Extract page number if present in citation
                page_num = None
                if len(groups) > 1 and groups[1]:
                    try:
                        page_num = int(groups[1])
                    except (ValueError, TypeError):
                        page_num = None

                # Create unique key for deduplication
                citation_key = (doc_num, page_num)

                if doc_num in doc_mapping and citation_key not in seen_citations:
                    doc = doc_mapping[doc_num]

                    # Use page from citation if available, otherwise from document metadata
                    final_page = page_num if page_num else doc.page

                    # Ensure page is valid (not None, not 0)
                    if final_page is None or final_page == 0:
                        final_page = doc.metadata.get("page", 1) if doc.metadata else 1

                    citation = Citation(
                        doc_id=doc.doc_id,
                        source=doc.source,
                        page=final_page,
                        text_snippet=doc.text[:200],
                        relevance_score=doc.score,
                    )

                    # Enrich with pdf_path from doc_id_map if available (lazy load)
                    try:
                        doc_id_map = _get_doc_id_map()
                        if doc.doc_id in doc_id_map:
                            citation.pdf_path = doc_id_map[doc.doc_id]
                    except Exception:
                        pass

                    citations.append(citation)
                    seen_citations.add(citation_key)

        # If no citations found but doc_mapping exists, use top docs as implicit citations
        if not citations and doc_mapping and self.config.include_citations:
            for doc_num in sorted(doc_mapping.keys())[:3]:  # Use top 3 docs
                doc = doc_mapping[doc_num]
                page = doc.page if doc.page else 1
                citation = Citation(
                    doc_id=doc.doc_id,
                    source=doc.source,
                    page=page,
                    text_snippet=doc.text[:200],
                    relevance_score=doc.score,
                )

                # Enrich with pdf_path from doc_id_map if available (lazy load)
                try:
                    doc_id_map = _get_doc_id_map()
                    if doc.doc_id in doc_id_map:
                        citation.pdf_path = doc_id_map[doc.doc_id]
                except Exception:
                    pass

                citations.append(citation)

        return citations

    def _try_vision_generation(
        self,
        english_query: str,
        original_query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        retrieved_docs: List[RetrievalResult],
        language: str,
    ) -> Optional[Tuple[str, List[Citation], Dict[str, Any]]]:
        """
        Attempt multimodal generation with Gemini 2.5 Pro using page images if available.
        Returns (answer, citations, vision_meta) or None if vision cannot run.
        """
        # 1) Build list of (pdf_path, page) to render
        try:
            pages_plan, pages_meta = self._build_vision_pages(retrieved_docs)
        except Exception as e:
            logger.warning(f"Failed to build vision pages: {e}")
            return None

        if not pages_plan:
            # No valid pages to render -> skip vision
            reason = (
                pages_meta.get("reason") if isinstance(pages_meta, dict) else "no_pages"
            )
            logger.info(f"Vision gating: OFF (reason={reason})")
            return None

        # 2) Render pages to images
        images: List[bytes] = []
        pages_used: List[Dict[str, Any]] = []
        pages_failed: List[Dict[str, Any]] = []
        try:
            from tools.pdf_renderer import get_pdf_page_count, render_page_to_image
        except Exception as e:
            logger.warning(f"PDF renderer not available: {e}")
            return None

        for item in pages_plan:
            pdf_path = item["pdf_path"]
            page = int(item["page"])  # 1-based
            try:
                img_bytes, meta = render_page_to_image(
                    pdf_path,
                    page,
                    self.config.pdf_render_dpi,
                    self.config.pdf_image_format,
                    True,
                )
                images.append(img_bytes)
                pages_used.append({"pdf_path": pdf_path, "page": page})
            except Exception as e:
                pages_failed.append(
                    {"pdf_path": pdf_path, "page": page, "reason": str(e)[:200]}
                )
                logger.debug(f"Render failed for {pdf_path} p.{page}: {e}")

        if not images:
            # Rendering failed for all pages
            logger.info("Vision gating: OFF (all page renders failed)")
            return None

        # 3) Call Gemini 2.5 Pro multimodal
        try:
            # Import google-genai only if needed
            from google import genai
            from google.genai import types

            from app.services.llm import get_api_key_for
        except Exception as e:
            logger.warning(f"Gemini client not available: {e}")
            return None

        # Validate doc_mapping before proceeding
        if not doc_mapping:
            logger.warning("Vision generation: doc_mapping is empty")
            return None

        # Validate images contain actual data
        if not all(isinstance(img, bytes) and len(img) > 0 for img in images):
            logger.warning("Vision generation: some images are invalid or empty")
            return None

        # Build prompt with bilingual and strict citation rules, and include mapping info
        # Provide mapping from [Doc N] -> doc_id and list attached pages for citation accuracy
        mapping_lines = []
        for i, doc in doc_mapping.items():
            try:
                mapping_lines.append(f"Doc {i} -> {doc.doc_id}")
            except Exception:
                mapping_lines.append(f"Doc {i} -> unknown")
        attached_lines = [
            f"(Doc {i}, p.{d.page if d and d.page else 'unknown'})"
            for i, d in doc_mapping.items()
        ]

        if language == "vi":
            instruction = (
                "Bạn là trợ lý kỹ thuật chính xác. Trả lời bằng Tiếng Việt."
                " Hãy sử dụng cả ngữ cảnh văn bản và ảnh trang đính kèm để lập luận. "
                "Luôn trích dẫn inline theo dạng [Doc X] hoặc [Doc X, p.Y]; khi nêu thông số cụ thể phải có số trang."
                ' Giữ nguyên giá trị và đơn vị theo nguồn. Nếu ngữ cảnh/ảnh không chứa câu trả lời, trả lời: "Không tìm thấy trong ngữ cảnh được cung cấp." và KHÔNG chèn trích dẫn.'
            )
            mapping_text = "Bản đồ Doc: " + ", ".join(
                mapping_lines
            ) + "\n" "Trang đính kèm (theo Doc/page): " + ", ".join(attached_lines)
            prompt_text = (
                f"Câu hỏi gốc: {original_query}\n"
                f"Bản dịch tiếng Anh (nếu có): {english_query}\n\n"
                f"Ngữ cảnh từ tài liệu:\n{context}\n\n"
                f"{mapping_text}\n\n"
                "Trả lời:"
            )
        else:
            instruction = (
                "You are a precise technical assistant. Answer in the user's language. "
                "Use BOTH the provided text context and the attached page images for reasoning. "
                "ALWAYS include inline citations [Doc X] or [Doc X, p.Y]; include page numbers when citing specific values. "
                'Keep exact values and units from the source. If the answer is not in the provided context/images, say: "Not found in the provided context." with no citations.'
            )
            mapping_text = "Doc mapping: " + ", ".join(
                mapping_lines
            ) + "\n" "Attached pages (Doc/page): " + ", ".join(attached_lines)
            prompt_text = (
                f"Question: {english_query}\n\n"
                f"Context:\n{context}\n\n"
                f"{mapping_text}\n\n"
                "Answer:"
            )

        # Assemble contents
        parts = [types.Part.from_text(prompt_text)]
        for img in images:
            mime = (
                "image/png"
                if str(self.config.pdf_image_format).lower() == "png"
                else "image/jpeg"
            )
            parts.append(types.Part.from_bytes(mime_type=mime, data=img))

        contents = [types.Content(role="user", parts=parts)]

        # Build config
        cfg_params = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_answer_length,
            "system_instruction": instruction,
        }
        cfg = types.GenerateContentConfig(**cfg_params)

        # Create client and call
        try:
            api_key = get_api_key_for("gemini")
        except Exception as e:
            logger.warning(f"Gemini API key missing: {e}")
            return None

        client = genai.Client(api_key=api_key)
        model_name = (
            self.config.vision_model
            if self.config.vision_model.startswith("models/")
            else f"models/{self.config.vision_model}"
        )

        try:
            resp = client.models.generate_content(
                model=model_name, contents=contents, config=cfg
            )
            answer_text = resp.text if hasattr(resp, "text") else ""
        except Exception as e:
            logger.error(f"Gemini multimodal generation failed: {e}")
            return None

        # Extract citations from answer
        citations = self._extract_citations(answer_text, doc_mapping)

        vision_meta = {
            "pages_used": pages_used,
            "pages_failed": pages_failed,
            "excerpts": [],  # Optional: can parse excerpts from answer in future
        }

        # Log vision pages summary
        try:
            used_pages = [p.get("page") for p in pages_used]
            logger.info(
                f"Vision pages: used={len(pages_used)}, failed={len(pages_failed)}, total_limit={self.config.vision_max_pages_total}; pages={used_pages}"
            )
        except Exception:
            pass

        return answer_text, citations, vision_meta

    def _build_vision_pages(
        self, retrieved_docs: List[RetrievalResult]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Build a plan of pages to render for vision based on retrieved documents.
        Returns (pages_plan, meta), where pages_plan is a list of {pdf_path, page}.
        """
        max_pages = max(1, int(self.config.vision_max_pages_total))
        doc_id_map = _get_doc_id_map()
        if not retrieved_docs or not doc_id_map:
            return [], {"reason": "no_docs_or_mapping"}

        from pathlib import Path

        from app.utils.page_utils import extract_page_number

        pages: List[Dict[str, Any]] = []
        seen = set()

        # Helper to add a page if not duplicate and under limit
        def add_page(pdf_path: str, page: int):
            key = (pdf_path, page)
            if key in seen:
                return
            if len(pages) >= max_pages:
                return
            pages.append({"pdf_path": pdf_path, "page": page})
            seen.add(key)

        # Iterate over top retrieved docs, preserving rank order
        for doc in retrieved_docs:
            if len(pages) >= max_pages:
                break
            doc_id = doc.doc_id or (
                doc.metadata.get("doc_id") if doc.metadata else None
            )
            if not doc_id or doc_id not in doc_id_map:
                continue
            pdf_path = doc_id_map[doc_id]
            # Determine page range
            meta = doc.metadata or {}
            start = None
            end = None
            try:
                # Check if we have explicit page range (both must be present and not None)
                if (
                    "page_start" in meta
                    and meta.get("page_start") is not None
                    and "page_end" in meta
                    and meta.get("page_end") is not None
                ):
                    start = int(meta["page_start"])
                    end = int(meta["page_end"])
                    # Ensure start <= end
                    if start > end:
                        start, end = end, start
                else:
                    # Use center page with ±2 window
                    center = doc.page if doc.page else extract_page_number(meta)
                    center = int(center) if center else 1
                    start = max(1, center - 2)
                    end = center + 2  # No need for max(start, ...) since center >= 1
            except Exception as e:
                # Fallback to single page from doc.page
                logger.debug(f"Page range extraction failed for doc {doc_id}: {e}")
                center = doc.page if doc.page else 1
                start, end = int(center), int(center)

            # Optional: clamp using page count if accessible
            try:
                from tools.pdf_renderer import get_pdf_page_count

                total_pages = int(get_pdf_page_count(pdf_path))
                start = max(1, min(start, total_pages))
                end = max(1, min(end, total_pages))
                if end < start:
                    start, end = start, start
            except Exception:
                pass

            # Add pages in range
            for p in range(start, end + 1):
                if len(pages) >= max_pages:
                    break
                add_page(pdf_path, p)

        return pages, {"selected": len(pages), "max": max_pages}

    def _calculate_confidence(
        self, answer: str, citations: List[Citation], docs: List[RetrievalResult]
    ) -> float:
        """Calculate confidence score for the answer"""

        # Base confidence from document scores
        if docs:
            avg_score = sum(d.score for d in docs[:3]) / min(3, len(docs))
            base_confidence = min(avg_score * 2, 1.0)  # Scale up
        else:
            base_confidence = 0.0

        # Adjust based on citations
        if citations:
            citation_boost = min(len(citations) * 0.1, 0.3)
            base_confidence = min(base_confidence + citation_boost, 1.0)

        # Penalize if answer is too short or generic
        if len(answer) < 50:
            base_confidence *= 0.7

        # Check for uncertainty markers
        uncertainty_phrases = ["not sure", "unclear", "might be", "possibly", "unknown"]
        if any(phrase in answer.lower() for phrase in uncertainty_phrases):
            base_confidence *= 0.8

        return base_confidence

    def _post_process_answer(
        self, answer: str, citations: List[Citation], confidence: float
    ) -> str:
        """Post-process answer for final formatting"""

        # Clean up answer
        answer = (answer or "").strip()

        # Add confidence indicator if low (ASCII only)
        if confidence < self.config.min_confidence and answer:
            answer = f"[LOW CONFIDENCE]\n{answer}"

        # Format citations based on style
        if self.config.citation_style == "footnote" and citations:
            # Convert inline [Doc X] to footnotes
            for i, citation in enumerate(citations, 1):
                answer = answer.replace(f"[Doc {i}]", f"[{i}]")

            # Add footnotes
            answer += "\n\nSources:"
            for i, citation in enumerate(citations, 1):
                answer += f"\n[{i}] {citation.source}"
                if citation.page:
                    answer += f" (Page {citation.page})"

        return answer

    def _generate_no_results_answer(self, query: TransformedQuery) -> GeneratedAnswer:
        """Generate answer when no documents are retrieved.
        If allowed, fall back to a general answer without citations.
        """
        if self.config.allow_uncited_fallback:
            # Try to produce a general answer using model knowledge
            try:
                generic_answer, _ = self._generate_general_answer(query.original)
            except Exception:
                generic_answer = ""
            if generic_answer:
                return GeneratedAnswer(
                    query=query.original,
                    answer=generic_answer,
                    citations=[],
                    confidence=0.5,
                    metadata={"no_results": True, "uncited_fallback": True},
                )
        # Conservative fallback message if disabled or failed
        answer = f"No specific information found about '{query.original}' in the current documents."
        return GeneratedAnswer(
            query=query.original,
            answer=answer,
            citations=[],
            confidence=0.0,
            metadata={"no_results": True},
        )

    def _generate_error_answer(
        self, query: TransformedQuery, error: str
    ) -> GeneratedAnswer:
        """Generate answer when an error occurs"""

        answer = (
            "I encountered an error while processing your request. "
            "Please try rephrasing your question or contact support if the issue persists."
        )

        logger.error(f"Generation error for query '{query.original}': {error}")

        return GeneratedAnswer(
            query=query.original,
            answer=answer,
            citations=[],
            confidence=0.0,
            metadata={"error": True, "error_message": error},
        )

    def generate_streaming(
        self, query: TransformedQuery, retrieved_docs: List[RetrievalResult]
    ) -> Any:
        """
        Generate answer with streaming (for future implementation)
        Yields chunks of the answer as they're generated
        """
        # TODO: Implement streaming generation for real-time responses
        pass


def create_generator(config: Optional[GeneratorConfig] = None) -> ResponseGenerator:
    """
    Factory function to create generator

    Args:
        config: Optional configuration

    Returns:
        Configured RAGGenerator instance
    """
    return ResponseGenerator(config or GeneratorConfig())


# Backward compatibility alias expected by some tests
RAGGenerator = ResponseGenerator


# Convenience function
def generate_answer(
    query: TransformedQuery, retrieved_docs: List[RetrievalResult], **kwargs
) -> GeneratedAnswer:
    """
    Quick function to generate answer

    Args:
        query: Transformed query
        retrieved_docs: Retrieved documents
        **kwargs: Additional config parameters

    Returns:
        Generated answer with citations
    """
    config = GeneratorConfig(**kwargs)
    generator = create_generator(config)
    return generator.generate(query, retrieved_docs)
