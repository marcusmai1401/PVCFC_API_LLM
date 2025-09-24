"""
Metrics utility module for tracking API metrics
"""
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Metrics storage (in production, use Prometheus or similar)
_metrics_store = {
    "requests": defaultdict(int),
    "latencies": defaultdict(list),
    "errors": defaultdict(int),
    "cache_hits": defaultdict(int),
    "cache_misses": defaultdict(int),
}

# Lock for thread-safe operations
_metrics_lock = threading.Lock()


def track_request_metrics(
    endpoint: str, latency_ms: float, result_count: int = 0, error: bool = False
):
    """
    Track metrics for a request

    Args:
        endpoint: API endpoint name
        latency_ms: Request latency in milliseconds
        result_count: Number of results returned
        error: Whether request resulted in error
    """
    with _metrics_lock:
        # Increment request counter
        _metrics_store["requests"][endpoint] += 1
        _metrics_store["requests"]["total"] += 1

        # Track latency
        _metrics_store["latencies"][endpoint].append(latency_ms)

        # Keep only last 1000 latencies per endpoint
        if len(_metrics_store["latencies"][endpoint]) > 1000:
            _metrics_store["latencies"][endpoint] = _metrics_store["latencies"][
                endpoint
            ][-1000:]

        # Track errors
        if error:
            _metrics_store["errors"][endpoint] += 1
            _metrics_store["errors"]["total"] += 1

        logger.debug(
            f"Metrics tracked: {endpoint} - {latency_ms:.2f}ms - {result_count} results"
        )


def track_cache_metrics(hit: bool, cache_type: str = "default"):
    """
    Track cache hit/miss metrics

    Args:
        hit: Whether cache hit occurred
        cache_type: Type of cache
    """
    with _metrics_lock:
        if hit:
            _metrics_store["cache_hits"][cache_type] += 1
            _metrics_store["cache_hits"]["total"] += 1
        else:
            _metrics_store["cache_misses"][cache_type] += 1
            _metrics_store["cache_misses"]["total"] += 1


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get summary of current metrics

    Returns:
        Dictionary with metrics summary
    """
    with _metrics_lock:
        summary = {
            "requests": dict(_metrics_store["requests"]),
            "errors": dict(_metrics_store["errors"]),
            "cache": {
                "hits": dict(_metrics_store["cache_hits"]),
                "misses": dict(_metrics_store["cache_misses"]),
            },
            "latencies": {},
        }

        # Calculate latency statistics
        for endpoint, latencies in _metrics_store["latencies"].items():
            if latencies:
                summary["latencies"][endpoint] = {
                    "count": len(latencies),
                    "mean": sum(latencies) / len(latencies),
                    "min": min(latencies),
                    "max": max(latencies),
                    "p50": _percentile(latencies, 50),
                    "p95": _percentile(latencies, 95),
                    "p99": _percentile(latencies, 99),
                }

        # Calculate cache hit rate
        total_hits = _metrics_store["cache_hits"].get("total", 0)
        total_misses = _metrics_store["cache_misses"].get("total", 0)
        if total_hits + total_misses > 0:
            summary["cache"]["hit_rate"] = total_hits / (total_hits + total_misses)
        else:
            summary["cache"]["hit_rate"] = 0.0

        return summary


def reset_metrics():
    """
    Reset all metrics
    """
    with _metrics_lock:
        _metrics_store["requests"].clear()
        _metrics_store["latencies"].clear()
        _metrics_store["errors"].clear()
        _metrics_store["cache_hits"].clear()
        _metrics_store["cache_misses"].clear()
        logger.info("Metrics reset")


def _percentile(data: list, percentile: int) -> float:
    """
    Calculate percentile of data

    Args:
        data: List of values
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value
    """
    if not data:
        return 0.0

    sorted_data = sorted(data)
    index = int(len(sorted_data) * percentile / 100)

    if index >= len(sorted_data):
        return sorted_data[-1]

    return sorted_data[index]


class MetricsCollector:
    """
    Context manager for collecting metrics
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.start_time = None
        self.error = False

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self.start_time) * 1000

        if exc_type is not None:
            self.error = True

        track_request_metrics(
            endpoint=self.endpoint, latency_ms=latency_ms, error=self.error
        )


# Export functions and classes
__all__ = [
    "track_request_metrics",
    "track_cache_metrics",
    "get_metrics_summary",
    "reset_metrics",
    "MetricsCollector",
]
