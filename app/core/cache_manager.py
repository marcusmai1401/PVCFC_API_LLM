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


# ==========================================
# Week 1: Distributed Cache Factory
# ==========================================

from typing import Protocol, Dict, Any
from app.core.config import settings


class CacheBackend(Protocol):
    """
    Protocol for unified cache interface.
    
    Both DistributedCache (Redis) and TTLCache wrappers implement this.
    """
    
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def get_many(self, keys: List[str]) -> Dict[str, Any]: ...
    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> int: ...
    def get_stats(self) -> Dict[str, Any]: ...


class TTLCacheWrapper:
    """
    Wrapper for legacy TTLCache to match CacheBackend protocol.
    Provides backward compatibility with existing in-memory cache.
    """
    
    def __init__(self, namespace: Optional[str] = None, default_ttl: int = 3600):
        self.namespace = namespace or "default"
        self.default_ttl = default_ttl
        self._cache = TTLCache(maxsize=1000, ttl=default_ttl)
        self._hits = 0
        self._misses = 0
        logger.info(f"TTLCacheWrapper: namespace={self.namespace}, ttl={default_ttl}s")
    
    def _build_key(self, key: str) -> str:
        return f"{self.namespace}:{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        full_key = self._build_key(key)
        value = self._cache.get(full_key, default)
        if value is not default:
            self._hits += 1
        else:
            self._misses += 1
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        full_key = self._build_key(key)
        try:
            self._cache[full_key] = value
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        full_key = self._build_key(key)
        if full_key in self._cache:
            del self._cache[full_key]
            return True
        return False
    
    def exists(self, key: str) -> bool:
        return self._build_key(key) in self._cache
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> int:
        count = 0
        for key, value in mapping.items():
            if self.set(key, value, ttl):
                count += 1
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "backend": "ttl_cache",
            "namespace": self.namespace,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "size": len(self._cache),
        }


class CacheFactory:
    """
    Cache factory with feature flag support.
    
    Returns:
    - DistributedCache (Redis) if USE_DISTRIBUTED_CACHE=true
    - TTLCacheWrapper (memory) if USE_DISTRIBUTED_CACHE=false
    """
    
    _instances: Dict[str, CacheBackend] = {}
    
    @classmethod
    def get_cache(
        cls,
        namespace: Optional[str] = None,
        default_ttl: Optional[int] = None,
    ) -> CacheBackend:
        """
        Get cache backend for namespace.
        
        Args:
            namespace: Cache namespace (e.g., "retrieval", "rerank")
            default_ttl: Default TTL (None = use config)
        
        Returns:
            CacheBackend (DistributedCache or TTLCacheWrapper)
        """
        namespace = namespace or "default"
        
        if namespace in cls._instances:
            return cls._instances[namespace]
        
        use_distributed = settings.use_distributed_cache
        
        if use_distributed:
            from app.core.distributed_cache import DistributedCache
            cache = DistributedCache(
                namespace=namespace,
                default_ttl=default_ttl or settings.cache_default_ttl,
                enable_compression=settings.cache_enable_compression,
            )
            logger.info(f"Using DistributedCache: {namespace}")
        else:
            cache = TTLCacheWrapper(
                namespace=namespace,
                default_ttl=default_ttl or settings.cache_default_ttl,
            )
            logger.info(f"Using TTLCache (memory): {namespace}")
        
        cls._instances[namespace] = cache
        return cache
    
    @classmethod
    def clear_all(cls):
        """Clear all cached instances."""
        cls._instances.clear()


def get_cache(
    namespace: Optional[str] = None,
    default_ttl: Optional[int] = None,
) -> CacheBackend:
    """
    Convenience function to get cache backend.
    
    Example:
        >>> cache = get_cache(namespace="retrieval")
        >>> cache.set("query:123", results, ttl=600)
        >>> cached = cache.get("query:123")
    """
    return CacheFactory.get_cache(namespace=namespace, default_ttl=default_ttl)
