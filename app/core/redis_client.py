"""
Redis client factory with Sentinel support for high availability.

Features:
- Automatic failover with Redis Sentinel
- Connection pooling for optimal performance
- Support for both single and sentinel modes
- Health check and graceful shutdown
- Read/write split with master/replica connections
"""

import logging
from typing import Optional

import redis
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.sentinel import Sentinel

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClientFactory:
    """
    Redis client factory managing connections with Sentinel support.

    Modes:
    - single: Direct connection to a standalone Redis instance
    - sentinel: HA cluster with automatic failover via Sentinel
    """

    def __init__(self):
        self._sentinel: Optional[Sentinel] = None
        self._master_pool: Optional[ConnectionPool] = None
        self._replica_pool: Optional[ConnectionPool] = None
        self._redis_master: Optional[redis.Redis] = None
        self._redis_replica: Optional[redis.Redis] = None
        self._mode: str = settings.redis_mode
        self._initialized: bool = False

    def initialize(self) -> None:
        """
        Initialize Redis connections based on configuration.
        Must be called during application startup.
        """
        if self._initialized:
            logger.warning("Redis client already initialized")
            return

        try:
            if self._mode == "sentinel":
                self._init_sentinel()
            else:
                self._init_single()

            # Verify connection with ping
            self.ping()
            self._initialized = True

            logger.info(
                f"Redis client initialized successfully in {self._mode} mode",
                extra={"redis_mode": self._mode},
            )

        except Exception as e:
            logger.error(
                f"Failed to initialize Redis client: {e}",
                exc_info=True,
                extra={"redis_mode": self._mode},
            )
            raise

    def _init_sentinel(self) -> None:
        """Initialize Redis Sentinel cluster connection."""
        if not settings.redis_sentinels:
            raise ValueError("REDIS_SENTINELS must be configured for sentinel mode")

        # Parse sentinel addresses (already validated by config)
        sentinel_list = settings.redis_sentinels

        # Create Sentinel instance
        self._sentinel = Sentinel(
            sentinels=sentinel_list,
            sentinel_kwargs={
                "password": settings.redis_password,
                "socket_connect_timeout": settings.redis_socket_connect_timeout_ms
                / 1000.0,
                "socket_timeout": settings.redis_socket_timeout_ms / 1000.0,
            },
            # Connection pool settings for discovered master/replica
            password=settings.redis_password,
            db=settings.redis_db,
            socket_connect_timeout=settings.redis_socket_connect_timeout_ms / 1000.0,
            socket_timeout=settings.redis_socket_timeout_ms / 1000.0,
            decode_responses=True,
            max_connections=50,  # Connection pool size
            retry_on_timeout=True,
        )

        # Get master connection (read/write)
        self._redis_master = self._sentinel.master_for(
            service_name=settings.redis_sentinel_service,
            socket_connect_timeout=settings.redis_socket_connect_timeout_ms / 1000.0,
            socket_timeout=settings.redis_socket_timeout_ms / 1000.0,
        )

        # Get replica connection (read-only, for future optimizations)
        try:
            self._redis_replica = self._sentinel.slave_for(
                service_name=settings.redis_sentinel_service,
                socket_connect_timeout=settings.redis_socket_connect_timeout_ms
                / 1000.0,
                socket_timeout=settings.redis_socket_timeout_ms / 1000.0,
            )
        except Exception as e:
            # Replica is optional - we can fall back to master for reads
            logger.warning(
                f"Could not connect to Redis replica, will use master for reads: {e}"
            )
            self._redis_replica = None

        logger.info(
            f"Redis Sentinel initialized: service={settings.redis_sentinel_service}, "
            f"sentinels={len(sentinel_list)}"
        )

    def _init_single(self) -> None:
        """Initialize single Redis instance connection."""
        # Create connection pool
        self._master_pool = ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            socket_connect_timeout=settings.redis_socket_connect_timeout_ms / 1000.0,
            socket_timeout=settings.redis_socket_timeout_ms / 1000.0,
            decode_responses=True,
            max_connections=50,
            retry_on_timeout=True,
        )

        # Create Redis client with pool
        self._redis_master = redis.Redis(connection_pool=self._master_pool)

        logger.info(
            f"Redis single mode initialized: {settings.redis_host}:{settings.redis_port}"
        )

    def get_redis(self, read_only: bool = False) -> redis.Redis:
        """
        Get Redis client instance.

        Args:
            read_only: If True and replicas are available (sentinel mode),
                      return a replica connection for read operations.
                      Default False (always use master).

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If client not initialized
        """
        if not self._initialized:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")

        # For read-only operations in sentinel mode, use replica if available
        if read_only and self._redis_replica is not None:
            return self._redis_replica

        # Default to master for all writes and single mode
        return self._redis_master

    def ping(self) -> bool:
        """
        Verify Redis connection is alive.

        Returns:
            True if ping successful

        Raises:
            RedisError: If connection fails
        """
        try:
            result = self._redis_master.ping()
            return result
        except RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            raise

    async def close(self) -> None:
        """
        Gracefully close all Redis connections and drain pools.
        Should be called during application shutdown.
        """
        if not self._initialized:
            return

        try:
            # Close master connection
            if self._redis_master:
                await self._redis_master.aclose() if hasattr(
                    self._redis_master, "aclose"
                ) else self._redis_master.close()
                logger.info("Redis master connection closed")

            # Close replica connection
            if self._redis_replica:
                await self._redis_replica.aclose() if hasattr(
                    self._redis_replica, "aclose"
                ) else self._redis_replica.close()
                logger.info("Redis replica connection closed")

            # Disconnect pools
            if self._master_pool:
                self._master_pool.disconnect()
                logger.info("Redis master pool disconnected")

            if self._sentinel:
                # Sentinel connections are managed by redis-py
                logger.info("Redis Sentinel connections released")

            self._initialized = False
            logger.info("Redis client shutdown complete")

        except Exception as e:
            logger.error(f"Error during Redis client shutdown: {e}", exc_info=True)

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized

    @property
    def mode(self) -> str:
        """Get current Redis mode (single/sentinel)."""
        return self._mode


# Global Redis client factory instance
_redis_factory: Optional[RedisClientFactory] = None


def get_redis_factory() -> RedisClientFactory:
    """
    Get the global Redis client factory instance.

    Returns:
        RedisClientFactory instance
    """
    global _redis_factory

    if _redis_factory is None:
        _redis_factory = RedisClientFactory()

    return _redis_factory


def get_redis(read_only: bool = False) -> redis.Redis:
    """
    Convenience function to get Redis client.

    Args:
        read_only: Whether to prefer replica for read operations

    Returns:
        Redis client instance
    """
    factory = get_redis_factory()
    return factory.get_redis(read_only=read_only)


# Async context manager support (future)
async def get_redis_async(read_only: bool = False):
    """
    Get async Redis client (placeholder for future async support).

    Args:
        read_only: Whether to prefer replica for read operations

    Returns:
        Redis async client instance

    Note:
        Currently returns sync client. Will be upgraded to redis.asyncio
        when async endpoints are implemented.
    """
    # For now, return sync client
    # TODO: Implement redis.asyncio support when needed
    return get_redis(read_only=read_only)
