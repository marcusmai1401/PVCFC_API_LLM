"""
Hybrid Retriever Module for RAG Pipeline
Combines BM25 (keyword) and FAISS (semantic) search with RRF fusion and parent expansion
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from loguru import logger

from app.rag.indexers.bm25_indexer import BM25Indexer
from app.rag.indexers.faiss_indexer import VectorIndexer
from app.rag.page_range_expander import PageRangeConfig, PageRangeExpander
from app.rag.query_transform import QueryFilters, TransformedQuery
from app.services.embedding_enhanced import EmbeddingService

# Import page utilities for consistent page handling
try:
    from app.utils.page_utils import extract_page_number, normalize_page_metadata
except ImportError:
    # Fallback if page_utils not available
    def extract_page_number(metadata: Dict[str, Any]) -> int:
        """Basic fallback for page extraction"""
        if isinstance(metadata, dict):
            return metadata.get("page", metadata.get("page_start", 1))
        return 1

    def normalize_page_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Basic fallback for metadata normalization"""
        if metadata is None:
            metadata = {}
        if "page" not in metadata:
            metadata["page"] = extract_page_number(metadata)
        return metadata


@dataclass
class RetrievalResult:
    """Single retrieval result with metadata"""

    chunk_id: str
    text: str
    score: float
    source: str  # "bm25" or "faiss"
    metadata: Dict[str, Any]
    doc_id: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[List[float]] = None
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata,
            "doc_id": self.doc_id,
            "page": self.page,
            "bbox": self.bbox,
            "parent_id": self.parent_id,
        }


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search"""

    k_bm25: int = 50  # Number of results from BM25
    k_faiss: int = 50  # Number of results from FAISS
    top_rrf: int = 60  # Number of results after RRF fusion
    rrf_k: int = 60  # RRF constant (usually 60)
    use_hyde: bool = True  # Whether to use HyDE queries
    expand_parent: bool = True  # Whether to expand to parent context
    parent_tokens: int = 1200  # Max tokens for parent expansion
    sentence_window: int = 2  # Sentences to include around hit
    # Page-range expansion config
    enable_page_range_expansion: bool = True  # Enable page-range expansion
    max_pages_to_scan: int = 5  # Maximum pages to include in expansion
    min_cluster_score: float = 0.1  # Minimum total score for a cluster
    page_gap_tolerance: int = 1  # Max gap between pages to consider consecutive


class HybridRetriever:
    """
    Hybrid retriever combining BM25 and FAISS search

    Features:
    - BM25 keyword search
    - FAISS semantic search
    - HyDE support for better recall
    - Reciprocal Rank Fusion (RRF)
    - Parent context expansion
    - Filter support
    """

    def __init__(
        self,
        bm25_index_dir: Optional[str] = None,
        faiss_index_dir: Optional[str] = None,
        config: Optional[HybridSearchConfig] = None,
    ):
        """
        Initialize HybridRetriever

        Args:
            bm25_index_dir: Directory containing BM25 index
            faiss_index_dir: Directory containing FAISS index
            config: Search configuration
        """
        self.config = config or HybridSearchConfig()

        # Initialize indices
        self.bm25_indexer = None
        self.faiss_indexer = None
        self.embedding_service = None

        # Load indices if provided
        if bm25_index_dir:
            self.load_bm25_index(bm25_index_dir)
        if faiss_index_dir:
            self.load_faiss_index(faiss_index_dir)

        # Cache for parent documents
        self.parent_cache = {}

        # Initialize page range expander
        self.page_expander = PageRangeExpander(
            PageRangeConfig(
                max_pages_to_scan=self.config.max_pages_to_scan,
                min_cluster_score=self.config.min_cluster_score,
                gap_tolerance=self.config.page_gap_tolerance,
                enable_expansion=self.config.enable_page_range_expansion,
            )
        )

        # Provide a chunk/page loader to expander so it can load full page content
        self._doc_id_map_cache = None  # Lazy-loaded mapping doc_id -> pdf_path
        self.page_expander.chunk_loader = self._load_page_content_impl

        logger.info(
            f"HybridRetriever initialized. BM25: {bm25_index_dir is not None}, "
            f"FAISS: {faiss_index_dir is not None}, "
            f"Page-range expansion: {self.config.enable_page_range_expansion}"
        )

    def load_bm25_index(self, index_dir: str):
        """Load BM25 index from directory"""
        try:
            self.bm25_indexer = BM25Indexer()
            self.bm25_indexer.load_index(index_dir)
            logger.info(
                f"Loaded BM25 index from {index_dir} with {len(self.bm25_indexer.documents)} documents"
            )
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            raise

    def load_faiss_index(self, index_dir: str):
        """Load FAISS index from directory"""
        try:
            self.faiss_indexer = VectorIndexer()
            self.faiss_indexer.load(index_dir)
            self.embedding_service = EmbeddingService()
            logger.info(
                f"Loaded FAISS index from {index_dir} with {len(self.faiss_indexer.documents)} documents"
            )
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            raise

    def search(
        self,
        transformed_query: TransformedQuery,
        config_override: Optional[HybridSearchConfig] = None,
    ) -> List[RetrievalResult]:
        """
        Perform hybrid search with the transformed query

        Args:
            transformed_query: Query after transformation (with intent, filters, HyDE)
            config_override: Optional config to override defaults

        Returns:
            List of retrieval results ranked by RRF
        """
        config = config_override or self.config

        logger.info(
            f"Starting hybrid search for: {transformed_query.normalized[:100]}..."
        )

        # Collect results from both sources
        all_results = []
        faiss_failed = False
        degrade_reason = None

        # Load degrade settings from config
        try:
            from app.core.config import settings

            allow_fallback = settings.retrieval_allow_bm25_only_fallback
            bm25_k_degrade = settings.bm25_k_when_degrade
        except Exception:
            # Fallback to defaults if settings not available
            allow_fallback = True
            bm25_k_degrade = 80

        # BM25 search (always attempt)
        if self.bm25_indexer:
            bm25_results = self._search_bm25(
                query=transformed_query.normalized,
                filters=transformed_query.filters,
                top_k=config.k_bm25,
            )
            all_results.extend(bm25_results)
            logger.info(f"BM25 returned {len(bm25_results)} results")

        # FAISS search (with degrade fallback)
        if self.faiss_indexer and self.embedding_service:
            try:
                faiss_results = self._search_faiss(
                    query=transformed_query.normalized,
                    hyde_queries=transformed_query.hyde_queries
                    if config.use_hyde
                    else None,
                    filters=transformed_query.filters,
                    top_k=config.k_faiss,
                )
                all_results.extend(faiss_results)
                logger.info(f"FAISS returned {len(faiss_results)} results")
            except Exception as e:
                faiss_failed = True
                degrade_reason = str(e)
                logger.error(f"FAISS search failed: {e}")

                if allow_fallback:
                    # Degrade mode: increase BM25 k to compensate
                    logger.warning(
                        f"Entering degrade mode: FAISS failed ({degrade_reason[:100]}), "
                        f"falling back to BM25-only with k={bm25_k_degrade}"
                    )

                    try:
                        # Re-fetch BM25 with higher k to compensate for missing FAISS
                        all_results = []  # Clear previous BM25 results
                        bm25_degrade_results = self._search_bm25(
                            query=transformed_query.normalized,
                            filters=transformed_query.filters,
                            top_k=bm25_k_degrade,
                        )
                        all_results.extend(bm25_degrade_results)
                        logger.info(
                            f"BM25 degrade mode returned {len(bm25_degrade_results)} results "
                            f"(k={bm25_k_degrade})"
                        )
                    except Exception as e2:
                        logger.error(f"BM25 fallback also failed: {e2}")
                        # If BM25 fallback also fails, propagate original error
                        raise RuntimeError(
                            f"Both FAISS and BM25 fallback failed: {e}, {e2}"
                        )
                else:
                    # Fallback not allowed, propagate FAISS error
                    logger.error("FAISS failed and fallback disabled")
                    raise

        # Apply RRF fusion
        fused_results = self._reciprocal_rank_fusion(
            all_results, k=config.rrf_k, top_n=config.top_rrf
        )

        logger.info(f"RRF fusion produced {len(fused_results)} results")

        # Attach degrade metadata if FAISS failed
        if faiss_failed:
            for result in fused_results:
                if result.metadata is None:
                    result.metadata = {}
                result.metadata["degrade_mode"] = True
                result.metadata["degrade_reason"] = degrade_reason
            logger.info("Degrade metadata attached to all results")

        # Apply page-range expansion if enabled (before parent expansion)
        if config.enable_page_range_expansion:
            fused_results = self.page_expander.expand_results(
                fused_results, max_results=config.top_rrf
            )
            logger.info("Page-range expansion completed")

            # Upgrade results to full page text where possible
            try:
                fused_results = self._upgrade_results_with_full_pages(fused_results)
            except Exception as e:
                logger.warning(f"Failed to upgrade results with full pages: {e}")

        # Expand parent context if enabled (now optional with page-range)
        elif config.expand_parent:
            fused_results = self._expand_parent_context(
                fused_results,
                max_tokens=config.parent_tokens,
                window_size=config.sentence_window,
            )
            logger.info("Parent context expansion completed")

        return fused_results

    def _search_bm25(
        self, query: str, filters: Optional[QueryFilters], top_k: int
    ) -> List[RetrievalResult]:
        """
        Search using BM25 index

        Args:
            query: Normalized query text
            filters: Optional filters to apply
            top_k: Number of results to return

        Returns:
            List of BM25 search results
        """
        if not self.bm25_indexer:
            return []

        # Perform BM25 search
        bm25_hits = self.bm25_indexer.search(query, top_k=top_k)

        # Convert to RetrievalResult
        results = []
        for hit in bm25_hits:
            # Apply filters if provided
            if filters and not self._passes_filters(hit.get("metadata", {}), filters):
                continue

            # Normalize metadata to ensure page field exists
            metadata = normalize_page_metadata(hit.get("metadata", {}))

            result = RetrievalResult(
                chunk_id=hit.get("chunk_id", f"bm25_{len(results)}"),
                text=hit["text"],
                score=hit["score"],
                source="bm25",
                metadata=metadata,
                doc_id=metadata.get("doc_id"),
                page=metadata.get("page"),  # Now guaranteed to exist
                bbox=metadata.get("bbox"),
                parent_id=metadata.get("parent_id"),
            )
            results.append(result)

        return results

    def _search_faiss(
        self,
        query: str,
        hyde_queries: Optional[List[str]],
        filters: Optional[QueryFilters],
        top_k: int,
    ) -> List[RetrievalResult]:
        """
        Search using FAISS index

        Args:
            query: Normalized query text
            hyde_queries: Optional HyDE generated queries
            filters: Optional filters to apply
            top_k: Number of results to return

        Returns:
            List of FAISS search results
        """
        if not self.faiss_indexer or not self.embedding_service:
            return []

        # Prepare queries for embedding
        all_queries = [query]
        if hyde_queries:
            all_queries.extend(hyde_queries[:2])  # Use max 2 HyDE queries

        # Embed all queries
        try:
            if len(all_queries) == 1:
                # Use embed_query for single query (optimized for retrieval)
                if hasattr(self.embedding_service, "embed_query"):
                    query_embeddings = self.embedding_service.embed_query(
                        all_queries[0]
                    )
                    query_embeddings = query_embeddings.reshape(1, -1)
                else:
                    query_embeddings = self.embedding_service.embed_text(all_queries[0])
                    query_embeddings = query_embeddings.reshape(1, -1)
            else:
                # For multiple queries (including HyDE), use embed_texts
                # First query should ideally use embed_query, but batch is more efficient
                query_embeddings = self.embedding_service.embed_texts(all_queries)
        except Exception as e:
            logger.error(f"Failed to embed queries: {e}")
            return []

        # Search with each embedding
        all_hits = []
        for i, embedding in enumerate(query_embeddings):
            embedding = embedding.reshape(1, -1)
            hits = self.faiss_indexer.search(embedding, top_k=top_k)

            # Weight HyDE results slightly lower
            weight = 0.8 if i > 0 else 1.0

            for hit_list in hits:
                for idx, score in hit_list:
                    all_hits.append((idx, score * weight))

        # Deduplicate and sort by score
        hit_dict = {}
        for idx, score in all_hits:
            if idx not in hit_dict or score > hit_dict[idx]:
                hit_dict[idx] = score

        # Sort by score and take top_k
        sorted_hits = sorted(hit_dict.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Convert to RetrievalResult
        results = []
        for idx, score in sorted_hits:
            if idx >= len(self.faiss_indexer.documents):
                continue

            doc = self.faiss_indexer.documents[idx]

            # Apply filters if provided
            if filters and not self._passes_filters(doc.metadata, filters):
                continue

            # Normalize metadata to ensure page field exists
            metadata = normalize_page_metadata(doc.metadata)

            result = RetrievalResult(
                chunk_id=metadata.get("chunk_id", f"faiss_{idx}"),
                text=doc.text,
                score=float(score),
                source="faiss",
                metadata=metadata,
                doc_id=metadata.get("doc_id"),
                page=metadata.get("page"),  # Now guaranteed to exist
                bbox=metadata.get("bbox"),
                parent_id=metadata.get("parent_id"),
            )
            results.append(result)

        return results

    def _load_page_content_impl(
        self, doc_id: str, page: int, score: float
    ) -> Optional[RetrievalResult]:
        """Load full text for a given document page and wrap as RetrievalResult"""
        try:
            pdf_path = self._get_pdf_path_for_doc(doc_id)
            if not pdf_path:
                return None
            # Lazy import to avoid overhead on module import
            import re
            from pathlib import Path

            import fitz  # PyMuPDF

            p = Path(pdf_path)
            if not p.exists():
                return None

            doc = fitz.open(str(p))
            if page < 1 or page > len(doc):
                doc.close()
                return None
            page_obj = doc[page - 1]
            raw_text = page_obj.get_text()
            doc.close()

            # Clean text
            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
            text = re.sub(r"\s+", " ", "\n".join(lines)).strip()
            if not text:
                return None

            metadata = {
                "doc_id": doc_id,
                "page": page,
                "pdf_path": str(p),
                "full_page": True,
            }
            return RetrievalResult(
                chunk_id=f"page_{doc_id}_{page}",
                text=text,
                score=float(score),
                source="page_expanded",
                metadata=metadata,
                doc_id=doc_id,
                page=page,
                bbox=None,
                parent_id=None,
            )
        except Exception as e:
            logger.debug(f"_load_page_content_impl error for {doc_id} p{page}: {e}")
            return None

    def _get_pdf_path_for_doc(self, doc_id: str) -> Optional[str]:
        """Resolve PDF file path from doc_id via artifacts/ingestion/doc_id_map.json (cached)"""
        if self._doc_id_map_cache is None:
            try:
                import json
                from pathlib import Path

                path = Path("artifacts/ingestion/doc_id_map.json")
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        self._doc_id_map_cache = json.load(f)
                else:
                    self._doc_id_map_cache = {}
            except Exception:
                self._doc_id_map_cache = {}
        return self._doc_id_map_cache.get(doc_id)

    def _upgrade_results_with_full_pages(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Replace result.text with full page text where available for top unique pages.
        Limits number of pages to scan to avoid excessive cost.
        """
        if not results:
            return results

        upgraded = []
        seen = set()
        # Limit to at most 2x configured max_pages_to_scan pages
        max_pages = max(1, self.config.max_pages_to_scan * 2)
        count = 0

        for r in results:
            key = (r.doc_id, r.page)
            if r.doc_id and r.page and key not in seen and count < max_pages:
                full = self._load_page_content_impl(r.doc_id, r.page, r.score)
                if full and len(full.text) > max(len(r.text), 200):
                    # Replace contents but keep original score/source boosted slightly
                    r.text = full.text
                    r.source = f"{r.source}+page_full"
                    if r.metadata is None:
                        r.metadata = {}
                    r.metadata.update(
                        {"pdf_path": full.metadata.get("pdf_path"), "full_page": True}
                    )
                seen.add(key)
                count += 1
            upgraded.append(r)

        return upgraded

    def _reciprocal_rank_fusion(
        self, results: List[RetrievalResult], k: int = 60, top_n: int = 60
    ) -> List[RetrievalResult]:
        """
        Apply Reciprocal Rank Fusion to merge results

        RRF formula: RRF(d) = Σ 1/(k + rank(d))

        Args:
            results: All results from different sources
            k: RRF constant (typically 60)
            top_n: Number of results to return

        Returns:
            Fused and reranked results
        """
        # Group results by source
        source_rankings = defaultdict(list)
        for result in results:
            source_rankings[result.source].append(result)

        # Calculate RRF scores
        rrf_scores = defaultdict(float)
        result_map = {}

        for source, source_results in source_rankings.items():
            # Sort by original score
            source_results.sort(key=lambda x: x.score, reverse=True)

            # Calculate RRF contribution
            for rank, result in enumerate(source_results, 1):
                # Use text as key for deduplication
                key = result.text[:200]  # Use first 200 chars as key
                rrf_scores[key] += 1 / (k + rank)

                # Keep the result with higher original score
                if key not in result_map or result.score > result_map[key].score:
                    result_map[key] = result

        # Sort by RRF score
        sorted_keys = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Return top N results with updated scores
        fused_results = []
        for key, rrf_score in sorted_keys[:top_n]:
            result = result_map[key]
            # Update score to RRF score
            result.score = rrf_score
            fused_results.append(result)

        return fused_results

    def _expand_parent_context(
        self,
        results: List[RetrievalResult],
        max_tokens: int = 1200,
        window_size: int = 2,
    ) -> List[RetrievalResult]:
        """
        Expand results to include parent/surrounding context

        Args:
            results: Original retrieval results
            max_tokens: Maximum tokens for expanded context
            window_size: Number of sentences/chunks to include around hit

        Returns:
            Results with expanded context
        """
        expanded_results = []

        for result in results:
            # Check if we have parent information
            if result.parent_id and result.parent_id in self.parent_cache:
                # Use cached parent
                parent_text = self.parent_cache[result.parent_id]
                result.text = self._extract_window(
                    parent_text, result.text, window_size
                )
            elif result.metadata.get("parent_text"):
                # Use parent text from metadata
                parent_text = result.metadata["parent_text"]
                result.text = self._extract_window(
                    parent_text, result.text, window_size
                )
            else:
                # Try to expand using surrounding chunks
                result.text = self._expand_with_neighbors(result, window_size)

            # Truncate if too long
            result.text = self._truncate_text(result.text, max_tokens)
            expanded_results.append(result)

        return expanded_results

    def _extract_window(
        self, parent_text: str, chunk_text: str, window_size: int
    ) -> str:
        """Extract a window of text around the chunk from parent"""
        # Find chunk in parent
        chunk_start = parent_text.find(chunk_text[:50])  # Use first 50 chars to find
        if chunk_start == -1:
            return chunk_text

        # Find sentence boundaries
        sentences = parent_text.split(". ")
        chunk_sentence_idx = None

        current_pos = 0
        for i, sentence in enumerate(sentences):
            if current_pos <= chunk_start < current_pos + len(sentence):
                chunk_sentence_idx = i
                break
            current_pos += len(sentence) + 2  # +2 for '. '

        if chunk_sentence_idx is None:
            return chunk_text

        # Extract window
        start_idx = max(0, chunk_sentence_idx - window_size)
        end_idx = min(len(sentences), chunk_sentence_idx + window_size + 1)

        window_sentences = sentences[start_idx:end_idx]
        return ". ".join(window_sentences) + ("." if window_sentences else "")

    def _expand_with_neighbors(self, result: RetrievalResult, window_size: int) -> str:
        """Expand using neighboring chunks (placeholder for now)"""
        # This would query for neighboring chunks based on chunk_id
        # For now, just return original text
        return result.text

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to maximum token count"""
        # Simple word-based truncation (rough approximation)
        # In production, use proper tokenizer
        words = text.split()
        estimated_tokens = len(words) * 1.3  # Rough estimate

        if estimated_tokens <= max_tokens:
            return text

        # Truncate to fit
        target_words = int(max_tokens / 1.3)
        truncated = " ".join(words[:target_words])
        return truncated + "..."

    def _passes_filters(self, metadata: Dict[str, Any], filters: QueryFilters) -> bool:
        """Check if metadata passes the filters"""
        # Check doc_categories
        if filters.doc_categories:
            doc_category = metadata.get("doc_category") or metadata.get("doc_type")
            if not doc_category or doc_category not in filters.doc_categories:
                return False

        # Check doc_ids
        if filters.doc_ids:
            doc_id = metadata.get("doc_id")
            if not doc_id or doc_id not in filters.doc_ids:
                return False

        # Check additional metadata filters
        if filters.metadata:
            for key, value in filters.metadata.items():
                if metadata.get(key) != value:
                    return False

        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded indices"""
        stats = {
            "bm25_documents": len(self.bm25_indexer.documents)
            if self.bm25_indexer
            else 0,
            "faiss_documents": len(self.faiss_indexer.documents)
            if self.faiss_indexer
            else 0,
            "config": {
                "k_bm25": self.config.k_bm25,
                "k_faiss": self.config.k_faiss,
                "top_rrf": self.config.top_rrf,
                "use_hyde": self.config.use_hyde,
                "expand_parent": self.config.expand_parent,
            },
        }
        return stats


# Convenience function
def create_hybrid_retriever(
    bm25_dir: str = "artifacts/index/bm25",
    faiss_dir: str = "artifacts/index/faiss",
    config: Optional[HybridSearchConfig] = None,
) -> HybridRetriever:
    """
    Create a hybrid retriever with default settings

    Args:
        bm25_dir: BM25 index directory
        faiss_dir: FAISS index directory
        config: Optional configuration

    Returns:
        Configured HybridRetriever instance
    """
    # If no config provided, create one with settings from environment
    if config is None:
        try:
            from app.core.config import settings

            # Create config that respects ENV settings
            config = HybridSearchConfig(
                enable_page_range_expansion=settings.text_range_scan_enabled
            )
        except Exception:
            # Fallback to default config if settings not available
            config = HybridSearchConfig()

    retriever = HybridRetriever(
        bm25_index_dir=bm25_dir, faiss_index_dir=faiss_dir, config=config
    )
    return retriever
