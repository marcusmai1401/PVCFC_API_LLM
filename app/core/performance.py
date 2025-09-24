"""
Performance monitoring for RAG pipeline.
Tracks latency breakdown, memory usage, and concurrent requests.
"""
import asyncio
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Timing breakdown (ms)
    query_transform_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    generation_ms: float = 0.0
    cove_verification_ms: float = 0.0
    total_ms: float = 0.0

    # Resource usage
    memory_mb: float = 0.0
    cpu_percent: float = 0.0

    # Concurrency
    concurrent_requests: int = 0
    queue_size: int = 0

    # Quality metrics
    chunks_retrieved: int = 0
    citations_generated: int = 0
    confidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "timing": {
                "query_transform_ms": round(self.query_transform_ms, 2),
                "retrieval_ms": round(self.retrieval_ms, 2),
                "rerank_ms": round(self.rerank_ms, 2),
                "generation_ms": round(self.generation_ms, 2),
                "cove_verification_ms": round(self.cove_verification_ms, 2),
                "total_ms": round(self.total_ms, 2),
            },
            "resources": {
                "memory_mb": round(self.memory_mb, 2),
                "cpu_percent": round(self.cpu_percent, 2),
            },
            "concurrency": {
                "concurrent_requests": self.concurrent_requests,
                "queue_size": self.queue_size,
            },
            "quality": {
                "chunks_retrieved": self.chunks_retrieved,
                "citations_generated": self.citations_generated,
                "confidence_score": round(self.confidence_score, 3),
            },
        }

    def get_breakdown_percentages(self) -> Dict[str, float]:
        """Get timing breakdown as percentages."""
        if self.total_ms == 0:
            return {}

        return {
            "query_transform": round(
                (self.query_transform_ms / self.total_ms) * 100, 1
            ),
            "retrieval": round((self.retrieval_ms / self.total_ms) * 100, 1),
            "rerank": round((self.rerank_ms / self.total_ms) * 100, 1),
            "generation": round((self.generation_ms / self.total_ms) * 100, 1),
            "cove_verification": round(
                (self.cove_verification_ms / self.total_ms) * 100, 1
            ),
        }


class PerformanceMonitor:
    """Monitor performance metrics across the RAG pipeline."""

    def __init__(self, history_size: int = 1000):
        """
        Initialize performance monitor.

        Args:
            history_size: Number of recent metrics to keep in memory
        """
        self.current_metrics: Dict[str, PerformanceMetrics] = {}
        self.history: deque = deque(maxlen=history_size)
        self.concurrent_requests = 0
        self.lock = threading.Lock()

        # Start resource monitoring thread
        self.process = psutil.Process()
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_resources, daemon=True
        )
        self.monitor_thread.start()

    def _monitor_resources(self):
        """Background thread to monitor system resources."""
        while self.monitoring:
            try:
                # Update resource metrics for all active requests
                with self.lock:
                    memory_mb = self.process.memory_info().rss / 1024 / 1024
                    cpu_percent = self.process.cpu_percent(interval=0.1)

                    for metrics in self.current_metrics.values():
                        metrics.memory_mb = memory_mb
                        metrics.cpu_percent = cpu_percent
                        metrics.concurrent_requests = self.concurrent_requests

                time.sleep(1)  # Update every second
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                time.sleep(5)

    def start_request(self, request_id: str) -> PerformanceMetrics:
        """Start monitoring a new request."""
        with self.lock:
            self.concurrent_requests += 1
            metrics = PerformanceMetrics(concurrent_requests=self.concurrent_requests)
            self.current_metrics[request_id] = metrics
            return metrics

    def end_request(self, request_id: str):
        """End monitoring a request."""
        with self.lock:
            if request_id in self.current_metrics:
                metrics = self.current_metrics[request_id]
                metrics.total_ms = sum(
                    [
                        metrics.query_transform_ms,
                        metrics.retrieval_ms,
                        metrics.rerank_ms,
                        metrics.generation_ms,
                        metrics.cove_verification_ms,
                    ]
                )

                # Add to history
                self.history.append(metrics)

                # Remove from current
                del self.current_metrics[request_id]
                self.concurrent_requests -= 1

    @contextmanager
    def measure_step(self, request_id: str, step: str):
        """
        Context manager to measure a pipeline step.

        Args:
            request_id: Request identifier
            step: Step name (query_transform, retrieval, rerank, generation, cove_verification)
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000

            with self.lock:
                if request_id in self.current_metrics:
                    metrics = self.current_metrics[request_id]

                    if step == "query_transform":
                        metrics.query_transform_ms = duration_ms
                    elif step == "retrieval":
                        metrics.retrieval_ms = duration_ms
                    elif step == "rerank":
                        metrics.rerank_ms = duration_ms
                    elif step == "generation":
                        metrics.generation_ms = duration_ms
                    elif step == "cove_verification":
                        metrics.cove_verification_ms = duration_ms

    def update_quality_metrics(
        self,
        request_id: str,
        chunks_retrieved: int = None,
        citations_generated: int = None,
        confidence_score: float = None,
    ):
        """Update quality metrics for a request."""
        with self.lock:
            if request_id in self.current_metrics:
                metrics = self.current_metrics[request_id]

                if chunks_retrieved is not None:
                    metrics.chunks_retrieved = chunks_retrieved
                if citations_generated is not None:
                    metrics.citations_generated = citations_generated
                if confidence_score is not None:
                    metrics.confidence_score = confidence_score

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        with self.lock:
            # Calculate statistics from history
            if not self.history:
                return {
                    "concurrent_requests": self.concurrent_requests,
                    "samples": 0,
                }

            recent = list(self.history)[-100:]  # Last 100 requests

            # Calculate percentiles
            latencies = [m.total_ms for m in recent]
            latencies.sort()

            def percentile(lst, p):
                if not lst:
                    return 0
                k = (len(lst) - 1) * p
                f = int(k)
                c = f + 1 if f < len(lst) - 1 else f
                return lst[f] if k == f else lst[f] * (c - k) + lst[c] * (k - f)

            # Calculate step averages
            step_avgs = {
                "query_transform": sum(m.query_transform_ms for m in recent)
                / len(recent),
                "retrieval": sum(m.retrieval_ms for m in recent) / len(recent),
                "rerank": sum(m.rerank_ms for m in recent) / len(recent),
                "generation": sum(m.generation_ms for m in recent) / len(recent),
                "cove_verification": sum(m.cove_verification_ms for m in recent)
                / len(recent),
            }

            # Calculate quality averages
            quality_avgs = {
                "chunks_retrieved": sum(m.chunks_retrieved for m in recent)
                / len(recent),
                "citations_generated": sum(m.citations_generated for m in recent)
                / len(recent),
                "confidence_score": sum(m.confidence_score for m in recent)
                / len(recent),
            }

            # Current resource usage
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            cpu_percent = self.process.cpu_percent(interval=0.1)

            return {
                "concurrent_requests": self.concurrent_requests,
                "samples": len(recent),
                "latency": {
                    "p50": round(percentile(latencies, 0.5), 2),
                    "p75": round(percentile(latencies, 0.75), 2),
                    "p90": round(percentile(latencies, 0.9), 2),
                    "p95": round(percentile(latencies, 0.95), 2),
                    "p99": round(percentile(latencies, 0.99), 2),
                    "mean": round(sum(latencies) / len(latencies), 2),
                },
                "step_breakdown_ms": {k: round(v, 2) for k, v in step_avgs.items()},
                "quality": {k: round(v, 2) for k, v in quality_avgs.items()},
                "resources": {
                    "memory_mb": round(memory_mb, 2),
                    "cpu_percent": round(cpu_percent, 2),
                },
            }

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent performance history."""
        with self.lock:
            recent = list(self.history)[-limit:]
            return [m.to_dict() for m in recent]

    def shutdown(self):
        """Shutdown the monitor."""
        self.monitoring = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)


# Global monitor instance
_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor."""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


# Convenience functions
def start_request_monitoring(request_id: str) -> PerformanceMetrics:
    """Start monitoring a request."""
    return get_monitor().start_request(request_id)


def end_request_monitoring(request_id: str):
    """End monitoring a request."""
    get_monitor().end_request(request_id)


@contextmanager
def monitor_step(request_id: str, step: str):
    """Monitor a pipeline step."""
    monitor = get_monitor()
    with monitor.measure_step(request_id, step):
        yield


def get_performance_stats() -> Dict[str, Any]:
    """Get current performance statistics."""
    return get_monitor().get_current_stats()
