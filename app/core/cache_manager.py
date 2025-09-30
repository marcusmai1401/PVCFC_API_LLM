"""
Cache manager for retrieval and rerank results
Provides LRU cache with TTL to reduce latency for duplicate queries
"""
import hashlib
import json
from typing import Any, List, Optional

from cachetools import TTLCache
from loguru import logger


class RetrievalCache:
    """LRU cache with TTL for retrieval results"""

    def __init__(self, maxsize: int = 1000, ttl: int = 600):
        """
        Initialize cache

        Args:
            maxsize: Maximum number of cache entries
            ttl: Time-to-live in seconds (default 10 minutes)
        """
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.ttl = ttl
        logger.info(f"RetrievalCache initialized: maxsize={maxsize}, ttl={ttl}s")

    def _make_key(self, query: str, filters: Optional[dict] = None, k: int = 8) -> str:
        """
        Generate cache key from query + filters + k

        Args:
            query: Query string (normalized)
            filters: Optional filters dict
            k: Number of results

        Returns:
            Hashed cache key (16 chars)
        """
        # Normalize query for consistent caching
        normalized_query = query.strip().lower()

        # Build cache key dict
        key_dict = {
            "query": normalized_query,
            "filters": filters or {},
            "k": k,
        }

        # Serialize and hash
        key_str = json.dumps(key_dict, sort_keys=True)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]

        return key_hash

    def get(
        self, query: str, filters: Optional[dict] = None, k: int = 8
    ) -> Optional[Any]:
        """
        Get cached results

        Args:
            query: Query string
            filters: Optional filters
            k: Number of results

        Returns:
            Cached results or None if not found/expired
        """
        key = self._make_key(query, filters, k)
        result = self.cache.get(key)

        if result is not None:
            logger.debug(f"Cache HIT for key={key}")
        else:
            logger.debug(f"Cache MISS for key={key}")

        return result

    def set(
        self,
        query: str,
        results: Any,
        filters: Optional[dict] = None,
        k: int = 8,
    ):
        """
        Set cache results

        Args:
            query: Query string
            results: Results to cache (typically List[RetrievalResult])
            filters: Optional filters
            k: Number of results
        """
        key = self._make_key(query, filters, k)
        self.cache[key] = results
        logger.debug(
            f"Cache SET for key={key}, size={len(self.cache)}/{self.cache.maxsize}"
        )

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "maxsize": self.cache.maxsize,
            "ttl_seconds": self.ttl,
        }


# Global cache instance (lazy initialization)
_retrieval_cache: Optional[RetrievalCache] = None


def get_retrieval_cache() -> RetrievalCache:
    """
    Get or create global retrieval cache singleton

    Returns:
        RetrievalCache instance
    """
    global _retrieval_cache

    if _retrieval_cache is None:
        try:
            from app.core.config import settings

            ttl_seconds = settings.retrieve_cache_ttl_min * 60
        except Exception:
            # Fallback to default if settings not available
            ttl_seconds = 600  # 10 minutes

        _retrieval_cache = RetrievalCache(maxsize=1000, ttl=ttl_seconds)
        logger.info(f"Global RetrievalCache created: maxsize=1000, ttl={ttl_seconds}s")

    return _retrieval_cache


def clear_cache():
    """Clear the global cache (useful for testing/debugging)"""
    global _retrieval_cache
    if _retrieval_cache:
        _retrieval_cache.clear()
