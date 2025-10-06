"""
Page-Level Reranker for Citation Accuracy (Phase 1)

This module provides intra-document page reranking to find the most relevant pages
within a document for a given query. Used to improve citation accuracy by identifying
the exact page that best answers the query.

Usage:
    reranker = PageReranker()
    pages = reranker.rank_pages_for_doc(
        query="maximum operating pressure",
        doc_id="DOCID_KT06101_datasheet_abc123",
        top_k=5
    )
    # Returns: [(page_num, score), ...]
"""

import hashlib
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonlines
import numpy as np
from loguru import logger
from rank_bm25 import BM25Okapi

# Import centralized config
try:
    from app.config import get_config

    _pipeline_config = get_config()
except ImportError:
    _pipeline_config = None
    logger.warning("Failed to import config, using fallback paths")

# Import shared text processing
try:
    from app.utils.text_processing import tokenize_for_bm25

    _tokenize_fn = tokenize_for_bm25
except ImportError:
    logger.warning("Text processing utils not available, using fallback tokenization")

    # Fallback tokenization
    def _tokenize_fn(text: str):
        return text.lower().split()


class LRUCache:
    """Simple LRU cache with TTL support"""

    def __init__(self, maxsize: int = 1024, ttl: int = 1800):
        """
        Initialize LRU cache

        Args:
            maxsize: Maximum number of entries
            ttl: Time to live in seconds (0 = no expiry)
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}  # key -> timestamp
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (None if not found or expired)"""
        if key not in self.cache:
            self.misses += 1
            return None

        # Check TTL
        if self.ttl > 0:
            age = time.time() - self.timestamps[key]
            if age > self.ttl:
                # Expired
                del self.cache[key]
                del self.timestamps[key]
                self.misses += 1
                return None

        # Move to end (mark as recently used)
        self.cache.move_to_end(key)
        self.hits += 1
        return self.cache[key]

    def put(self, key: str, value: Any):
        """Put value in cache"""
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
        else:
            # Add new
            self.cache[key] = value

            # Evict if over size
            if len(self.cache) > self.maxsize:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]

        self.cache[key] = value
        self.timestamps[key] = time.time()

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.timestamps.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        return {
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "ttl": self.ttl,
        }


class PageReranker:
    """
    Page-level reranker using BM25 and semantic similarity.

    Features:
    - BM25 lexical matching
    - Semantic similarity with embeddings (when available)
    - Hybrid scoring (BM25 + semantic)
    - LRU caching for page ranks and query embeddings
    - Performance metrics tracking
    """

    def __init__(
        self,
        page_index_path: Optional[str] = None,
        text_by_page_path: Optional[str] = None,
        page_metadata_path: Optional[str] = None,
    ):
        """
        Initialize PageReranker

        Args:
            page_index_path: Path to BM25 page index pickle (defaults from config)
            text_by_page_path: Path to text_by_page.jsonl (defaults from config)
            page_metadata_path: Path to page metadata JSON (defaults from config)
        """
        # Use config defaults if available
        if _pipeline_config:
            self.page_index_path = (
                Path(page_index_path)
                if page_index_path
                else _pipeline_config.page_bm25_index_path
            )
            self.text_by_page_path = (
                Path(text_by_page_path)
                if text_by_page_path
                else _pipeline_config.text_by_page_path
            )
            self.page_metadata_path = (
                Path(page_metadata_path)
                if page_metadata_path
                else _pipeline_config.page_metadata_path
            )
        else:
            # Fallback to hardcoded defaults
            self.page_index_path = (
                Path(page_index_path)
                if page_index_path
                else Path("artifacts/ingestion_production/page_bm25_index.pkl")
            )
            self.text_by_page_path = (
                Path(text_by_page_path)
                if text_by_page_path
                else Path("artifacts/ingestion_production/text_by_page.jsonl")
            )
            self.page_metadata_path = (
                Path(page_metadata_path)
                if page_metadata_path
                else Path("artifacts/ingestion_production/page_metadata.json")
            )

        # Lazy loading
        self._page_index = None
        self._page_lookup = None  # (doc_id, page) -> corpus_index
        self._page_texts = None  # For fallback search

        # Semantic embeddings (lazy)
        self._embeddings = None  # numpy array (N_pages, dim)
        self._emb_doc_ids = None  # list[str]
        self._emb_pages = None  # list[int]
        self._bm25_to_emb_idx = (
            None  # Optional[List[int]] mapping corpus_idx -> emb_idx if misaligned
        )

        # Caching
        self._rank_cache = None  # LRU cache for page rankings
        self._embed_cache = None  # LRU cache for query embeddings
        self._init_caches()

    def _load_index(self):
        """Load BM25 page index (lazy loading)"""
        if self._page_index is not None:
            return

        if not self.page_index_path.exists():
            logger.warning(f"Page index not found: {self.page_index_path}")
            logger.warning("PageReranker will use fallback mode without BM25")
            self._page_index = None
            return

        try:
            with open(self.page_index_path, "rb") as f:
                data = pickle.load(f)

            self._page_index = data["bm25"]

            # Build lookup: (doc_id, page) -> corpus_index
            self._page_lookup = {}
            doc_ids = data["doc_ids"]
            pages = data["pages"]

            for idx, (doc_id, page) in enumerate(zip(doc_ids, pages)):
                self._page_lookup[(doc_id, page)] = idx

            logger.info(f"Loaded page index with {len(doc_ids)} pages")

        except Exception as e:
            logger.error(f"Failed to load page index: {e}")
            self._page_index = None

    def _load_embeddings(self):
        """Lazy-load page embeddings from NPZ file if available"""
        if self._embeddings is not None:
            return

        if _pipeline_config is None:
            logger.debug("Config not available; embeddings loading skipped")
            return

        emb_path: Path = _pipeline_config.page_embeddings_path
        if not emb_path.exists():
            logger.info(f"Page embeddings file not found: {emb_path}")
            return

        try:
            data = np.load(str(emb_path), allow_pickle=True)
            self._embeddings = data["embeddings"]  # (N, D)
            self._emb_doc_ids = list(data["doc_ids"].tolist())
            self._emb_pages = list(data["pages"].tolist())

            # Build direct mapping from BM25 corpus idx -> embeddings idx if aligned
            if self._page_lookup is None:
                self._load_index()

            # Fast path: if lengths equal and first/last few entries match, assume alignment
            try:
                with open(_pipeline_config.page_bm25_index_path, "rb") as f:
                    bm25_data = pickle.load(f)
                bm25_doc_ids = bm25_data["doc_ids"]
                bm25_pages = bm25_data["pages"]

                if (
                    len(bm25_doc_ids) == len(self._emb_doc_ids)
                    and bm25_doc_ids[:5] == self._emb_doc_ids[:5]
                    and bm25_pages[:5] == self._emb_pages[:5]
                    and bm25_doc_ids[-5:] == self._emb_doc_ids[-5:]
                ):
                    # Assume same order
                    self._bm25_to_emb_idx = None  # direct index
                    logger.info(
                        f"Loaded embeddings: shape={self._embeddings.shape} (aligned with BM25 order)"
                    )
                else:
                    # Build mapping using (doc_id, page)
                    emb_lookup = {
                        (did, pg): idx
                        for idx, (did, pg) in enumerate(
                            zip(self._emb_doc_ids, self._emb_pages)
                        )
                    }
                    # Create array mapping corpus_idx -> emb_idx
                    self._bm25_to_emb_idx = []
                    for (did, pg), corpus_idx in self._page_lookup.items():
                        self._bm25_to_emb_idx.append(emb_lookup.get((did, pg), -1))
                    logger.info(
                        f"Loaded embeddings: shape={self._embeddings.shape} (built cross-index mapping)"
                    )
            except Exception as map_err:
                logger.warning(
                    f"Could not verify alignment; proceeding without mapping: {map_err}"
                )
                self._bm25_to_emb_idx = None

        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            self._embeddings = None

    def _init_caches(self):
        """Initialize LRU caches based on config"""
        if _pipeline_config:
            if _pipeline_config.ENABLE_PAGE_RANK_CACHE:
                self._rank_cache = LRUCache(
                    maxsize=_pipeline_config.PAGE_RANK_CACHE_SIZE,
                    ttl=_pipeline_config.PAGE_RANK_CACHE_TTL,
                )
                logger.info(
                    f"Page rank cache enabled: size={_pipeline_config.PAGE_RANK_CACHE_SIZE}, "
                    f"ttl={_pipeline_config.PAGE_RANK_CACHE_TTL}s"
                )

            if _pipeline_config.ENABLE_QUERY_EMBED_CACHE:
                self._embed_cache = LRUCache(
                    maxsize=_pipeline_config.QUERY_EMBED_CACHE_SIZE,
                    ttl=_pipeline_config.PAGE_RANK_CACHE_TTL,  # Same TTL as rank cache
                )
                logger.info(
                    f"Query embedding cache enabled: size={_pipeline_config.QUERY_EMBED_CACHE_SIZE}"
                )
        else:
            # Fallback: enable with default settings
            self._rank_cache = LRUCache(maxsize=1024, ttl=1800)
            self._embed_cache = LRUCache(maxsize=512, ttl=1800)
            logger.info(
                "Caches initialized with default settings (config not available)"
            )

    def _make_cache_key(
        self, query: str, doc_id: str, top_k: int, min_score: float, use_semantic: bool
    ) -> str:
        """Create cache key for page ranking results"""
        # Include semantic weights if using semantic
        if use_semantic and _pipeline_config:
            w_bm25 = _pipeline_config.PAGE_HYBRID_W_BM25
            w_sem = _pipeline_config.PAGE_HYBRID_W_SEM
            key_str = f"{query}|{doc_id}|{top_k}|{min_score}|sem|{w_bm25}|{w_sem}"
        else:
            key_str = f"{query}|{doc_id}|{top_k}|{min_score}|bm25"

        # Hash to keep key size manageable
        return hashlib.md5(key_str.encode()).hexdigest()

    def clear_caches(self):
        """Clear all caches (useful after index rebuild)"""
        if self._rank_cache:
            self._rank_cache.clear()
            logger.info("Page rank cache cleared")
        if self._embed_cache:
            self._embed_cache.clear()
            logger.info("Query embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {}

        if self._rank_cache:
            stats["rank_cache"] = self._rank_cache.stats()
        else:
            stats["rank_cache"] = {"enabled": False}

        if self._embed_cache:
            stats["embed_cache"] = self._embed_cache.stats()
        else:
            stats["embed_cache"] = {"enabled": False}

        return stats

    def _load_page_texts(self, doc_id: str) -> Dict[int, str]:
        """
        Load page texts for a specific document

        Args:
            doc_id: Document ID

        Returns:
            Dict mapping page_num -> text
        """
        page_texts = {}

        try:
            with jsonlines.open(self.text_by_page_path) as reader:
                for obj in reader:
                    if obj["doc_id"] == doc_id:
                        page_texts[obj["page"]] = obj["text"]
        except Exception as e:
            logger.error(f"Failed to load page texts: {e}")

        return page_texts

    def rank_pages_for_doc(
        self,
        query: str,
        doc_id: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Tuple[int, float]]:
        """
        Rank pages within a document for a given query (with caching)

        Args:
            query: Search query
            doc_id: Document ID to search within
            top_k: Number of top pages to return
            min_score: Minimum score threshold

        Returns:
            List of (page_num, score) tuples, sorted by score descending
        """
        start_time = time.time()

        # Lazy load index first
        self._load_index()

        if self._page_index is None:
            logger.warning("BM25 index not available, using fallback ranking")
            return self._fallback_rank(query, doc_id, top_k)

        # Lazy load embeddings to determine cache key
        if _pipeline_config and _pipeline_config.ENABLE_PAGE_SEMANTIC:
            self._load_embeddings()

        # Check cache first
        use_semantic = (
            _pipeline_config
            and _pipeline_config.ENABLE_PAGE_SEMANTIC
            and self._embeddings is not None
        )
        cache_key = self._make_cache_key(query, doc_id, top_k, min_score, use_semantic)

        if self._rank_cache:
            cached_result = self._rank_cache.get(cache_key)
            if cached_result is not None:
                cache_latency = (time.time() - start_time) * 1000
                logger.debug(
                    f"Cache HIT for query='{query[:30]}...', doc={doc_id}, "
                    f"latency={cache_latency:.2f}ms"
                )
                return cached_result

        # Tokenize query using shared function (same as indexing)
        query_tokens = _tokenize_fn(query)

        # Get all pages for this doc
        doc_pages = [
            (page, idx)
            for (did, page), idx in self._page_lookup.items()
            if did == doc_id
        ]

        if not doc_pages:
            logger.warning(f"No pages found for doc_id: {doc_id}")
            return []

        # Get BM25 scores for all corpus documents
        try:
            all_scores = self._page_index.get_scores(query_tokens)
        except Exception as e:
            logger.error(f"BM25 scoring failed: {e}")
            return self._fallback_rank(query, doc_id, top_k)

        # Filter BM25 scores for this document's pages
        bm25_page_scores = []
        bm25_values = []
        page_indices = []  # corresponding corpus indices
        for page_num, corpus_idx in doc_pages:
            score = float(all_scores[corpus_idx])
            if score >= min_score:
                bm25_page_scores.append((page_num, score))
                bm25_values.append(score)
                page_indices.append(corpus_idx)

        if not bm25_page_scores:
            return []

        # Attempt semantic scoring if enabled and embeddings available
        use_semantic_actual = False
        semantic_values = None
        hybrid_scores = None
        try:
            if _pipeline_config and _pipeline_config.ENABLE_PAGE_SEMANTIC:
                self._load_embeddings()
                if self._embeddings is not None:
                    # Try to get cached query embedding first
                    q_emb = None
                    if self._embed_cache:
                        q_emb = self._embed_cache.get(query)

                    if q_emb is None:
                        # Compute embedding
                        from app.services.embedding_enhanced import (
                            UniversalEmbeddingService,
                        )

                        # Use same model as embeddings were built with if possible
                        embed_model = (
                            "BAAI/bge-small-en-v1.5"  # default lightweight model
                        )
                        embed = UniversalEmbeddingService(
                            provider="local", model_name=embed_model
                        )
                        q_emb = embed.embed_query(query)

                        # Cache the embedding
                        if self._embed_cache:
                            self._embed_cache.put(query, q_emb)
                    # Ensure normalized (should already be)
                    if q_emb.ndim == 1:
                        q_emb = q_emb.reshape(1, -1)
                    # Compute cosine similarities for the doc's pages
                    semantic_values = []
                    for corpus_idx in page_indices:
                        emb_idx = corpus_idx
                        if self._bm25_to_emb_idx is not None:
                            # If mapping exists
                            try:
                                emb_mapped = self._bm25_to_emb_idx[corpus_idx]
                                if emb_mapped is not None and emb_mapped >= 0:
                                    emb_idx = emb_mapped
                                else:
                                    semantic_values.append(0.0)
                                    continue
                            except Exception:
                                semantic_values.append(0.0)
                                continue
                        page_vec = self._embeddings[emb_idx]
                        # dot product (vectors are normalized)
                        sim = float(np.dot(page_vec, q_emb[0]))
                        # map to [0,1]
                        sim = max(0.0, min(1.0, (sim + 1.0) / 2.0))
                        semantic_values.append(sim)
                    # Normalize both series to 0..1 (per-doc) to combine fairly
                    bm25_arr = np.array(bm25_values, dtype=np.float32)
                    sem_arr = np.array(semantic_values, dtype=np.float32)

                    def _minmax(x: np.ndarray) -> np.ndarray:
                        xmin = float(np.min(x))
                        xmax = float(np.max(x))
                        if xmax - xmin < 1e-8:
                            return np.full_like(x, 0.5)
                        return (x - xmin) / (xmax - xmin)

                    bm25_norm = _minmax(bm25_arr)
                    sem_norm = _minmax(sem_arr)
                    w_bm25 = getattr(_pipeline_config, "PAGE_HYBRID_W_BM25", 0.6)
                    w_sem = getattr(_pipeline_config, "PAGE_HYBRID_W_SEM", 0.4)
                    hybrid_vals = w_bm25 * bm25_norm + w_sem * sem_norm
                    # Build final list of (page, score)
                    hybrid_scores = [
                        (pg, float(hv))
                        for (pg, _), hv in zip(bm25_page_scores, hybrid_vals)
                    ]
                    use_semantic_actual = True
        except Exception as e:
            logger.warning(
                f"Semantic scoring unavailable, falling back to BM25 only: {e}"
            )
            use_semantic_actual = False

        # Determine final result
        if use_semantic_actual and hybrid_scores is not None:
            # Sort by hybrid score
            hybrid_scores.sort(key=lambda x: x[1], reverse=True)
            result = hybrid_scores[:top_k]
        else:
            # Default: BM25-only sort
            bm25_page_scores.sort(key=lambda x: x[1], reverse=True)
            result = bm25_page_scores[:top_k]

        # Cache the result
        if self._rank_cache:
            self._rank_cache.put(cache_key, result)

        # Log timing
        total_latency = (time.time() - start_time) * 1000
        logger.debug(
            f"Cache MISS for query='{query[:30]}...', doc={doc_id}, "
            f"semantic={use_semantic_actual}, latency={total_latency:.2f}ms"
        )

        return result

    def _fallback_rank(
        self,
        query: str,
        doc_id: str,
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """
        Fallback ranking using simple keyword matching

        This is a basic implementation for when BM25 index is not available.
        """
        page_texts = self._load_page_texts(doc_id)

        if not page_texts:
            return []

        # Simple keyword match scoring
        query_lower = query.lower()
        query_words = set(query_lower.split())

        page_scores = []
        for page_num, text in page_texts.items():
            text_lower = text.lower()

            # Count keyword matches
            matches = sum(1 for word in query_words if word in text_lower)

            # Simple score: match ratio
            if len(query_words) > 0:
                score = matches / len(query_words)
            else:
                score = 0.0

            if score > 0:
                page_scores.append((page_num, score))

        # Sort by score descending
        page_scores.sort(key=lambda x: x[1], reverse=True)

        return page_scores[:top_k]

    def get_page_text(self, doc_id: str, page: int) -> Optional[str]:
        """
        Get text for a specific page

        Args:
            doc_id: Document ID
            page: Page number (1-indexed)

        Returns:
            Page text or None if not found
        """
        try:
            with jsonlines.open(self.text_by_page_path) as reader:
                for obj in reader:
                    if obj["doc_id"] == doc_id and obj["page"] == page:
                        return obj["text"]
        except Exception as e:
            logger.error(f"Failed to get page text: {e}")

        return None

    def validate_page_exists(self, doc_id: str, page: int) -> bool:
        """
        Check if a page exists in the index

        Args:
            doc_id: Document ID
            page: Page number

        Returns:
            True if page exists
        """
        self._load_index()

        if self._page_lookup is None:
            # Fallback: check in text_by_page.jsonl
            try:
                with jsonlines.open(self.text_by_page_path) as reader:
                    for obj in reader:
                        if obj["doc_id"] == doc_id and obj["page"] == page:
                            return True
            except:
                pass
            return False

        return (doc_id, page) in self._page_lookup


# Singleton instance (lazy loading)
_page_reranker_instance = None


def get_page_reranker() -> PageReranker:
    """
    Get singleton PageReranker instance

    Returns:
        PageReranker instance
    """
    global _page_reranker_instance

    if _page_reranker_instance is None:
        _page_reranker_instance = PageReranker()

    return _page_reranker_instance
