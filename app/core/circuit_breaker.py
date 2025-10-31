"""
Circuit Breaker Pattern Implementation for External Services

Protects against cascading failures by:
- Failing fast when service is unavailable
- Automatic recovery detection (half-open state)
- Graceful degradation to fallback services

Based on pybreaker library with custom configuration for each service.
"""

from typing import Optional
from pybreaker import CircuitBreaker, CircuitBreakerListener
from loguru import logger

from app.core.config import settings


class CircuitBreakerMetricsListener(CircuitBreakerListener):
    """
    Listener for circuit breaker state changes.
    Logs state transitions for monitoring and debugging.
    """

    def state_change(self, cb, old_state, new_state):
        """Called when circuit breaker state changes"""
        logger.warning(
            f"Circuit breaker state change: {cb.name}",
            extra={
                "circuit_breaker": cb.name,
                "old_state": str(old_state),
                "new_state": str(new_state),
                "fail_counter": cb.fail_counter,
            },
        )

    def failure(self, cb, exc):
        """Called when a failure is recorded"""
        logger.debug(
            f"Circuit breaker failure: {cb.name}",
            extra={
                "circuit_breaker": cb.name,
                "fail_counter": cb.fail_counter,
                "exception": str(exc),
            },
        )

    def success(self, cb):
        """Called when a successful call is recorded"""
        logger.debug(
            f"Circuit breaker success: {cb.name}",
            extra={"circuit_breaker": cb.name, "state": str(cb.current_state)},
        )


# Global circuit breaker instances
_weaviate_breaker: Optional[CircuitBreaker] = None
_opensearch_breaker: Optional[CircuitBreaker] = None
_gemini_breaker: Optional[CircuitBreaker] = None
_redis_breaker: Optional[CircuitBreaker] = None


def get_weaviate_breaker() -> CircuitBreaker:
    """
    Get or create Weaviate circuit breaker.

    Weaviate is critical for semantic search, so we use strict settings:
    - fail_max=5: Open after 5 consecutive failures
    - reset_timeout=60: Try to recover after 60 seconds
    """
    global _weaviate_breaker

    if _weaviate_breaker is None:
        fail_max = getattr(settings, "weaviate_circuit_fail_max", 5)
        reset_timeout = getattr(settings, "weaviate_circuit_reset_timeout", 60)

        _weaviate_breaker = CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            name="weaviate",
            listeners=[CircuitBreakerMetricsListener()],
        )

        logger.info(
            f"Weaviate circuit breaker initialized: fail_max={fail_max}, reset_timeout={reset_timeout}s"
        )

    return _weaviate_breaker


def get_opensearch_breaker() -> CircuitBreaker:
    """
    Get or create OpenSearch circuit breaker.

    OpenSearch has BM25 fallback, so we use moderate settings:
    - fail_max=3: Open after 3 consecutive failures
    - reset_timeout=30: Try to recover after 30 seconds
    """
    global _opensearch_breaker

    if _opensearch_breaker is None:
        fail_max = getattr(settings, "opensearch_circuit_fail_max", 3)
        reset_timeout = getattr(settings, "opensearch_circuit_reset_timeout", 30)

        _opensearch_breaker = CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            name="opensearch",
            listeners=[CircuitBreakerMetricsListener()],
        )

        logger.info(
            f"OpenSearch circuit breaker initialized: fail_max={fail_max}, reset_timeout={reset_timeout}s"
        )

    return _opensearch_breaker


def get_gemini_breaker() -> CircuitBreaker:
    """
    Get or create Gemini LLM circuit breaker.

    Gemini API rate limits are common, so we use lenient settings:
    - fail_max=10: Open after 10 consecutive failures
    - reset_timeout=120: Try to recover after 2 minutes
    """
    global _gemini_breaker

    if _gemini_breaker is None:
        fail_max = getattr(settings, "gemini_circuit_fail_max", 10)
        reset_timeout = getattr(settings, "gemini_circuit_reset_timeout", 120)

        _gemini_breaker = CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            name="gemini",
            listeners=[CircuitBreakerMetricsListener()],
        )

        logger.info(
            f"Gemini circuit breaker initialized: fail_max={fail_max}, reset_timeout={reset_timeout}s"
        )

    return _gemini_breaker


def get_redis_breaker() -> CircuitBreaker:
    """
    Get or create Redis circuit breaker.

    Redis has Sentinel HA from Week 1, so we use very lenient settings:
    - fail_max=5: Open after 5 consecutive failures
    - reset_timeout=60: Try to recover after 60 seconds
    """
    global _redis_breaker

    if _redis_breaker is None:
        fail_max = getattr(settings, "redis_circuit_fail_max", 5)
        reset_timeout = getattr(settings, "redis_circuit_reset_timeout", 60)

        _redis_breaker = CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            name="redis",
            listeners=[CircuitBreakerMetricsListener()],
        )

        logger.info(
            f"Redis circuit breaker initialized: fail_max={fail_max}, reset_timeout={reset_timeout}s"
        )

    return _redis_breaker


def get_circuit_breaker_status() -> dict:
    """
    Get status of all circuit breakers for monitoring.

    Returns:
        Dict with circuit breaker name as key and status dict as value
    """
    breakers = {
        "weaviate": _weaviate_breaker,
        "opensearch": _opensearch_breaker,
        "gemini": _gemini_breaker,
        "redis": _redis_breaker,
    }

    status = {}
    for name, breaker in breakers.items():
        if breaker is None:
            status[name] = {"initialized": False}
        else:
            status[name] = {
                "initialized": True,
                "state": str(breaker.current_state),
                "fail_counter": breaker.fail_counter,
                "opened_at": getattr(breaker, "_opened", None),
            }

    return status


def reset_all_circuit_breakers():
    """
    Reset all circuit breakers (for testing/recovery).
    WARNING: Use with caution in production.
    """
    global _weaviate_breaker, _opensearch_breaker, _gemini_breaker, _redis_breaker

    if _weaviate_breaker:
        _weaviate_breaker.close()
    if _opensearch_breaker:
        _opensearch_breaker.close()
    if _gemini_breaker:
        _gemini_breaker.close()
    if _redis_breaker:
        _redis_breaker.close()

    logger.warning("All circuit breakers have been reset")
