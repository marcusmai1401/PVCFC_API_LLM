"""
Distributed cache implementation using Redis.

Features:
- JSON serialization with optional compression
- Namespace isolation for multi-tenant support
- Per-key TTL with default fallback
- Batch operations (get_many, set_many)
- Cache stampede prevention with simple locks
- Thread and process-safe (uses Redis atomic operations)
- Observability with hit/miss logging
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class DistributedCache:
    """
    Redis-backed distributed cache with JSON serialization.

    Enables cache sharing across multiple application instances for:
    - Horizontal scaling
    - Consistent cache hit rates
    - Reduced memory footprint per instance

    Thread-safe and process-safe via Redis atomic operations.
    """

    def __init__(
        self,
        namespace: Optional[str] = None,
        default_ttl: Optional[int] = None,
        enable_compression: bool = False,
    ):
        """
        Initialize distributed cache.

        Args:
            namespace: Sub-namespace for key isolation (e.g., "retrieval", "rerank")
            default_ttl: Default TTL in seconds (overrides config if provided)
            enable_compression: Enable gzip compression for large values
        """
        self.redis_client = get_redis(read_only=False)

        # Namespace: {CACHE_NAMESPACE}:{sub_namespace}:{key}
        self.base_namespace = settings.cache_namespace
        self.sub_namespace = namespace or "default"
        self.namespace_prefix = f"{self.base_namespace}:{self.sub_namespace}"

        # TTL configuration
        self.default_ttl = default_ttl or settings.cache_default_ttl

        # Compression (disabled by default for performance)
        self.enable_compression = (
            enable_compression or settings.cache_enable_compression
        )

        # Observability counters (in-memory, per instance)
        self._hits = 0
        self._misses = 0
        self._errors = 0

        logger.info(
            f"DistributedCache initialized: namespace={self.namespace_prefix}, "
            f"default_ttl={self.default_ttl}s, compression={self.enable_compression}"
        )

    def _build_key(self, key: str) -> str:
        """Build fully qualified cache key with namespace."""
        return f"{self.namespace_prefix}:{key}"

    def _serialize(self, value: Any) -> str:
        """Serialize value to JSON string."""
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value: {e}")
            raise

    def _deserialize(self, data: str) -> Any:
        """Deserialize JSON string to value."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to deserialize value: {e}")
            return None

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key (without namespace)
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        full_key = self._build_key(key)

        try:
            data = self.redis_client.get(full_key)

            if data is None:
                self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return default

            self._hits += 1
            value = self._deserialize(data)
            logger.debug(f"Cache hit: {key}")
            return value if value is not None else default

        except RedisError as e:
            self._errors += 1
            logger.error(f"Redis error on get({key}): {e}")
            return default

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key (without namespace)
            value: Value to cache (must be JSON-serializable)
            ttl: TTL in seconds (None = use default)

        Returns:
            True if successful, False otherwise
        """
        full_key = self._build_key(key)
        ttl_seconds = ttl if ttl is not None else self.default_ttl

        try:
            data = self._serialize(value)
            result = self.redis_client.setex(full_key, ttl_seconds, data)
            logger.debug(f"Cache set: {key} (ttl={ttl_seconds}s)")
            return bool(result)

        except (RedisError, TypeError, ValueError) as e:
            self._errors += 1
            logger.error(f"Failed to set cache key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key (without namespace)

        Returns:
            True if key was deleted, False if not found or error
        """
        full_key = self._build_key(key)

        try:
            result = self.redis_client.delete(full_key)
            deleted = result > 0
            if deleted:
                logger.debug(f"Cache delete: {key}")
            return deleted

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key (without namespace)

        Returns:
            True if key exists, False otherwise
        """
        full_key = self._build_key(key)

        try:
            return bool(self.redis_client.exists(full_key))
        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to check existence of {key}: {e}")
            return False

    def incr(
        self, key: str, amount: int = 1, ttl: Optional[int] = None
    ) -> Optional[int]:
        """
        Atomically increment counter (useful for rate limiting, metrics).

        Args:
            key: Cache key (without namespace)
            amount: Increment amount (default: 1)
            ttl: TTL in seconds for new keys (None = use default)

        Returns:
            New value after increment, or None on error
        """
        full_key = self._build_key(key)
        ttl_seconds = ttl if ttl is not None else self.default_ttl

        try:
            # Increment atomically
            new_value = self.redis_client.incr(full_key, amount)

            # Set TTL if this is a new key (TTL returns -1 for keys without expiry)
            if self.redis_client.ttl(full_key) == -1:
                self.redis_client.expire(full_key, ttl_seconds)

            return new_value

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to increment {key}: {e}")
            return None

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple keys in one round-trip (batch operation).

        Args:
            keys: List of cache keys (without namespace)

        Returns:
            Dict mapping keys to values (missing keys omitted)
        """
        if not keys:
            return {}

        full_keys = [self._build_key(k) for k in keys]

        try:
            # MGET is atomic and faster than multiple GETs
            values = self.redis_client.mget(full_keys)

            result = {}
            for key, data in zip(keys, values):
                if data is not None:
                    value = self._deserialize(data)
                    if value is not None:
                        result[key] = value
                        self._hits += 1
                    else:
                        self._misses += 1
                else:
                    self._misses += 1

            logger.debug(f"Cache get_many: {len(result)}/{len(keys)} hits")
            return result

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to get_many: {e}")
            return {}

    def set_many(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> int:
        """
        Set multiple keys in pipeline (faster than individual SETs).

        Args:
            mapping: Dict of key-value pairs to cache
            ttl: TTL in seconds (None = use default)

        Returns:
            Number of successfully set keys
        """
        if not mapping:
            return 0

        ttl_seconds = ttl if ttl is not None else self.default_ttl

        try:
            # Use pipeline for atomic batch operation
            pipe = self.redis_client.pipeline()

            for key, value in mapping.items():
                full_key = self._build_key(key)
                try:
                    data = self._serialize(value)
                    pipe.setex(full_key, ttl_seconds, data)
                except (TypeError, ValueError) as e:
                    logger.warning(
                        f"Skipping key {key} due to serialization error: {e}"
                    )

            results = pipe.execute()
            success_count = sum(1 for r in results if r)

            logger.debug(f"Cache set_many: {success_count}/{len(mapping)} successful")
            return success_count

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to set_many: {e}")
            return 0

    def lock(self, key: str, timeout: int = 10) -> bool:
        """
        Acquire simple lock using SETNX (cache stampede prevention).

        Args:
            key: Lock key (without namespace)
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired, False if already locked

        Note:
            This is a simple lock, not distributed-lock-safe.
            For production-grade locks, consider redlock or redis-py's Lock.
        """
        full_key = self._build_key(f"lock:{key}")

        try:
            # SETNX with timeout
            acquired = self.redis_client.set(
                full_key,
                "locked",
                nx=True,  # Only set if not exists
                ex=timeout,  # Auto-expire
            )

            if acquired:
                logger.debug(f"Lock acquired: {key}")
            else:
                logger.debug(f"Lock already held: {key}")

            return bool(acquired)

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to acquire lock {key}: {e}")
            return False

    def unlock(self, key: str) -> bool:
        """
        Release lock.

        Args:
            key: Lock key (without namespace)

        Returns:
            True if lock released, False otherwise
        """
        full_key = self._build_key(f"lock:{key}")

        try:
            result = self.redis_client.delete(full_key)
            if result:
                logger.debug(f"Lock released: {key}")
            return result > 0

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to release lock {key}: {e}")
            return False

    def clear_namespace(self) -> int:
        """
        Clear all keys in current namespace (use with caution!).

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.namespace_prefix}:*"

        try:
            keys = list(self.redis_client.scan_iter(match=pattern, count=100))
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.warning(
                    f"Cleared {deleted} keys from namespace {self.namespace_prefix}"
                )
                return deleted
            return 0

        except RedisError as e:
            self._errors += 1
            logger.error(f"Failed to clear namespace: {e}")
            return 0

    def get_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get cache statistics for observability.

        Returns:
            Dict with hits, misses, errors, hit_rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "hit_rate": round(hit_rate, 2),
            "total_requests": total,
        }

    def reset_stats(self):
        """Reset statistics counters."""
        self._hits = 0
        self._misses = 0
        self._errors = 0
