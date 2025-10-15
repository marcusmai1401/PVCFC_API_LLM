"""
Page-First RAG Agent - Operation Manual Implementation

Main orchestrator for Page-First RAG pipeline following Operation Manual steps A-G:
    A) Query normalization
    B) Hybrid retrieval (BM25 + Vector)
    C) RRF merge and deduplication
    D) Cross-encoder reranking
    E) Context building
    F) LLM structured output
    G) CiteFix validation and metrics

This Phase 1 implementation provides the skeleton and integration points.
Full orchestration logic to be implemented in Phase 2.

Example:
    >>> from app.rag.page_first_config import PageFirstConfig
    >>> from app.rag.page_first_agent import PageFirstAgent
    >>>
    >>> config = PageFirstConfig.from_env()
    >>> agent = PageFirstAgent(config)
    >>> # Phase 2: result = agent.answer("What is the maximum pressure?")
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.rag.page_first_config import PageFirstConfig

logger = logging.getLogger(__name__)


# Type aliases for clarity
PageHit = Dict[str, Any]  # {doc_id, page, score, text, ...}
Citation = Dict[str, Any]  # {doc_id, page, quote, confidence, ...}


class PageFirstAgent:
    """
    Page-First RAG Agent implementing Operation Manual workflow.

    Orchestrates the complete pipeline from query to answered with citations:
    - Step A: Query normalization
    - Step B: Hybrid page retrieval (BM25 + Vector)
    - Step C: RRF merge and deduplication
    - Step D: Cross-encoder page reranking
    - Step E: Context construction with neighbor pages
    - Step F: LLM call with structured output
    - Step G: CiteFix validation with NLI scoring

    Integration points:
        - PageReranker: for BM25 page search and text loading
        - CitationValidator: for citation post-validation
        - RuleBasedNLIValidator: for entailment scoring
        - HybridRetriever: for vector search (optional)

    Example:
        >>> config = PageFirstConfig(TOPK_BM25=30, RERANK_KEEP=8)
        >>> agent = PageFirstAgent(config)
        >>> # Phase 2: response = agent.answer("maximum pressure for KT06101?")
    """

    def __init__(
        self,
        config: PageFirstConfig,
        reranker: Optional[Any] = None,
        citation_validator: Optional[Any] = None,
        nli_validator: Optional[Any] = None,
        retriever: Optional[Any] = None,
    ):
        """
        Initialize Page-First RAG Agent.

        Args:
            config: PageFirstConfig with all parameters
            reranker: PageReranker instance (lazy loaded if None)
            citation_validator: CitationValidator instance (lazy loaded if None)
            nli_validator: RuleBasedNLIValidator instance (lazy loaded if None)
            retriever: HybridRetriever instance (lazy loaded if None)
        """
        self.config = config
        self.config.validate()

        logger.info(f"Initializing PageFirstAgent with config: {self.config}")

        # Lazy import and instantiate dependencies
        self.reranker = reranker or self._lazy_load_reranker()
        self.citation_validator = (
            citation_validator or self._lazy_load_citation_validator()
        )
        self.nli_validator = nli_validator or self._lazy_load_nli_validator()
        self.retriever = retriever  # Optional, may stay None

        logger.info("PageFirstAgent initialized successfully")

    def _lazy_load_reranker(self) -> Optional[Any]:
        """Lazy load PageReranker if available."""
        try:
            from app.rag.page_reranker import PageReranker

            logger.debug("Loaded PageReranker")
            return PageReranker()
        except ImportError as e:
            logger.warning(f"PageReranker not available: {e}")
            return None

    def _lazy_load_citation_validator(self) -> Optional[Any]:
        """Lazy load CitationValidator if available."""
        try:
            from app.rag.citation_validator import CitationValidator

            logger.debug("Loaded CitationValidator")
            return CitationValidator()
        except ImportError as e:
            logger.warning(f"CitationValidator not available: {e}")
            return None

    def _lazy_load_nli_validator(self) -> Optional[Any]:
        """Lazy load RuleBasedNLIValidator."""
        try:
            from app.rag.nli_validator import RuleBasedNLIValidator

            logger.debug("Loaded RuleBasedNLIValidator")
            return RuleBasedNLIValidator()
        except ImportError as e:
            logger.warning(f"RuleBasedNLIValidator not available: {e}")
            return None

    # =========================================================================
    # STEP A: Query Normalization
    # =========================================================================

    def normalize_query(self, question: str) -> str:
        """
        Step A: Normalize user query.

        Canonicalize query for retrieval:
        - Preserve numbers, units, and technical terms
        - Normalize punctuation spacing
        - Detect language (vi/en) for later use

        TODO (Phase 2):
            - Implement language detection
            - Handle special characters in technical terms
            - Preserve case for acronyms

        Args:
            question: Raw user question

        Returns:
            Normalized query string

        Config:
            Uses config.CTX_MAX_TOKENS implicitly for later context building
        """
        # Phase 1: Placeholder implementation
        # Phase 2: Full implementation with language detection
        logger.debug(f"Normalizing query: {question[:50]}...")

        # Basic normalization (Phase 1)
        normalized = question.strip()

        return normalized

    # =========================================================================
    # STEP B: Hybrid Retrieval
    # =========================================================================

    def _search_pages_bm25(self, query: str, top_k: int) -> List[PageHit]:
        """
        Search pages using BM25.

        Uses PageReranker's BM25 index to search across all pages.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of page hits with BM25 scores
        """
        if not self.reranker:
            logger.warning("PageReranker not available, returning empty BM25 results")
            return []

        try:
            # Load BM25 index directly from PageReranker
            # First ensure index is loaded
            self.reranker._load_index()

            if self.reranker._page_index:
                import pickle
                from pathlib import Path

                import numpy as np

                # Load full index data to get doc_ids, pages, corpus
                index_path = self.reranker.page_index_path
                with open(index_path, "rb") as f:
                    data = pickle.load(f)

                bm25 = self.reranker._page_index
                doc_ids = data.get("doc_ids", [])
                pages = data.get("pages", [])
                corpus = data.get("corpus", [])

                # Tokenize query (use same tokenization as index)
                try:
                    from app.utils.text_processing import tokenize_for_bm25

                    query_tokens = tokenize_for_bm25(query)
                except ImportError:
                    # Fallback tokenization
                    query_tokens = query.lower().split()

                # Get scores
                scores = bm25.get_scores(query_tokens)

                # Get top-k indices
                top_indices = np.argsort(scores)[::-1][:top_k]

                # Build results
                results = []
                for idx in top_indices:
                    if scores[idx] > 0:  # Only include if score > 0
                        results.append(
                            {
                                "doc_id": doc_ids[idx],
                                "page": int(pages[idx]),
                                "score": float(scores[idx]),
                                "source": "bm25",
                                "text": corpus[idx][:500] if idx < len(corpus) else "",
                            }
                        )

                logger.debug(f"BM25 search returned {len(results)} results")
                return results

            else:
                logger.warning("BM25 index structure not recognized")
                return []

        except Exception as e:
            logger.error(f"BM25 search failed: {e}", exc_info=True)
            return []

    def _search_pages_vector(self, query: str, top_k: int) -> List[PageHit]:
        """
        Search pages using vector similarity.

        Uses page embeddings to find semantically similar pages.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of page hits with cosine similarity scores
        """
        try:
            from pathlib import Path

            import numpy as np

            # Load page embeddings
            embeddings_path = Path("artifacts/ingestion_production/page_embeddings.npz")

            if not embeddings_path.exists():
                logger.warning(f"Page embeddings not found at {embeddings_path}")
                return []

            # Load embeddings
            data = np.load(embeddings_path, allow_pickle=True)
            embeddings = data["embeddings"]  # Shape: (N, 768)
            doc_ids = data["doc_ids"]
            pages_data = data["pages"]

            logger.debug(f"Loaded {len(embeddings)} page embeddings")

            # Embed query
            if not hasattr(self, "_embedding_service"):
                from app.services.embedding_enhanced import EmbeddingService

                self._embedding_service = EmbeddingService()

            query_embedding = self._embedding_service.embed_text(query)
            query_vec = np.array(query_embedding).reshape(1, -1)

            # Compute cosine similarity
            # Normalize vectors
            query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
            embeddings_norm = embeddings / (
                np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
            )

            # Cosine similarity = dot product of normalized vectors
            similarities = (embeddings_norm @ query_norm.T).flatten()

            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]

            # Build results
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    results.append(
                        {
                            "doc_id": str(doc_ids[idx]),
                            "page": int(pages_data[idx]),
                            "score": float(similarities[idx]),
                            "source": "vector",
                            "text": "",  # Will load on demand if needed
                        }
                    )

            logger.debug(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            return []

    def search_pages_hybrid(self, query: str) -> tuple[List[PageHit], List[PageHit]]:
        """
        Step B: Hybrid page retrieval (BM25 + Vector).

        Retrieve candidate pages from two sources:
        1. BM25 lexical search (TOPK_BM25)
        2. Vector semantic search (TOPK_VEC)

        Args:
            query: Normalized query

        Returns:
            Tuple of (bm25_hits, vector_hits)
            Each hit: {doc_id, page, score, source, ...}

        Config:
            - config.TOPK_BM25: Number of BM25 results
            - config.TOPK_VEC: Number of vector results
        """
        import time

        start = time.time()

        logger.debug(
            f"Hybrid search: BM25={self.config.TOPK_BM25}, VEC={self.config.TOPK_VEC}"
        )

        # BM25 search
        bm25_hits = self._search_pages_bm25(query, self.config.TOPK_BM25)

        # Vector search
        vec_hits = self._search_pages_vector(query, self.config.TOPK_VEC)

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"Hybrid retrieval: {len(bm25_hits)} BM25 + {len(vec_hits)} vector "
            f"in {elapsed:.0f}ms"
        )

        return bm25_hits, vec_hits

    # =========================================================================
    # STEP C: RRF Merge
    # =========================================================================

    def rrf_merge(
        self, bm25_hits: List[PageHit], vec_hits: List[PageHit]
    ) -> List[PageHit]:
        """
        Step C: Reciprocal Rank Fusion (RRF) and deduplication.

        Merge BM25 and vector hits using RRF:
        - RRF score = sum(1 / (k + rank_i)) for each list
        - k = 60 (standard RRF constant)
        - Deduplicate by (doc_id, page)
        - Keep top MERGED_K results

        Args:
            bm25_hits: BM25 results
            vec_hits: Vector results

        Returns:
            Merged and deduplicated list of top MERGED_K pages
            Each page has 'fused_score' field

        Config:
            - config.MERGED_K: Number of pages after merge
        """
        from collections import defaultdict

        logger.debug(f"Merging {len(bm25_hits)} BM25 + {len(vec_hits)} vector hits")

        # RRF constant
        k = 60

        # Accumulate scores by (doc_id, page)
        scores = defaultdict(float)
        hit_info = {}  # Store metadata for each (doc_id, page)

        # Process BM25 hits
        for rank, hit in enumerate(bm25_hits, start=1):
            key = (hit["doc_id"], hit["page"])
            scores[key] += 1.0 / (k + rank)

            if key not in hit_info:
                hit_info[key] = {
                    "doc_id": hit["doc_id"],
                    "page": hit["page"],
                    "text": hit.get("text", ""),
                    "bm25_score": hit.get("score", 0.0),
                    "bm25_rank": rank,
                }

        # Process vector hits
        for rank, hit in enumerate(vec_hits, start=1):
            key = (hit["doc_id"], hit["page"])
            scores[key] += 1.0 / (k + rank)

            if key not in hit_info:
                hit_info[key] = {
                    "doc_id": hit["doc_id"],
                    "page": hit["page"],
                    "text": hit.get("text", ""),
                    "vec_score": hit.get("score", 0.0),
                    "vec_rank": rank,
                }
            else:
                hit_info[key]["vec_score"] = hit.get("score", 0.0)
                hit_info[key]["vec_rank"] = rank

        # Create merged results
        merged = []
        for key, rrf_score in scores.items():
            info = hit_info[key]
            merged.append(
                {
                    "doc_id": info["doc_id"],
                    "page": info["page"],
                    "text": info["text"],
                    "fused_score": rrf_score,
                    "bm25_score": info.get("bm25_score", 0.0),
                    "vec_score": info.get("vec_score", 0.0),
                    "bm25_rank": info.get("bm25_rank", None),
                    "vec_rank": info.get("vec_rank", None),
                }
            )

        # Sort by fused score descending
        merged.sort(key=lambda x: x["fused_score"], reverse=True)

        # Keep top MERGED_K
        top_merged = merged[: self.config.MERGED_K]

        logger.debug(
            f"RRF merged to {len(merged)} unique pages, " f"kept top {len(top_merged)}"
        )

        return top_merged

    # =========================================================================
    # STEP D: Cross-Encoder Reranking
    # =========================================================================

    def cross_encoder_rerank(self, query: str, pages: List[PageHit]) -> List[PageHit]:
        """
        Step D: Cross-encoder page reranking.

        Rerank pages using hybrid scoring (BM25 + semantic if available).
        Falls back to BM25 rescoring if cross-encoder unavailable.

        Args:
            query: Normalized query
            pages: Merged candidate pages

        Returns:
            Top RERANK_KEEP pages sorted by rerank_score

        Config:
            - config.RERANK_KEEP: Number of pages to keep
        """
        logger.debug(
            f"Reranking {len(pages)} pages, keeping top {self.config.RERANK_KEEP}"
        )

        if not pages:
            return []

        # Load page texts if needed
        pages_with_text = []
        for page in pages:
            if not page.get("text"):
                # Load text from PageReranker
                if self.reranker:
                    try:
                        text = self.reranker.get_page_text(page["doc_id"], page["page"])
                        page["text"] = text[:2000]  # Truncate for memory
                    except Exception as e:
                        logger.warning(
                            f"Failed to load text for {page['doc_id']} p{page['page']}: {e}"
                        )
                        page["text"] = ""

            if page.get("text"):
                pages_with_text.append(page)

        logger.debug(f"Loaded text for {len(pages_with_text)}/{len(pages)} pages")

        # Rerank using hybrid scoring
        if self.reranker and hasattr(self.reranker, "rank_pages_for_doc"):
            # Group pages by doc_id
            by_doc = {}
            for page in pages_with_text:
                doc_id = page["doc_id"]
                if doc_id not in by_doc:
                    by_doc[doc_id] = []
                by_doc[doc_id].append(page)

            # Rerank each document's pages
            reranked_all = []
            for doc_id, doc_pages in by_doc.items():
                try:
                    # Call PageReranker (returns all pages ranked)
                    ranked = self.reranker.rank_pages_for_doc(
                        query=query,
                        doc_id=doc_id,
                        top_k=100,  # Get all pages, we'll filter later
                        min_score=0.0,
                    )

                    # Build lookup: page_num -> score
                    score_lookup = {page_num: score for page_num, score in ranked}

                    # Merge scores back to our pages
                    for page in doc_pages:
                        page_num = page["page"]
                        if page_num in score_lookup:
                            page["rerank_score"] = score_lookup[page_num]
                        else:
                            # Page not in ranked results, use fused_score
                            page["rerank_score"] = page.get("fused_score", 0.0)
                        reranked_all.append(page)

                except Exception as e:
                    logger.warning(f"Reranking failed for {doc_id}: {e}")
                    # Fallback: use fused_score
                    for page in doc_pages:
                        page["rerank_score"] = page.get("fused_score", 0.0)
                        reranked_all.append(page)

        else:
            # Fallback: use fused_score from RRF
            logger.warning("PageReranker unavailable, using fused_score for reranking")
            reranked_all = pages_with_text
            for page in reranked_all:
                page["rerank_score"] = page.get("fused_score", 0.0)

        # Sort by rerank_score
        reranked_all.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Keep top RERANK_KEEP
        top_pages = reranked_all[: self.config.RERANK_KEEP]

        # Log diversity
        doc_ids = [p["doc_id"] for p in top_pages]
        unique_docs = len(set(doc_ids))
        logger.info(
            f"Reranked to top {len(top_pages)} pages " f"from {unique_docs} documents"
        )

        return top_pages

    # =========================================================================
    # STEP E: Context Building
    # =========================================================================

    def build_page_context(self, pages: List[PageHit]) -> str:
        """
        Step E: Build context from top pages.

        Construct context window:
        - For each page in top pages:
          * Add header: [DOC {doc_id} — PAGE {page}]
          * Include page text
          * Optionally include NEIGHBOR_RADIUS neighbor pages
        - Truncate to CTX_MAX_TOKENS
        - Preserve sentence boundaries

        Args:
            pages: Reranked pages

        Returns:
            Context string with page headers

        Config:
            - config.CTX_MAX_TOKENS: Maximum context tokens
            - config.NEIGHBOR_RADIUS: Neighbor pages to include
        """
        logger.debug(f"Building context, max_tokens={self.config.CTX_MAX_TOKENS}")

        if not pages:
            return ""

        # Collect all pages to include (core + neighbors)
        pages_to_include = set()
        for page in pages:
            doc_id = page["doc_id"]
            page_num = page["page"]

            # Add core page
            pages_to_include.add((doc_id, page_num))

            # Add neighbor pages
            if self.config.NEIGHBOR_RADIUS > 0:
                for offset in range(
                    -self.config.NEIGHBOR_RADIUS, self.config.NEIGHBOR_RADIUS + 1
                ):
                    if offset != 0:  # Skip center page (already added)
                        neighbor_page = page_num + offset
                        if neighbor_page > 0:  # Page numbers start at 1
                            pages_to_include.add((doc_id, neighbor_page))

        logger.debug(f"Including {len(pages_to_include)} pages (core + neighbors)")

        # Build context with page headers
        context_parts = []
        current_tokens = 0

        # Process core pages first (in rank order)
        for page in pages:
            doc_id = page["doc_id"]
            page_num = page["page"]

            # Get neighbor pages for this core page
            neighbor_pages = []
            if self.config.NEIGHBOR_RADIUS > 0:
                for offset in range(
                    -self.config.NEIGHBOR_RADIUS, self.config.NEIGHBOR_RADIUS + 1
                ):
                    neighbor_page_num = page_num + offset
                    if neighbor_page_num > 0:
                        neighbor_pages.append(neighbor_page_num)
            else:
                neighbor_pages = [page_num]

            # Sort neighbor pages
            neighbor_pages.sort()

            # Add pages to context
            for nb_page_num in neighbor_pages:
                # Check if already added
                if (doc_id, nb_page_num) in pages_to_include:
                    # Load page text
                    text = self._get_page_text(
                        doc_id, nb_page_num, page if nb_page_num == page_num else None
                    )

                    if text:
                        # Estimate tokens (rough: 4 chars per token)
                        text_tokens = len(text) // 4
                        header = f"[DOC {doc_id} — PAGE {nb_page_num}]\n"
                        header_tokens = len(header) // 4

                        # Check token limit
                        if (
                            current_tokens + header_tokens + text_tokens
                            > self.config.CTX_MAX_TOKENS
                        ):
                            # Try to fit truncated version
                            remaining_tokens = (
                                self.config.CTX_MAX_TOKENS
                                - current_tokens
                                - header_tokens
                            )
                            if remaining_tokens > 100:  # Minimum useful size
                                # Truncate at sentence boundary
                                truncated_text = self._truncate_at_sentence(
                                    text, remaining_tokens * 4
                                )
                                context_parts.append(header + truncated_text)
                                current_tokens += (
                                    header_tokens + len(truncated_text) // 4
                                )

                            # Stop adding more pages
                            logger.debug(
                                f"Context truncated at {current_tokens} tokens"
                            )
                            break

                        context_parts.append(header + text)
                        current_tokens += header_tokens + text_tokens

                        # Mark as processed
                        pages_to_include.discard((doc_id, nb_page_num))

            # Stop if context is full
            if current_tokens >= self.config.CTX_MAX_TOKENS:
                break

        context = "\n\n".join(context_parts)
        logger.info(
            f"Built context: {len(context_parts)} page sections, ~{current_tokens} tokens"
        )

        return context

    def _get_page_text(
        self, doc_id: str, page_num: int, page_hit: Optional[PageHit] = None
    ) -> str:
        """
        Get text for a specific page.

        Args:
            doc_id: Document ID
            page_num: Page number
            page_hit: Optional PageHit dict with pre-loaded text

        Returns:
            Page text or empty string if not found
        """
        # Use pre-loaded text if available
        if page_hit and page_hit.get("text"):
            return page_hit["text"]

        # Try to load from PageReranker
        if self.reranker and hasattr(self.reranker, "get_page_text"):
            try:
                text = self.reranker.get_page_text(doc_id, page_num)
                return text or ""
            except Exception as e:
                logger.debug(f"Could not load text for {doc_id} p{page_num}: {e}")

        # Fallback: load from text_by_page.jsonl
        try:
            import json
            from pathlib import Path

            text_path = Path("artifacts/ingestion_production/text_by_page.jsonl")
            if text_path.exists():
                with open(text_path, "r", encoding="utf-8") as f:
                    for line in f:
                        obj = json.loads(line)
                        if obj["doc_id"] == doc_id and obj["page"] == page_num:
                            return obj["text"]
        except Exception as e:
            logger.warning(
                f"Failed to load text from JSONL for {doc_id} p{page_num}: {e}"
            )

        return ""

    def _truncate_at_sentence(self, text: str, max_chars: int) -> str:
        """
        Truncate text at sentence boundary.

        Args:
            text: Text to truncate
            max_chars: Maximum characters

        Returns:
            Truncated text ending at sentence boundary
        """
        if len(text) <= max_chars:
            return text

        # Find last sentence boundary before max_chars
        truncated = text[:max_chars]

        # Look for sentence endings (., !, ?, \n)
        for delimiter in [". ", "! ", "? ", "\n"]:
            last_pos = truncated.rfind(delimiter)
            if last_pos > max_chars * 0.7:  # At least 70% of target
                return truncated[: last_pos + 1].strip()

        # No good sentence boundary found, just truncate
        return truncated.strip() + "..."

    # =========================================================================
    # STEP F: LLM Structured Output
    # =========================================================================

    def call_llm_structured(self, context: str, query: str) -> Dict[str, Any]:
        """
        Step F: Call LLM with structured output schema.

        Prompt LLM to generate answer with structured citations:
        - Enforce JSON schema for output
        - Each claim must have citation (doc_id, page, quote)
        - Quote must be ≤280 chars, verbatim from context
        - Constrain answer length to ANSWER_MAX_TOKENS

        Args:
            context: Built context with page headers
            query: Normalized query

        Returns:
            Dict with:
                answer: str
                citations: List[Citation]
                language: str (vi/en)
                usage: dict (tokens, latency)

        Config:
            - config.ANSWER_MAX_TOKENS: Maximum answer tokens
        """
        import json
        import time

        logger.debug(f"Calling LLM, max_answer_tokens={self.config.ANSWER_MAX_TOKENS}")

        start_time = time.time()

        # Build system prompt
        system_prompt = """You are a technical documentation assistant. Answer questions based ONLY on the provided context.

Rules:
1. Answer in the same language as the question (Vietnamese or English)
2. Be precise and concise
3. Each claim in your answer MUST be supported by a citation
4. Citations must include: doc_id, page number, and a verbatim quote (max 280 chars)
5. Quotes must be EXACTLY as they appear in context, no modifications
6. If information is not in context, say "Thông tin không có trong tài liệu" or "Information not found in documents"

Output Format (JSON):
{
  "answer": "Your detailed answer here...",
  "citations": [
    {
      "doc_id": "DOCID_...",
      "page": 123,
      "quote": "Exact quote from context...",
      "evidence_type": "direct_quote|paraphrase"
    }
  ],
  "language": "vi" or "en"
}"""

        # Build user prompt
        user_prompt = f"""Context:
{context}

---

Question: {query}

Provide a JSON response with your answer and citations."""

        # Call OpenAI API
        try:
            import os

            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=self.config.ANSWER_MAX_TOKENS + 500,  # Buffer for citations
                temperature=0.0,
            )

            # Parse response
            raw_content = response.choices[0].message.content
            result = json.loads(raw_content)

            # Validate structure
            if "answer" not in result:
                raise ValueError("LLM response missing 'answer' field")

            if "citations" not in result:
                result["citations"] = []

            if "language" not in result:
                # Auto-detect language
                result["language"] = self._detect_language(query)

            # Add usage metadata
            latency_ms = (time.time() - start_time) * 1000
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "latency_ms": latency_ms,
            }

            logger.info(
                f"LLM call successful: {result['usage']['total_tokens']} tokens, "
                f"{latency_ms:.0f}ms, {len(result['citations'])} citations"
            )

            return result

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)

            # Return fallback response
            latency_ms = (time.time() - start_time) * 1000
            return {
                "answer": f"Error generating answer: {str(e)}",
                "citations": [],
                "language": self._detect_language(query),
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": latency_ms,
                },
                "error": str(e),
            }

    def _detect_language(self, text: str) -> str:
        """
        Simple language detection (Vietnamese vs English).

        Args:
            text: Text to analyze

        Returns:
            'vi' or 'en'
        """
        # Check for Vietnamese diacritics
        vietnamese_chars = set(
            "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
        )
        vietnamese_chars.update(
            "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
        )

        text_chars = set(text.lower())
        if text_chars & vietnamese_chars:
            return "vi"

        return "en"

    # =========================================================================
    # STEP G: CiteFix Validation
    # =========================================================================

    def citefix_validate(self, citations: List[Citation], query: str) -> List[Citation]:
        """
        Step G: Post-validate and fix citations.

        For each citation:
        1. Load page text
        2. Compute fuzzy overlap (quote vs page text)
        3. Compute NLI entailment (claim vs page text)
        4. If fuzzy >= FUZZY_MIN AND nli >= NLI_THRESHOLD:
           - Keep citation, assign confidence
        5. Else:
           - Scan neighbor pages (±NEIGHBOR_RADIUS)
           - Find best page by score = 0.5*fuzzy + 0.5*nli
           - Update citation.page and confidence
        6. Deduplicate: 1 claim = 1 page (keep highest confidence)

        Args:
            citations: Raw citations from LLM
            query: Original query (for context)

        Returns:
            Validated and fixed citations with confidence scores

        Config:
            - config.FUZZY_MIN: Minimum fuzzy overlap
            - config.NLI_THRESHOLD: Minimum entailment score
            - config.NEIGHBOR_RADIUS: Page scan radius
        """
        from app.rag.fuzzy_matcher import fuzzy_overlap
        from app.rag.nli_validator import RuleBasedNLIValidator

        logger.debug(
            f"Validating {len(citations)} citations, neighbor_radius={self.config.NEIGHBOR_RADIUS}"
        )

        if not citations:
            return []

        # Initialize NLI validator if needed
        if not self.nli_validator:
            self.nli_validator = RuleBasedNLIValidator()

        validated_citations = []

        for idx, citation in enumerate(citations):
            try:
                doc_id = citation.get("doc_id", "")
                page_num = citation.get("page", 0)
                quote = citation.get("quote", "")

                if not doc_id or not page_num or not quote:
                    logger.warning(f"Citation {idx} missing required fields, skipping")
                    continue

                # Load original page text
                page_text = self._get_page_text(doc_id, page_num)

                if not page_text:
                    logger.warning(f"Could not load text for {doc_id} p{page_num}")
                    citation["confidence"] = 0.0
                    citation["fixed"] = False
                    validated_citations.append(citation)
                    continue

                # Compute fuzzy overlap
                fuzzy_score = fuzzy_overlap(quote, page_text)

                # Compute NLI entailment
                nli_score = self.nli_validator.entail(quote, page_text)

                # Check if citation is valid
                if (
                    fuzzy_score >= self.config.FUZZY_MIN
                    and nli_score >= self.config.NLI_THRESHOLD
                ):
                    # Citation is valid
                    confidence = 0.5 * fuzzy_score + 0.5 * nli_score
                    citation["confidence"] = round(confidence, 3)
                    citation["fuzzy_score"] = round(fuzzy_score, 3)
                    citation["nli_score"] = round(nli_score, 3)
                    citation["fixed"] = False
                    validated_citations.append(citation)
                    logger.debug(
                        f"Citation {idx} valid: fuzzy={fuzzy_score:.3f}, "
                        f"nli={nli_score:.3f}, confidence={confidence:.3f}"
                    )
                else:
                    # Try to fix by scanning neighbor pages
                    logger.debug(
                        f"Citation {idx} invalid (fuzzy={fuzzy_score:.3f}, nli={nli_score:.3f}), "
                        f"scanning neighbors..."
                    )

                    best_page = page_num
                    best_score = 0.5 * fuzzy_score + 0.5 * nli_score
                    best_fuzzy = fuzzy_score
                    best_nli = nli_score

                    # Scan neighbor pages
                    for offset in range(
                        -self.config.NEIGHBOR_RADIUS, self.config.NEIGHBOR_RADIUS + 1
                    ):
                        if offset == 0:
                            continue  # Already checked

                        neighbor_page_num = page_num + offset
                        if neighbor_page_num <= 0:
                            continue

                        neighbor_text = self._get_page_text(doc_id, neighbor_page_num)
                        if not neighbor_text:
                            continue

                        # Compute scores for neighbor
                        n_fuzzy = fuzzy_overlap(quote, neighbor_text)
                        n_nli = self.nli_validator.entail(quote, neighbor_text)
                        n_score = 0.5 * n_fuzzy + 0.5 * n_nli

                        if n_score > best_score:
                            best_score = n_score
                            best_page = neighbor_page_num
                            best_fuzzy = n_fuzzy
                            best_nli = n_nli

                    # Update citation with best page found
                    if best_page != page_num:
                        logger.info(
                            f"Citation {idx} FIXED: {doc_id} p{page_num} -> p{best_page} "
                            f"(score: {best_score:.3f})"
                        )
                        citation["page"] = best_page
                        citation["fixed"] = True
                    else:
                        citation["fixed"] = False

                    citation["confidence"] = round(best_score, 3)
                    citation["fuzzy_score"] = round(best_fuzzy, 3)
                    citation["nli_score"] = round(best_nli, 3)
                    validated_citations.append(citation)

            except Exception as e:
                logger.error(f"Error validating citation {idx}: {e}", exc_info=True)
                citation["confidence"] = 0.0
                citation["fixed"] = False
                citation["error"] = str(e)
                validated_citations.append(citation)

        # Deduplicate: keep highest confidence for each (doc_id, page)
        deduped = {}
        for citation in validated_citations:
            key = (citation.get("doc_id"), citation.get("page"))
            if key not in deduped or citation.get("confidence", 0) > deduped[key].get(
                "confidence", 0
            ):
                deduped[key] = citation

        final_citations = list(deduped.values())

        # Sort by confidence descending
        final_citations.sort(key=lambda c: c.get("confidence", 0), reverse=True)

        logger.info(
            f"Citation validation complete: {len(citations)} raw -> "
            f"{len(final_citations)} validated/deduped"
        )

        return final_citations

    # =========================================================================
    # METRICS & OUTPUT
    # =========================================================================

    def compute_metrics(
        self, citations: List[Citation], latency_ms: float
    ) -> Dict[str, Any]:
        """
        Compute aggregate metrics for response.

        Metrics:
        - groundedness_est: median NLI score
        - coverage_est: fraction with confidence > threshold
        - latency_ms: total pipeline latency
        - steps: breakdown of config used

        Args:
            citations: Validated citations
            latency_ms: Total latency

        Returns:
            Metrics dict
        """
        if not citations:
            return {
                "groundedness_est": 0.0,
                "coverage_est": 0.0,
                "latency_ms": latency_ms,
                "steps": self.config.to_dict(),
            }

        # Estimate groundedness from citation confidences
        confidences = [c.get("confidence", 0.0) for c in citations]
        groundedness = sum(confidences) / len(confidences) if confidences else 0.0

        # Coverage: fraction with confidence > threshold
        coverage = sum(1 for c in confidences if c >= self.config.FUZZY_MIN) / len(
            confidences
        )

        return {
            "groundedness_est": round(groundedness, 3),
            "coverage_est": round(coverage, 3),
            "latency_ms": int(latency_ms),
            "steps": self.config.to_dict(),
        }

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================

    def answer(self, question: str) -> Dict[str, Any]:
        """
        Main entry point: Answer question with citations.

        Orchestrates Steps A-G:
        1. Normalize query
        2. Hybrid retrieval
        3. RRF merge
        4. Rerank
        5. Build context
        6. Call LLM
        7. Validate citations
        8. Compute metrics

        Args:
            question: User question

        Returns:
            Final output dict:
                answer: str
                citations: List[Citation]
                metrics: Dict
                language: str
                retrieval_info: Debug info about retrieval steps
        """
        logger.info(f"Processing question: {question[:100]}...")
        start_time = time.time()

        try:
            # Step A: Normalize query
            logger.info("Step A: Normalizing query...")
            normalized_query = self.normalize_query(question)

            # Step B: Hybrid retrieval
            logger.info("Step B: Hybrid retrieval...")
            bm25_hits, vec_hits = self.search_pages_hybrid(normalized_query)

            if not bm25_hits and not vec_hits:
                logger.warning("No results from retrieval")
                return self._empty_response(
                    question, "No relevant documents found.", time.time() - start_time
                )

            # Step C: RRF merge
            logger.info("Step C: RRF merge...")
            merged_hits = self.rrf_merge(bm25_hits, vec_hits)

            if not merged_hits:
                logger.warning("No results after merge")
                return self._empty_response(
                    question,
                    "No relevant documents after merging.",
                    time.time() - start_time,
                )

            # Step D: Cross-encoder rerank
            logger.info("Step D: Reranking...")
            reranked_hits = self.cross_encoder_rerank(normalized_query, merged_hits)

            if not reranked_hits:
                logger.warning("No results after reranking")
                return self._empty_response(
                    question,
                    "No relevant documents after reranking.",
                    time.time() - start_time,
                )

            # Step E: Build context
            logger.info("Step E: Building context...")
            context = self.build_page_context(reranked_hits)

            if not context:
                logger.warning("Empty context built")
                return self._empty_response(
                    question,
                    "Could not build context from documents.",
                    time.time() - start_time,
                )

            # Step F: Call LLM
            logger.info("Step F: Calling LLM...")
            llm_output = self.call_llm_structured(context, normalized_query)

            # Step G: Validate citations
            logger.info("Step G: Validating citations...")
            validated_citations = self.citefix_validate(
                llm_output.get("citations", []), normalized_query
            )

            # Compute metrics
            elapsed_ms = (time.time() - start_time) * 1000
            metrics = self.compute_metrics(validated_citations, elapsed_ms)

            # Build final response
            result = {
                "answer": llm_output.get("answer", ""),
                "citations": validated_citations,
                "language": llm_output.get("language", "en"),
                "metrics": metrics,
                "retrieval_info": {
                    "bm25_hits": len(bm25_hits),
                    "vector_hits": len(vec_hits),
                    "merged_hits": len(merged_hits),
                    "reranked_hits": len(reranked_hits),
                    "llm_usage": llm_output.get("usage", {}),
                },
            }

            logger.info(
                f"Question answered successfully: "
                f"{len(validated_citations)} citations, "
                f"{elapsed_ms:.0f}ms total"
            )

            return result

        except Exception as e:
            logger.error(f"Error answering question: {e}", exc_info=True)
            elapsed_ms = (time.time() - start_time) * 1000
            return {
                "answer": f"Error processing question: {str(e)}",
                "citations": [],
                "language": "en",
                "metrics": {
                    "groundedness_est": 0.0,
                    "coverage_est": 0.0,
                    "latency_ms": int(elapsed_ms),
                    "steps": self.config.to_dict(),
                },
                "retrieval_info": {},
                "error": str(e),
            }

    def _empty_response(
        self, question: str, message: str, elapsed: float
    ) -> Dict[str, Any]:
        """
        Generate empty response for cases with no results.

        Args:
            question: Original question
            message: Explanation message
            elapsed: Elapsed time in seconds

        Returns:
            Empty response dict
        """
        language = self._detect_language(question)
        return {
            "answer": message,
            "citations": [],
            "language": language,
            "metrics": {
                "groundedness_est": 0.0,
                "coverage_est": 0.0,
                "latency_ms": int(elapsed * 1000),
                "steps": self.config.to_dict(),
            },
            "retrieval_info": {
                "bm25_hits": 0,
                "vector_hits": 0,
                "merged_hits": 0,
                "reranked_hits": 0,
            },
        }


if __name__ == "__main__":
    # Smoke test
    print("=== PageFirstAgent Smoke Test ===")

    config = PageFirstConfig.from_env()
    config.validate()
    print(f"✓ Config loaded: {config}")

    agent = PageFirstAgent(config)
    print(f"✓ Agent initialized")

    # Test normalize_query (only implemented method in Phase 1)
    normalized = agent.normalize_query("What is the maximum pressure?")
    print(f"✓ Query normalized: '{normalized}'")

    print("\n✓ Phase 1 skeleton complete!")
    print("⚠ Full implementation (Steps A-G) will be added in Phase 2")
