"""
LRU caching for RAG pipeline.
"""
import hashlib
import json
import logging
import pickle
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache implementation."""

    def __init__(self, max_size: int = 512, ttl_seconds: int = 600):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds (default 10 minutes)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.hit_count = 0
        self.miss_count = 0

    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        # Create a stable key from args and kwargs
        key_data = {"args": args, "kwargs": kwargs}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        # Non-cryptographic hash suitable for caching keys
        return hashlib.blake2b(key_str.encode(), digest_size=16).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        # Check if key exists
        if key not in self.cache:
            self.miss_count += 1
            return None

        # Check TTL
        if time.time() - self.timestamps[key] > self.ttl_seconds:
            # Expired
            del self.cache[key]
            del self.timestamps[key]
            self.miss_count += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hit_count += 1

        return self.cache[key]

    def set(self, key: str, value: Any):
        """Set value in cache."""
        # Remove oldest if at capacity
        if key not in self.cache and len(self.cache) >= self.max_size:
            # Remove least recently used
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]

        # Add or update
        self.cache[key] = value
        self.timestamps[key] = time.time()

        # Move to end if updating
        if key in self.cache:
            self.cache.move_to_end(key)

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.timestamps.clear()
        self.hit_count = 0
        self.miss_count = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl_seconds,
        }


class CacheManager:
    """Manages multiple cache instances."""

    def __init__(self):
        self.caches: Dict[str, LRUCache] = {}

        # Initialize default caches
        self.caches["retrieval"] = LRUCache(max_size=512, ttl_seconds=600)
        self.caches["rerank"] = LRUCache(max_size=256, ttl_seconds=600)
        self.caches["transform"] = LRUCache(max_size=128, ttl_seconds=300)

    def get_cache(self, cache_name: str) -> Optional[LRUCache]:
        """Get a specific cache instance."""
        return self.caches.get(cache_name)

    def create_cache(
        self, cache_name: str, max_size: int = 512, ttl_seconds: int = 600
    ):
        """Create a new cache instance."""
        self.caches[cache_name] = LRUCache(max_size=max_size, ttl_seconds=ttl_seconds)

    def clear_all(self):
        """Clear all caches."""
        for cache in self.caches.values():
            cache.clear()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches."""
        return {name: cache.get_stats() for name, cache in self.caches.items()}


# Global cache manager
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(cache_name: str = "default", ttl_seconds: Optional[int] = None):
    """
    Decorator for caching function results.

    Args:
        cache_name: Name of the cache to use
        ttl_seconds: Optional TTL override
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get cache
            manager = get_cache_manager()
            cache = manager.get_cache(cache_name)

            if cache is None:
                # Create cache if doesn't exist
                manager.create_cache(cache_name, ttl_seconds=ttl_seconds or 600)
                cache = manager.get_cache(cache_name)

            # Generate key
            key = cache._make_key(*args, **kwargs)

            # Check cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return result

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            cache.set(key, result)
            logger.debug(f"Cached result for {func.__name__}")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get cache
            manager = get_cache_manager()
            cache = manager.get_cache(cache_name)

            if cache is None:
                # Create cache if doesn't exist
                manager.create_cache(cache_name, ttl_seconds=ttl_seconds or 600)
                cache = manager.get_cache(cache_name)

            # Generate key
            key = cache._make_key(*args, **kwargs)

            # Check cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return result

            # Call function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(key, result)
            logger.debug(f"Cached result for {func.__name__}")

            return result

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_cache(cache_name: str, key: Optional[str] = None):
    """
    Invalidate cache entries.

    Args:
        cache_name: Name of the cache
        key: Optional specific key to invalidate (invalidates all if None)
    """
    manager = get_cache_manager()
    cache = manager.get_cache(cache_name)

    if cache:
        if key:
            # Invalidate specific key
            if key in cache.cache:
                del cache.cache[key]
                del cache.timestamps[key]
        else:
            # Clear entire cache
            cache.clear()
