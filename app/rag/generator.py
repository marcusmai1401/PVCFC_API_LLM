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


# -------- Debug helpers for safe, concise logging --------


def _safe_truncate(text: Optional[str], limit: int = 1200) -> str:
    """Return a safely truncated preview string for logs."""
    try:
        if not text:
            return ""
        t = str(text)
        return t[:limit] + ("..." if len(t) > limit else "")
    except Exception:
        return ""


def _summarize_doc_mapping(doc_mapping: Dict[int, "RetrievalResult"]) -> List[str]:
    """Produce one-line summaries per [Doc N] for logging."""
    lines: List[str] = []
    for num, r in (doc_mapping or {}).items():
        meta = r.metadata or {}
        pdf_path = meta.get("pdf_path")
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        rng = f", range={page_start}-{page_end}" if page_start and page_end else ""
        score = getattr(r, "score", None)
        score_txt = f"{float(score):.4f}" if isinstance(score, (int, float)) else "n/a"
        lines.append(
            f"Doc {num}: doc_id={r.doc_id or 'unknown'}, source={r.source}, page={r.page or '?'}, "
            f"score={score_txt}, pdf_path={'yes' if pdf_path else 'no'}{rng}"
        )
    return lines


def _format_citations_for_log(citations: List["Citation"]) -> List[str]:
    """Human-friendly citation lines for logs."""
    out: List[str] = []
    for i, c in enumerate(citations or [], 1):
        out.append(
            f"[{i}] doc_id={c.doc_id}, page={c.page}, pdf_path={'yes' if c.pdf_path else 'no'}, source={c.source}"
        )
    return out


def _get_doc_id_map() -> Dict[str, str]:
    global _DOC_ID_MAP_CACHE
    if _DOC_ID_MAP_CACHE is not None:
        return _DOC_ID_MAP_CACHE
    try:
        import json
        from pathlib import Path

        # Try production path first (priority)
        production_path = Path("artifacts/ingestion_production/doc_id_map.json")
        legacy_path = Path("artifacts/ingestion/doc_id_map.json")

        if production_path.exists():
            with open(production_path, "r", encoding="utf-8") as f:
                _DOC_ID_MAP_CACHE = json.load(f)
            logger.info(
                f"Loaded doc_id_map from production: {len(_DOC_ID_MAP_CACHE)} entries"
            )
        elif legacy_path.exists():
            with open(legacy_path, "r", encoding="utf-8") as f:
                _DOC_ID_MAP_CACHE = json.load(f)
            logger.info(
                f"Loaded doc_id_map from legacy path: {len(_DOC_ID_MAP_CACHE)} entries"
            )
        else:
            _DOC_ID_MAP_CACHE = {}
            logger.warning("No doc_id_map.json found in production or legacy paths")
    except Exception as e:
        logger.error(f"Failed to load doc_id_map: {e}")
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
    # HIGH-SCORE BYPASS: If all top scores are already high (≥0.80), skip rescaling
    # This prevents artificially low confidence for high-quality retrievals
    if raw_scores and min(raw_scores) >= 0.80:
        base_conf = float(mean(raw_scores))
        components = {
            "raw_top_scores": raw_scores,
            "base": round(base_conf, 4),
            "boosts": {},
            "penalties": {},
            "note": "High-quality retrieval, no rescaling applied",
        }
        logger.debug(
            f"High scores detected (min={min(raw_scores):.3f}), "
            f"using raw average: {base_conf:.3f}"
        )
    else:
        # Standard rescaling for lower/mixed scores
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
    bbox: Optional[
        List[float]
    ] = None  # Bounding box [x0, y0, x1, y1] in normalized coordinates
    metadata: Optional[
        Dict[str, Any]
    ] = None  # Additional metadata (tags, equipment_type, etc.)

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
        # Include bbox if available
        if self.bbox is not None:
            result["bbox"] = self.bbox
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

    # Structured output controls (Phase 0 - Citation Accuracy)
    enable_structured_output: bool = False  # Use JSON mode with schema enforcement
    enable_claims_extraction: bool = False  # Extract per-claim citations

    # Citation validation controls (Phase 1 - CiteFix-lite)
    enable_citation_validation: bool = (
        True  # Post-validate citations with CitationValidator
    )
    citation_validation_level: int = 2  # 1=basic, 2=text verification
    citation_min_confidence: float = 0.7  # Minimum confidence for valid citation
    citation_neighbor_scan: int = 2  # ±N pages to scan for low-confidence citations

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

    # Smart vision strategy (Phase 2 - Day 11)
    enable_smart_vision_strategy: bool = (
        True  # Use strategy to decide when/how to run vision
    )
    vision_skip_text_only: bool = True  # Skip vision when likely text-only evidence
    vision_table_figure_keywords: Tuple[str, ...] = (
        "table",
        "figure",
        "fig.",
        "fig ",
        "diagram",
        "chart",
        "graph",
        "image",
        "picture",
        "photo",
        "hình",
        "bảng",
        "biểu đồ",
        "sơ đồ",
    )
    vision_text_only_negative_keywords: Tuple[str, ...] = (
        # If these are absent and table/figure keywords absent, likely text-only
        # This is used as supporting heuristic
        "table",
        "figure",
        "fig.",
        "diagram",
        "chart",
        "graph",
        "image",
        "hình",
        "bảng",
        "biểu đồ",
        "sơ đồ",
    )


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

    def _is_bbox_detection_enabled(self) -> bool:
        """Check if bbox detection is enabled via feature flag (Day 13)"""
        try:
            import os

            from app.core.config import settings

            # Check env var first (highest priority)
            env_flag = os.getenv("ENABLE_BBOX_DETECTION", "").lower()
            if env_flag in ("true", "1", "yes"):
                return True
            elif env_flag in ("false", "0", "no"):
                return False

            # Fall back to settings
            return getattr(settings, "enable_bbox_detection", True)
        except Exception as e:
            logger.debug(f"Error checking bbox detection flag: {e}")
            return True  # Default to enabled

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
                    # Extract query classification from metadata for vision reordering
                    query_classification = (
                        query.metadata.get("query_classification")
                        if query.metadata
                        else None
                    )
                    vision_result = self._try_vision_generation(
                        english_query=generation_query,
                        original_query=original_query,
                        context=context,
                        doc_mapping=doc_mapping,
                        retrieved_docs=retrieved_docs,
                        language=response_language,
                        query_classification=query_classification,
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

            # Try structured output generation if enabled and vision didn't succeed
            structured_answer = None
            structured_citations: List[Citation] = []
            if self.config.enable_structured_output and not vision_answer:
                logger.info("Structured output: Attempting JSON mode generation")
                try:
                    structured_result = self._generate_structured(
                        english_query=generation_query,
                        original_query=original_query,
                        context=context,
                        doc_mapping=doc_mapping,
                        language=response_language,
                    )
                    if structured_result:
                        structured_answer, structured_citations = structured_result
                        metadata_extra["structured_output"] = True
                        logger.info(
                            f"Structured output: SUCCESS ({len(structured_citations)} citations)"
                        )
                except Exception as e:
                    logger.warning(
                        f"Structured output failed, falling back to regex: {e}"
                    )

            # Generate answer based on intent; prefer Vision > Structured > Legacy
            if query.intent == QueryIntent.ASK:
                if vision_answer:
                    answer, citations = vision_answer, vision_citations
                elif structured_answer:
                    answer, citations = structured_answer, structured_citations
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
                elif structured_answer:
                    answer, citations = structured_answer, structured_citations
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
                elif structured_answer:
                    answer, citations = structured_answer, structured_citations
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
                # Default also uses bilingual; prefer vision > structured
                if vision_answer:
                    answer, citations = vision_answer, vision_citations
                elif structured_answer:
                    answer, citations = structured_answer, structured_citations
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

            # Post-validate citations with CiteFix-lite (Phase 1)
            if citations and self.config.enable_citation_validation:
                logger.info(f"Post-validating {len(citations)} citations")
                try:
                    citations, validation_results = self._post_validate_citations(
                        citations=citations,
                        query=query.normalized,
                        retrieved_docs=retrieved_docs,
                    )

                    # Store validation metadata
                    if "metadata_extra" not in locals():
                        metadata_extra = {}
                    metadata_extra["citation_validation"] = validation_results

                    logger.info(
                        f"Validation: {validation_results['valid_count']}/{validation_results['total_count']} valid, "
                        f"avg_confidence={validation_results['avg_confidence']:.3f}"
                    )
                except Exception as e:
                    logger.warning(f"Citation validation failed: {e}")

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

            # Be robust if intent may be a string
            intent_val = getattr(query.intent, "value", query.intent)
            metadata_extra.update(
                {
                    "intent": intent_val,
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

            # Build doc_number_map for IEEE-style citations (Frontend will use this)
            # Prefer vision mapping if available; otherwise fallback to text doc_mapping
            if (
                isinstance(metadata_extra, dict)
                and metadata_extra.get("vision_generation")
                and isinstance(metadata_extra.get("vision_generation"), dict)
                and metadata_extra["vision_generation"].get("doc_number_map")
            ):
                doc_number_map = metadata_extra["vision_generation"]["doc_number_map"]
            else:
                doc_number_map = self._build_doc_number_map(doc_mapping)
            metadata_extra["doc_number_map"] = doc_number_map

            # Debug log the doc_number_map for frontend citation rendering
            try:
                if isinstance(doc_number_map, dict) and doc_number_map:
                    lines = []
                    for k in sorted(doc_number_map.keys()):
                        v = doc_number_map[k]
                        lines.append(
                            f"Doc {k}: doc_id={v.get('doc_id')}, file={v.get('file_name')}, pdf_path={'present' if v.get('pdf_path') else 'missing'}"
                        )
                    logger.debug("doc_number_map built:\n" + "\n".join(lines[:50]))
            except Exception as e:
                logger.debug(f"Logging doc_number_map failed: {e}")

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

        # Log context and mapping for diagnostics
        try:
            logger.info(
                f"Prepared LLM context: docs={len(docs)}, combined_len={len(context)}, max_context_length={self.config.max_context_length}"
            )
            mapping_lines = _summarize_doc_mapping(doc_mapping)
            if mapping_lines:
                logger.debug("Doc mapping summary:\n" + "\n".join(mapping_lines[:20]))
            logger.debug("Context preview:\n" + _safe_truncate(context, 1500))
        except Exception as e:
            logger.debug(f"Logging _prepare_context failed: {e}")

        return context, doc_mapping

    def _build_doc_number_map(
        self, doc_mapping: Dict[int, RetrievalResult]
    ) -> Dict[int, Dict[str, str]]:
        """Build doc_number_map for IEEE-style citations in frontend.

        Args:
            doc_mapping: Mapping of doc numbers (1-indexed) to RetrievalResult objects

        Returns:
            Dict mapping doc_number -> {doc_id, pdf_path, file_name}
        """
        from pathlib import Path

        doc_number_map = {}
        doc_id_map = _get_doc_id_map()

        for doc_num, result in doc_mapping.items():
            doc_id = result.doc_id or (
                result.metadata.get("doc_id") if result.metadata else None
            )

            # Try to get pdf_path from result metadata first
            pdf_path = None
            if result.metadata and "pdf_path" in result.metadata:
                pdf_path = str(result.metadata["pdf_path"])
            # Otherwise lookup via doc_id_map
            elif doc_id and doc_id in doc_id_map:
                doc_info = doc_id_map[doc_id]
                if isinstance(doc_info, dict):
                    pdf_path = doc_info.get("pdf_path")
                elif isinstance(doc_info, str):
                    pdf_path = doc_info

            # Extract file_name from pdf_path
            file_name = "Unknown"
            if pdf_path:
                try:
                    file_name = Path(pdf_path).name
                except Exception:
                    file_name = "Unknown"

            doc_number_map[doc_num] = {
                "doc_id": doc_id or "unknown",
                "pdf_path": pdf_path or "",
                "file_name": file_name,
            }

        return doc_number_map

    def _call_llm_with_fallback(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call primary LLM, and if empty/apology/error, retry with light-tier model."""
        # First try with configured client
        try:
            logger.debug(
                f"Calling LLM (tier={self.config.llm_tier}) temp={temperature} max_tokens={max_tokens} prompt_len={len(prompt)}"
            )
            logger.debug("Prompt preview:\n" + _safe_truncate(prompt, 1500))
        except Exception:
            pass
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
                logger.info(
                    "Primary LLM response unusable; attempting fallback tier=light"
                )
            except Exception:
                pass
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
        final = (content or "").strip()
        try:
            logger.debug(f"LLM returned answer_len={len(final)}")
            logger.debug("Answer preview:\n" + _safe_truncate(final, 1500))
        except Exception:
            pass
        return final

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

        # Log prompt before calling LLM
        try:
            logger.info(
                f"Prepared ASK(bilingual) prompt: language={language}, temp={self.config.temperature}, max_tokens={self.config.max_answer_length}"
            )
            # Log doc mapping summary used for this prompt
            mapping_lines = _summarize_doc_mapping(doc_mapping)
            if mapping_lines:
                logger.debug(
                    "Doc mapping summary (ASK bilingual):\n"
                    + "\n".join(mapping_lines[:20])
                )
            # Log context preview specifically
            logger.debug(
                "Context preview (ASK bilingual):\n" + _safe_truncate(context, 1500)
            )
        except Exception:
            pass

        # Call LLM with fallback to light-tier if needed
        answer = self._call_llm_with_fallback(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_answer_length,
        )

        # Extract citations
        citations = self._extract_citations(answer, doc_mapping)

        # Log answer and parsed citations
        try:
            logger.info(
                f"ASK(bilingual) generation complete: answer_len={len(answer)}, citations={len(citations)}"
            )
            cit_lines = _format_citations_for_log(citations)
            if cit_lines:
                logger.debug(
                    "Parsed citations (ASK bilingual):\n" + "\n".join(cit_lines[:20])
                )
        except Exception:
            pass

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

                    # Extract metadata for citation (tags, equipment_type, doc_type)
                    citation_metadata = None
                    if doc.metadata:
                        citation_metadata = {}
                        if "tags" in doc.metadata:
                            citation_metadata["tags"] = doc.metadata["tags"]
                        if "equipment_type" in doc.metadata:
                            citation_metadata["equipment_type"] = doc.metadata[
                                "equipment_type"
                            ]
                        if "doc_type" in doc.metadata:
                            citation_metadata["doc_type"] = doc.metadata["doc_type"]
                        if not citation_metadata:
                            citation_metadata = None

                    citation = Citation(
                        doc_id=doc.doc_id,
                        source=doc.source,
                        page=final_page,
                        text_snippet=doc.text[:200],
                        relevance_score=doc.score,
                        metadata=citation_metadata,
                    )

                    # Enrich with pdf_path from metadata (for vision results) or doc_id_map
                    try:
                        # First check if pdf_path is in the doc metadata (from vision)
                        if doc.metadata and "pdf_path" in doc.metadata:
                            pdf_path_val = doc.metadata["pdf_path"]
                            # Ensure it's a string, not dict
                            citation.pdf_path = (
                                str(pdf_path_val) if pdf_path_val else None
                            )
                        else:
                            # Otherwise try doc_id_map (for text retrieval)
                            doc_id_map = _get_doc_id_map()
                            if doc.doc_id in doc_id_map:
                                doc_info = doc_id_map[doc.doc_id]
                                # Handle both dict format (new) and string format (legacy)
                                if isinstance(doc_info, dict):
                                    pdf_path_val = doc_info.get("pdf_path")
                                    citation.pdf_path = (
                                        str(pdf_path_val) if pdf_path_val else None
                                    )
                                elif isinstance(doc_info, str):
                                    citation.pdf_path = doc_info
                    except Exception:
                        pass

                    citations.append(citation)
                    seen_citations.add(citation_key)

        # If no citations found but doc_mapping exists, use top docs as implicit citations
        if not citations and doc_mapping and self.config.include_citations:
            for doc_num in sorted(doc_mapping.keys())[:3]:  # Use top 3 docs
                doc = doc_mapping[doc_num]
                page = doc.page if doc.page else 1

                # Extract metadata for implicit citation
                implicit_metadata = None
                if doc.metadata:
                    implicit_metadata = {}
                    if "tags" in doc.metadata:
                        implicit_metadata["tags"] = doc.metadata["tags"]
                    if "equipment_type" in doc.metadata:
                        implicit_metadata["equipment_type"] = doc.metadata[
                            "equipment_type"
                        ]
                    if "doc_type" in doc.metadata:
                        implicit_metadata["doc_type"] = doc.metadata["doc_type"]
                    if not implicit_metadata:
                        implicit_metadata = None

                citation = Citation(
                    doc_id=doc.doc_id,
                    source=doc.source,
                    page=page,
                    text_snippet=doc.text[:200],
                    relevance_score=doc.score,
                    metadata=implicit_metadata,
                )

                # Enrich with pdf_path from metadata (for vision results) or doc_id_map
                try:
                    # First check if pdf_path is in the doc metadata (from vision)
                    if doc.metadata and "pdf_path" in doc.metadata:
                        pdf_path_val = doc.metadata["pdf_path"]
                        # Ensure it's a string, not dict
                        citation.pdf_path = str(pdf_path_val) if pdf_path_val else None
                    else:
                        # Otherwise try doc_id_map (for text retrieval)
                        doc_id_map = _get_doc_id_map()
                        if doc.doc_id in doc_id_map:
                            doc_info = doc_id_map[doc.doc_id]
                            # Handle both dict format (new) and string format (legacy)
                            if isinstance(doc_info, dict):
                                pdf_path_val = doc_info.get("pdf_path")
                                citation.pdf_path = (
                                    str(pdf_path_val) if pdf_path_val else None
                                )
                            elif isinstance(doc_info, str):
                                citation.pdf_path = doc_info
                except Exception:
                    pass

                citations.append(citation)

        # Log extraction summary for diagnostics
        try:
            logger.info(
                f"Citation extraction: found {len(citations)} citations from answer "
                f"(doc_mapping size: {len(doc_mapping) if doc_mapping else 0})"
            )
            details = _format_citations_for_log(citations)
            if details:
                logger.debug("Citations detail:\n" + "\n".join(details[:30]))
        except Exception:
            pass

        return citations

    def _try_vision_generation(
        self,
        english_query: str,
        original_query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        retrieved_docs: List[RetrievalResult],
        language: str,
        query_classification: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, List[Citation], Dict[str, Any]]]:
        """
        Attempt multimodal generation with Gemini 2.5 Pro using page images if available.
        Returns (answer, citations, vision_meta) or None if vision cannot run.

        Args:
            query_classification: Optional dict with 'type' field ("pid", "technical_doc", "auto")
                                  Used to conditionally apply tag matching bonus in reordering.
        """
        # 0) Smart strategy gate DISABLED - Vision always ON for full multimodal capability
        # User requirement: Always use Vision to combine text + image data for maximum accuracy
        strategy_meta = {}
        logger.debug("Vision strategy: ALWAYS ON (smart_vision_strategy disabled)")

        # 1) Build list of (pdf_path, page) to render (prioritize visuals if strategy suggests)
        # DIAGNOSTIC: Log top retrieved_docs metadata
        logger.info(f"[DIAGNOSTIC] Retrieved docs count: {len(retrieved_docs)}")
        for i, doc in enumerate(retrieved_docs[:3]):
            meta = doc.metadata or {}
            has_pdf_path = "pdf_path" in meta
            logger.info(
                f"[DIAGNOSTIC] Top doc #{i+1}: doc_id={doc.doc_id[:50]}, page={doc.page}, "
                f"page_start={meta.get('page_start')}, page_end={meta.get('page_end')}, "
                f"has_pdf_path={has_pdf_path}, score={doc.score:.4f}"
            )

        try:
            prioritize_visual = (
                bool(strategy_meta.get("prioritize_visual", False))
                if strategy_meta
                else False
            )
            pages_plan, pages_meta = self._build_vision_pages(
                retrieved_docs, prioritize_visual=prioritize_visual
            )
        except Exception as e:
            logger.warning(f"Failed to build vision pages: {e}")
            return None

        if not pages_plan:
            # No valid pages to render -> skip vision
            reason = (
                pages_meta.get("reason") if isinstance(pages_meta, dict) else "no_pages"
            )
            logger.warning(
                f"[DIAGNOSTIC] Vision gating: OFF (reason={reason}). "
                f"Retrieved docs: {len(retrieved_docs)}, pages_meta: {pages_meta}"
            )
            # Log first few docs to understand why no pages
            for i, doc in enumerate(retrieved_docs[:3]):
                meta = doc.metadata or {}
                logger.warning(
                    f"[DIAGNOSTIC] Doc #{i+1} skipped: doc_id={doc.doc_id[:50] if doc.doc_id else 'None'}, "
                    f"has_metadata_pdf_path={'pdf_path' in meta}, in_doc_id_map={doc.doc_id in doc_id_map if doc.doc_id else False}"
                )
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

        # Build vision-specific doc_mapping that maps to actual vision pages
        vision_doc_mapping: Dict[int, RetrievalResult] = {}
        doc_id_map = _get_doc_id_map()

        for idx, item in enumerate(pages_plan, 1):
            pdf_path = item["pdf_path"]
            page = int(item["page"])  # 1-based
            # Prefer doc_id carried in pages_plan; fallback to reverse lookup
            carried_doc_id = item.get("doc_id") if isinstance(item, dict) else None
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

                # Find doc_id for this pdf_path from doc_id_map (reverse lookup)
                doc_id_for_path = carried_doc_id
                if not doc_id_for_path:
                    for did, doc_info in doc_id_map.items():
                        # Handle both dict format (new) and string format (legacy)
                        dpath = None
                        if isinstance(doc_info, dict):
                            dpath = doc_info.get("pdf_path")
                        elif isinstance(doc_info, str):
                            dpath = doc_info

                        if dpath == pdf_path:
                            doc_id_for_path = did
                            break

                # Create a synthetic RetrievalResult for this vision page
                # This will be used for citation extraction
                vision_doc_mapping[idx] = RetrievalResult(
                    chunk_id=f"vision_{idx}",
                    doc_id=doc_id_for_path or f"vision_page_{idx}",
                    source="vision",
                    page=page,
                    text=f"Page {page} from {pdf_path}",
                    score=1.0,
                    metadata={
                        "pdf_path": pdf_path,
                        "page": page,
                        "doc_id": doc_id_for_path,
                    },
                )
            except Exception as e:
                pages_failed.append(
                    {"pdf_path": pdf_path, "page": page, "reason": str(e)[:200]}
                )
                logger.debug(f"Render failed for {pdf_path} p.{page}: {e}")

        if not images:
            # Rendering failed for all pages
            logger.info("Vision gating: OFF (all page renders failed)")
            return None

        # 2.5) Reorder vision_doc_mapping by relevance (Task 3 fix)
        # Pages with query keywords/tags should be ranked higher as [Doc 1], [Doc 2]
        # DIAGNOSTIC: Log reorder process
        logger.info(
            f"[DIAGNOSTIC] Starting reorder for {len(vision_doc_mapping)} vision pages"
        )
        try:
            # Extract potential keywords/tags from query
            query_tokens = set(re.findall(r"\b[\w-]+\b", english_query.lower()))
            query_tokens.update(re.findall(r"\b[\w-]+\b", original_query.lower()))

            # Score each page by relevance
            page_scores = []
            for idx, result in vision_doc_mapping.items():
                score = 0.0
                matched_via = "no_match"

                # Check if this page is from a retrieved doc with high score
                # FIXED: Match by doc_id + page proximity for accurate ranking
                best_match_score = 0.0
                best_match_rank = 999
                best_match_doc = None

                for rank_idx, doc in enumerate(retrieved_docs[:20]):  # Top 20 docs
                    result_doc_id = result.metadata.get("doc_id")

                    # Try matching by doc_id (most reliable for our case)
                    if doc.doc_id and result_doc_id and doc.doc_id == result_doc_id:
                        # Matched by doc_id - same document
                        # Check page proximity to find the best matching chunk
                        page_distance = abs(result.page - doc.page) if doc.page else 999

                        # Calculate match score with page proximity weight
                        # Closer pages = better match
                        proximity_bonus = max(
                            0, 50 - (page_distance * 10)
                        )  # ±0 pages=50, ±1=40, ±2=30, etc.
                        rank_bonus = max(
                            0, 100 - (rank_idx * 5)
                        )  # Rank 0=100, 1=95, 2=90, etc.
                        doc_score = doc.score * 10  # Retrieval score

                        match_score = doc_score + rank_bonus + proximity_bonus

                        # Keep the best match (highest score)
                        if match_score > best_match_score:
                            best_match_score = match_score
                            best_match_rank = rank_idx
                            best_match_doc = doc
                            score = match_score
                            matched_via = "doc_id"

                # Apply tag matching bonus to best matched doc
                # NEW: Only apply tag bonus for P&ID queries (not technical_doc)
                if best_match_doc and best_match_doc.text:
                    doc_text_lower = best_match_doc.text.lower()

                    # Check for specific patterns (tags, numbers)
                    # Use flexible pattern to catch variations like 04-FIC-2035 or 04/FIC/2035
                    tag_patterns = re.findall(
                        r"\b\d+[-/][A-Z]{2,}[-/]\d+\b",
                        best_match_doc.text,
                        re.IGNORECASE,
                    )
                    if tag_patterns:
                        # Determine if we should apply tag bonus based on query classification
                        query_type = (
                            query_classification.get("type")
                            if query_classification
                            else None
                        )
                        apply_tag_bonus = (
                            query_type != "technical_doc"
                        )  # Disable for technical_doc, enable for pid/auto

                        for tag in tag_patterns:
                            if (
                                tag.lower() in original_query.lower()
                                or tag.lower() in english_query.lower()
                            ):
                                if apply_tag_bonus:
                                    score += 50  # Strong boost for matching tags
                                    matched_via = "tag_match"
                                    logger.info(
                                        f"[DIAGNOSTIC] Tag match found: {tag} in page {result.page} (bonus applied, query_type={query_type})"
                                    )
                                else:
                                    logger.info(
                                        f"[DIAGNOSTIC] Tag match found: {tag} in page {result.page} (bonus SKIPPED, query_type={query_type})"
                                    )

                    # Check for keyword overlap
                    keyword_count = 0
                    for token in query_tokens:
                        if len(token) > 3 and token in doc_text_lower:
                            score += 1
                            keyword_count += 1

                    if keyword_count > 5 and matched_via == "doc_id":
                        matched_via = "doc_id+keywords"

                page_scores.append((idx, result, score, matched_via))
                logger.info(
                    f"[DIAGNOSTIC] Vision page idx={idx} (page={result.page}): score={score:.2f}, matched_via={matched_via}"
                )

            # Sort by score descending
            page_scores.sort(key=lambda x: x[2], reverse=True)

            # Rebuild vision_doc_mapping with new order
            new_vision_doc_mapping = {}
            for new_idx, (old_idx, result, score, matched_via) in enumerate(
                page_scores, 1
            ):
                new_vision_doc_mapping[new_idx] = result
                logger.info(
                    f"[DIAGNOSTIC] Reordered: [Doc {new_idx}] = page {result.page} (was idx={old_idx}, score={score:.2f})"
                )

            vision_doc_mapping = new_vision_doc_mapping

            logger.info(
                f"[DIAGNOSTIC] Reorder complete. Top 3 pages: "
                f"{[vision_doc_mapping[i].page for i in list(vision_doc_mapping.keys())[:3]]}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to reorder vision_doc_mapping: {e}. Using original order."
            )

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
        # Use vision_doc_mapping for prompt to match actual shown pages
        mapping_lines = []
        for i, doc in vision_doc_mapping.items():
            try:
                mapping_lines.append(f"Doc {i} -> {doc.doc_id}")
            except Exception:
                mapping_lines.append(f"Doc {i} -> unknown")
        attached_lines = [
            f"(Doc {i}, p.{d.page if d and d.page else 'unknown'})"
            for i, d in vision_doc_mapping.items()
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
        # Fixed: Use types.Part(text=...) instead of from_text()
        # See: google-genai SDK 1.36.0 API changes
        parts = [types.Part(text=prompt_text)]
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
            # Check both hasattr and not None to avoid NoneType error in regex
            answer_text = resp.text if (hasattr(resp, "text") and resp.text) else ""
            if not answer_text:
                logger.warning("Vision generation returned empty response from Gemini")
                return None
        except Exception as e:
            logger.error(f"Gemini multimodal generation failed: {e}")
            return None

        # Extract citations from answer using vision_doc_mapping
        # This ensures citations point to the actual pages shown in vision images
        citations = self._extract_citations(answer_text, vision_doc_mapping)

        # Build a doc_number_map for vision mapping so frontend can render IEEE references correctly
        vision_doc_number_map = {}
        try:
            from pathlib import Path as _Path

            for i, result in vision_doc_mapping.items():
                # Extract pdf_path and file_name from result.metadata
                pdf_path_val = None
                if result.metadata and "pdf_path" in result.metadata:
                    pdf_path_val = result.metadata.get("pdf_path")
                file_name = "Unknown"
                if pdf_path_val:
                    try:
                        file_name = _Path(pdf_path_val).name
                    except Exception:
                        file_name = "Unknown"
                vision_doc_number_map[i] = {
                    "doc_id": result.doc_id or "unknown",
                    "pdf_path": str(pdf_path_val) if pdf_path_val else "",
                    "file_name": file_name,
                }
        except Exception:
            vision_doc_number_map = {}

        vision_meta = {
            "pages_used": pages_used,
            "pages_failed": pages_failed,
            "excerpts": [],  # Optional: can parse excerpts from answer in future
            "vision_strategy": strategy_meta,
            "doc_number_map": vision_doc_number_map,
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

    def _generate_structured(
        self,
        english_query: str,
        original_query: str,
        context: str,
        doc_mapping: Dict[int, RetrievalResult],
        language: str,
    ) -> Optional[Tuple[str, List[Citation]]]:
        """
        Generate answer using structured JSON mode (Phase 0).
        Returns (answer, citations) or None if generation fails.
        """
        try:
            from google import genai
            from google.genai import types

            from app.rag.schemas_structured import get_simple_citation_schema
            from app.services.llm import get_api_key_for
        except ImportError as e:
            logger.error(f"Failed to import structured generation dependencies: {e}")
            return None

        # Build doc mapping info for LLM
        doc_info_lines = []
        for doc_num, result in doc_mapping.items():
            doc_id = result.doc_id or "unknown"
            page = result.page or "?"
            doc_info_lines.append(f"Doc {doc_num} = {doc_id}, page {page}")
        doc_mapping_text = "\n".join(doc_info_lines)

        # Construct prompt for structured output
        if language == "vi":
            instruction = (
                "Bạn là trợ lý kỹ thuật chính xác. Trả lời bằng Tiếng Việt. "
                "Trả về JSON với trường 'answer' (câu trả lời đầy đủ) và 'citations' "
                "(mảng các trích dẫn với doc_id, page, quote). "
                "Mỗi thông số kỹ thuật cụ thể PHẢI có trích dẫn."
            )
            prompt_text = (
                f"Câu hỏi: {original_query}\n"
                f"(English: {english_query})\n\n"
                f"Ngữ cảnh từ tài liệu:\n{context}\n\n"
                f"Mapping:\n{doc_mapping_text}\n\n"
                "Trả lời với citations:"
            )
        else:
            instruction = (
                "You are a precise technical assistant. Return JSON with 'answer' "
                "(full answer text) and 'citations' (array of citations with doc_id, page, quote). "
                "Every specific technical value MUST have a citation."
            )
            prompt_text = (
                f"Question: {english_query}\n\n"
                f"Context:\n{context}\n\n"
                f"Mapping:\n{doc_mapping_text}\n\n"
                "Answer with citations:"
            )

        # Get schema and build config
        schema = get_simple_citation_schema()
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_answer_length,
            system_instruction=instruction,
        )

        # Create client and generate
        try:
            api_key = get_api_key_for("gemini")
            client = genai.Client(api_key=api_key)

            model_name = (
                self.config.vision_model  # Use same model as vision
                if self.config.vision_model.startswith("models/")
                else f"models/{self.config.vision_model}"
            )

            contents = [
                types.Content(role="user", parts=[types.Part(text=prompt_text)])
            ]

            resp = client.models.generate_content(
                model=model_name, contents=contents, config=cfg
            )

            # Parse JSON response
            import json

            result = json.loads(resp.text)

            answer_text = result.get("answer", "")
            raw_citations = result.get("citations", [])

            # Convert to Citation objects
            citations = []
            for raw_cit in raw_citations:
                doc_id = raw_cit.get("doc_id")
                page = raw_cit.get("page")
                if doc_id and page:
                    # Find pdf_path from doc_id
                    pdf_path = None
                    doc_id_map = _get_doc_id_map()
                    if doc_id in doc_id_map:
                        doc_info = doc_id_map[doc_id]
                        if isinstance(doc_info, dict):
                            pdf_path = doc_info.get("pdf_path")
                        elif isinstance(doc_info, str):
                            pdf_path = doc_info

                    citations.append(
                        Citation(
                            doc_id=doc_id,
                            source=doc_id,  # Use doc_id as source
                            page=int(page),
                            text_snippet=raw_cit.get("quote", ""),
                            relevance_score=1.0,
                            pdf_path=pdf_path,
                        )
                    )

            logger.info(f"Structured generation: {len(citations)} citations extracted")
            return answer_text, citations

        except Exception as e:
            logger.error(f"Structured generation failed: {e}")
            return None

    def _build_vision_pages(
        self, retrieved_docs: List[RetrievalResult], prioritize_visual: bool = False
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
        def add_page(pdf_path: str, page: int, doc_id_for_page: Optional[str] = None):
            key = (pdf_path, page)
            if key in seen:
                return
            if len(pages) >= max_pages:
                return
            item = {"pdf_path": pdf_path, "page": page}
            if doc_id_for_page:
                item["doc_id"] = doc_id_for_page
            pages.append(item)
            seen.add(key)

        # Helper to check if a text likely references figures/tables
        def looks_visual(text: str) -> bool:
            if not text:
                return False
            t = text.lower()
            for kw in self.config.vision_table_figure_keywords:
                if kw in t:
                    return True
            # Heuristic: contains table-like patterns
            if "|" in t or "\t" in t:
                return True
            return False

        # IMPROVED: Prioritize top-k chunks without dedupe by doc_id
        # Old logic: stopped at max_pages, causing some high-rank chunks to be skipped
        # New logic: extract unique pages from ALL top-k chunks first, then limit to max_pages

        # Step 1: Collect all candidate pages from retrieved docs with their scores
        candidate_pages: List[Dict[str, Any]] = []

        for rank_idx, doc in enumerate(retrieved_docs):
            doc_id = doc.doc_id or (
                doc.metadata.get("doc_id") if doc.metadata else None
            )

            # Resolve pdf_path via doc_id_map first, then fallback to metadata
            pdf_path = None
            if doc_id and doc_id in doc_id_map:
                doc_info = doc_id_map[doc_id]
                if isinstance(doc_info, dict):
                    pdf_path = doc_info.get("pdf_path")
                elif isinstance(doc_info, str):
                    pdf_path = doc_info
            # Fallback: use metadata-provided pdf_path if available
            if not pdf_path and doc.metadata and "pdf_path" in doc.metadata:
                try:
                    pdf_path_val = doc.metadata.get("pdf_path")
                    pdf_path = str(pdf_path_val) if pdf_path_val else None
                except Exception:
                    pdf_path = None

            if not pdf_path:
                # Cannot determine a pdf_path for this doc, skip
                continue
            # Determine page range
            meta = doc.metadata or {}
            start = None
            end = None
            try:
                # NEW: Try to extract page from content first (more reliable)
                from app.utils.page_utils import (
                    extract_page_from_content,
                    get_best_page_number,
                )

                # Task 5: P&ID-specific heuristics
                # Check if doc contains tag patterns (e.g., 04-FIC-2035)
                tag_pattern_found = False
                if hasattr(doc, "text") and doc.text:
                    # Look for equipment tags like XX-YYY-ZZZZ
                    tag_matches = re.findall(r"\b\d+[-/][A-Z]{2,}[-/]\d+\b", doc.text)
                    if tag_matches:
                        tag_pattern_found = True
                        logger.debug(f"Found tags in doc: {tag_matches[:3]}")

                # Get the most accurate page number
                # DIAGNOSTIC: Log center calculation logic
                if hasattr(doc, "text") and doc.text:
                    center = get_best_page_number(doc.text, meta)
                    logger.info(
                        f"[DIAGNOSTIC] get_best_page_number returned center={center} for doc_id={doc_id[:40]}"
                    )
                else:
                    # Fallback to metadata-based extraction
                    center = doc.page if doc.page else extract_page_number(meta)
                    logger.info(
                        f"[DIAGNOSTIC] No text, using metadata: center={center} (doc.page={doc.page})"
                    )

                    # Task 5: Smart fallback for P&ID - small-page-bias instead of middle-of-range
                    if center == 1 and "page_end" in meta:
                        page_start = meta.get("page_start", 1)
                        page_end = meta.get("page_end", 1)
                        if page_end > page_start + 5:
                            # Check if doc_id or pdf_path suggests P&ID (check multiple patterns)
                            pdf_path_upper = pdf_path.upper() if pdf_path else ""
                            doc_id_upper = str(doc_id).upper() if doc_id else ""
                            is_pid = (
                                "P&ID" in pdf_path_upper
                                or "P & I" in pdf_path_upper
                                or "P_ID" in pdf_path_upper
                            ) or (
                                "P&ID" in doc_id_upper
                                or "P & I" in doc_id_upper
                                or "P_ID" in doc_id_upper
                            )

                            logger.info(
                                f"[DIAGNOSTIC] Detected wide range [{page_start}-{page_end}], is_pid={is_pid}, "
                                f"tag_found={tag_pattern_found}"
                            )

                            if is_pid and not tag_pattern_found:
                                # For P&ID without explicit tags, prefer early pages (legends/headers)
                                old_center = center
                                center = min(
                                    10, page_end // 4
                                )  # Bias towards pages 1-10
                                logger.info(
                                    f"[DIAGNOSTIC] P&ID small-page-bias: changed center from {old_center} to {center}"
                                )
                            else:
                                # Original middle-of-range logic
                                old_center = center
                                center = (page_start + page_end) // 2
                                logger.info(
                                    f"[DIAGNOSTIC] Middle-of-range: changed center from {old_center} to {center}"
                                )

                center = int(center) if center else 1

                # FIXED: Override center if it's too far from start for P&ID with tag patterns in doc
                # This handles case where get_best_page_number returns middle-of-range (e.g., 58)
                # Force early pages when: P&ID + center too far + doc contains equipment tags + large doc
                page_start = meta.get("page_start", 1)
                page_end = meta.get("page_end", center)
                # Detect P&ID: check for "P&ID", "P & I", or "P_ID" patterns (based on actual data)
                pdf_path_upper = pdf_path.upper() if pdf_path else ""
                doc_id_upper = str(doc_id).upper() if doc_id else ""
                is_pid = (
                    "P&ID" in pdf_path_upper
                    or "P & I" in pdf_path_upper
                    or "P_ID" in pdf_path_upper
                ) or (
                    "P&ID" in doc_id_upper
                    or "P & I" in doc_id_upper
                    or "P_ID" in doc_id_upper
                )

                # REMOVED: P&ID override logic was causing incorrect page selection
                # When retrieval correctly identifies page 71 with tag "MYLP 04504",
                # forcing to page 10 causes wrong citations.
                # Tag patterns in doc.text are accurate content, not false positives.

                start = max(1, center - 1)  # Reduced from center-2 to center-1
                end = center + 1  # Reduced from center+2 to center+1 (3 pages total)
                logger.info(
                    f"[DIAGNOSTIC] Final page window: [{start}-{end}] (center={center})"
                )
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

            # If prioritizing visuals, require the doc text to look visual
            if prioritize_visual:
                try:
                    sample_text = (doc.text or "")[:400]
                    if not looks_visual(sample_text):
                        # Skip non-visual-looking docs when prioritizing visuals
                        continue
                except Exception:
                    pass

            # Collect candidate pages with metadata (rank, score)
            for p in range(start, end + 1):
                candidate_pages.append(
                    {
                        "pdf_path": pdf_path,
                        "page": p,
                        "doc_id": doc_id,
                        "rank": rank_idx,  # Lower is better
                        "score": doc.score
                        if hasattr(doc, "score") and doc.score
                        else 0.0,
                    }
                )

        # Step 2: Sort candidates by rank (lower is better), then by page number
        # This ensures top-k chunks are prioritized
        candidate_pages.sort(key=lambda x: (x["rank"], x["page"]))

        # Step 3: Dedupe by (pdf_path, page) tuple and limit to max_pages
        for candidate in candidate_pages:
            if len(pages) >= max_pages:
                break
            add_page(
                candidate["pdf_path"],
                candidate["page"],
                doc_id_for_page=candidate["doc_id"],
            )

        logger.info(
            f"Vision page selection: {len(candidate_pages)} candidates → "
            f"{len(pages)} unique pages (max={max_pages})"
        )

        return pages, {
            "selected": len(pages),
            "max": max_pages,
            "candidates": len(candidate_pages),
        }

    def _calculate_confidence(
        self, answer: str, citations: List[Citation], docs: List[RetrievalResult]
    ) -> float:
        """Calculate confidence score for the answer"""

        # Base confidence from document scores
        if docs:
            # IMPORTANT: Ensure scores are non-negative (can be negative from cross-encoder)
            # Also handle None scores (defensive: some retrievers may not set score)
            avg_score = sum(max(0, (d.score or 0)) for d in docs[:3]) / min(
                3, len(docs)
            )
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

        # IMPORTANT: Final clamp to ensure confidence is always in [0, 1] range
        # This handles any edge cases where calculations might produce values outside bounds
        return max(0.0, min(1.0, base_confidence))

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

    def _post_validate_citations(
        self,
        citations: List[Citation],
        query: str,
        retrieved_docs: List[RetrievalResult],
    ) -> Tuple[List[Citation], Dict[str, Any]]:
        """
        Post-validate citations using CitationValidator (CiteFix-lite)

        Args:
            citations: List of citations extracted from LLM answer
            query: Original search query
            retrieved_docs: Retrieved documents for context

        Returns:
            Tuple of (validated_citations, validation_summary)
        """
        from app.rag.citation_validator import get_citation_validator

        # Initialize validator
        validator = get_citation_validator(
            validation_level=self.config.citation_validation_level,
            min_confidence_threshold=self.config.citation_min_confidence,
            neighbor_scan_range=self.config.citation_neighbor_scan,
        )

        validated_citations = []
        validation_results = {
            "total_count": len(citations),
            "valid_count": 0,
            "invalid_count": 0,
            "corrected_count": 0,
            "avg_confidence": 0.0,
            "details": [],
        }

        total_confidence = 0.0

        for idx, citation in enumerate(citations):
            try:
                # Get page text (use snippet if available, otherwise try to load from page)
                page_text = citation.text_snippet or ""

                # If no text in citation, try to find from retrieved docs
                if not page_text:
                    for doc in retrieved_docs:
                        if doc.doc_id == citation.doc_id and doc.page == citation.page:
                            page_text = doc.text or ""
                            break

                # Validate citation
                validation_result = validator.validate(
                    doc_id=citation.doc_id,
                    page=citation.page or 1,
                    page_text=page_text,
                    snippets=None,  # Can add snippet validation if needed
                    query=query,
                )

                # Track validation details
                detail = {
                    "citation_index": idx,
                    "doc_id": citation.doc_id,
                    "page": citation.page,
                    "is_valid": validation_result.is_valid,
                    "confidence": validation_result.confidence,
                    "errors": [e.to_dict() for e in validation_result.errors],
                }

                # Check for neighbor page correction
                if validation_result.metadata.get("neighbor_match"):
                    neighbor = validation_result.metadata["neighbor_match"]
                    detail["corrected_page"] = neighbor["page"]
                    detail["correction_confidence"] = neighbor["confidence"]

                    # Update citation with corrected page
                    citation.page = neighbor["page"]
                    validation_results["corrected_count"] += 1

                    logger.info(
                        f"Citation corrected: {citation.doc_id} p.{citation.page} -> p.{neighbor['page']} "
                        f"(confidence: {neighbor['confidence']:.3f})"
                    )

                # Update citation confidence (use validator's confidence if higher)
                if validation_result.confidence > citation.relevance_score:
                    citation.relevance_score = validation_result.confidence

                # Phase 2 - Day 12-13: Add bbox detection for validated citations
                # Check feature flag first
                if (
                    citation.pdf_path
                    and citation.text_snippet
                    and self._is_bbox_detection_enabled()
                ):
                    import time

                    from app.core.metrics import MetricsCollector

                    bbox_start = time.time()
                    bbox_found = False
                    bbox_confidence = 0.0
                    bbox_error = False

                    try:
                        from app.core.config import settings
                        from tools.pdf_renderer import find_bbox_by_quote

                        # Improved quote selection (Day 13)
                        # Try full snippet first, then truncated if too long
                        quote_candidates = [
                            citation.text_snippet,  # Full snippet
                            citation.text_snippet[:200],  # First 200 chars
                            citation.text_snippet[:100],  # First 100 chars (fallback)
                        ]

                        # Use first non-empty candidate
                        quote_text = next(
                            (q for q in quote_candidates if len(q.strip()) >= 10),
                            citation.text_snippet[:100],
                        )

                        # Get fuzzy threshold from settings
                        fuzzy_threshold = getattr(
                            settings, "bbox_detection_fuzzy_threshold", 0.8
                        )

                        logger.debug(
                            f"Bbox detection for {citation.doc_id} p.{citation.page}: "
                            f"quote_len={len(quote_text)}, threshold={fuzzy_threshold}"
                        )

                        # Find bbox candidates (list)
                        from tools.pdf_renderer import normalize_bbox as _normalize_bbox

                        matches = find_bbox_by_quote(
                            pdf_path=citation.pdf_path,
                            page_num=citation.page or 1,
                            quote=quote_text,
                            fuzzy=True,
                            use_cache=True,
                        )

                        if matches:
                            # Pick best by confidence
                            best = max(
                                matches, key=lambda m: float(m.get("confidence", 0.0))
                            )
                            bbox_abs = best.get("bbox")
                            pw = best.get("page_width")
                            ph = best.get("page_height")
                            if bbox_abs and pw and ph:
                                citation.bbox = list(
                                    _normalize_bbox(tuple(bbox_abs), pw, ph)
                                )
                                bbox_found = True
                                bbox_confidence = float(best.get("confidence", 0.0))
                                detail["bbox_found"] = True
                                detail["bbox_confidence"] = bbox_confidence
                                detail["bbox_quote_length"] = len(quote_text)

                                logger.debug(
                                    f"✓ Bbox detected: {citation.doc_id} p.{citation.page} "
                                    f"confidence={bbox_confidence:.2f}, bbox={citation.bbox}"
                                )
                            else:
                                detail["bbox_found"] = False
                                logger.debug(
                                    f"✗ Bbox result missing geometry for {citation.doc_id} p.{citation.page}"
                                )
                        else:
                            detail["bbox_found"] = False
                            logger.debug(
                                f"✗ Bbox not found: {citation.doc_id} p.{citation.page} "
                                f"(quote_len={len(quote_text)})"
                            )

                    except Exception as e:
                        bbox_error = True
                        logger.debug(f"Bbox detection error for citation {idx}: {e}")
                        detail["bbox_error"] = str(e)[:100]

                    finally:
                        # Record metrics (Day 13)
                        bbox_latency_ms = (time.time() - bbox_start) * 1000
                        try:
                            MetricsCollector.record_bbox_detection(
                                latency_ms=bbox_latency_ms,
                                found=bbox_found,
                                confidence=bbox_confidence if bbox_found else None,
                                error=bbox_error,
                            )
                        except Exception:
                            pass  # Don't fail validation if metrics fail

                validation_results["details"].append(detail)
                total_confidence += validation_result.confidence

                if validation_result.is_valid:
                    validation_results["valid_count"] += 1
                    validated_citations.append(citation)
                else:
                    validation_results["invalid_count"] += 1
                    # Keep citation but mark as low confidence
                    citation.relevance_score = min(citation.relevance_score, 0.5)
                    validated_citations.append(citation)

                    logger.warning(
                        f"Citation validation failed: {citation.doc_id} p.{citation.page} "
                        f"(confidence: {validation_result.confidence:.3f}, errors: {len(validation_result.errors)})"
                    )

            except Exception as e:
                logger.error(f"Failed to validate citation {idx}: {e}")
                # Keep original citation on error
                validated_citations.append(citation)
                validation_results["details"].append(
                    {
                        "citation_index": idx,
                        "error": str(e),
                    }
                )

        # Calculate average confidence
        if validation_results["total_count"] > 0:
            validation_results["avg_confidence"] = (
                total_confidence / validation_results["total_count"]
            )

        # Task 7: Enhanced logging summary
        logger.info(
            f"Post-validation summary: {validation_results['total_count']} citations processed, "
            f"{validation_results['valid_count']} valid, {validation_results['corrected_count']} corrected, "
            f"avg_confidence={validation_results['avg_confidence']:.3f}"
        )

        return validated_citations, validation_results

    def _smart_vision_strategy(
        self,
        english_query: str,
        retrieved_docs: List[RetrievalResult],
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Decide whether to use vision and how to prioritize pages (Phase 2 - Day 11).

        Heuristics:
        - If query suggests visuals (table/figure keywords) -> use vision
        - Else if retrieved_docs top texts suggest visuals -> use vision
        - Else -> skip vision if configured to skip for text-only

        Returns a dict:
        {
            should_use_vision: bool,
            reason: str,
            prioritize_visual: bool,  # if True, filter to visual-like pages
            keywords_matched: List[str],
        }
        """
        # If vision disabled globally, skip
        if not self.config.enable_vision_generation:
            return {"should_use_vision": False, "reason": "vision_disabled"}

        # Normalize
        q = (english_query or "").lower()
        matched_keywords = [
            kw for kw in self.config.vision_table_figure_keywords if kw in q
        ]
        looks_visual_query = len(matched_keywords) > 0

        # Inspect top retrieved docs for visual cues
        looks_visual_docs = False
        doc_keywords = set()
        for doc in (retrieved_docs or [])[:5]:
            try:
                t = (doc.text or "")[:600].lower()
                for kw in self.config.vision_table_figure_keywords:
                    if kw in t:
                        looks_visual_docs = True
                        doc_keywords.add(kw)
                # Heuristic: table-like content
                if ("|" in t) or ("\t" in t):
                    looks_visual_docs = True
                    doc_keywords.add("table-like")
            except Exception:
                continue

        # Decision
        if looks_visual_query or looks_visual_docs:
            return {
                "should_use_vision": True,
                "reason": "visual_keywords",
                "prioritize_visual": True,
                "keywords_matched": list(set(matched_keywords) | doc_keywords),
            }

        # Otherwise text-only likely
        if self.config.vision_skip_text_only:
            return {
                "should_use_vision": False,
                "reason": "text_only",
                "prioritize_visual": False,
                "keywords_matched": [],
            }

        # Default: allow vision but without prioritization
        return {
            "should_use_vision": True,
            "reason": "default_allow",
            "prioritize_visual": False,
            "keywords_matched": [],
        }

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
