"""
Prometheus metrics for monitoring RAG pipeline.
"""
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Request counters
request_counter = Counter(
    "rag_requests_total", "Total number of RAG requests", ["endpoint", "status"]
)

# Latency histograms
latency_histogram = Histogram(
    "rag_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint", "step"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Token usage
token_counter = Counter(
    "rag_tokens_total",
    "Total tokens used",
    ["model", "type"],  # type: prompt, completion
)

# Cache metrics
cache_hits = Counter("rag_cache_hits_total", "Total cache hits", ["cache_type"])

cache_misses = Counter("rag_cache_misses_total", "Total cache misses", ["cache_type"])

# Index metrics
index_size = Gauge("rag_index_size", "Size of search indices", ["index_type"])

index_query_counter = Counter(
    "rag_index_queries_total", "Total index queries", ["index_type", "status"]
)

# Retrieval metrics
retrieval_chunks = Histogram(
    "rag_retrieval_chunks",
    "Number of chunks retrieved",
    ["method"],
    buckets=(5, 10, 20, 30, 50, 100),
)

retrieval_scores = Histogram(
    "rag_retrieval_scores",
    "Retrieval relevance scores",
    ["method"],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Reranking metrics
rerank_gain = Histogram(
    "rag_rerank_gain",
    "Score improvement from reranking",
    buckets=(-0.5, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.5),
)

# Generation metrics
generation_confidence = Histogram(
    "rag_generation_confidence",
    "Answer confidence scores",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

citation_count = Histogram(
    "rag_citations_per_answer",
    "Number of citations per answer",
    buckets=(0, 1, 2, 3, 5, 10, 20),
)

# CoVe metrics
cove_verification_rate = Histogram(
    "rag_cove_verification_rate",
    "Chain-of-Verification success rate",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

cove_adjustments = Counter(
    "rag_cove_adjustments_total",
    "Total CoVe adjustments made",
    ["adjustment_type"],  # warning, correction, rejection
)

# Citation metrics
citation_rate = Gauge(
    "rag_citation_rate", "Rate of responses with valid citations", ["endpoint"]
)

citation_precision = Histogram(
    "rag_citation_precision",
    "Precision of citations (valid/total)",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Error counters
error_counter = Counter("rag_errors_total", "Total errors", ["endpoint", "error_type"])

# Rate limit metrics
rate_limit_exceeded = Counter(
    "rag_rate_limit_exceeded_total", "Rate limit exceeded count", ["client_id"]
)

# Pipeline step metrics
pipeline_step_duration = Histogram(
    "rag_pipeline_step_duration_seconds",
    "Duration of each pipeline step",
    ["step"],  # query_transform, retrieve, rerank, generate, verify
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

pipeline_step_errors = Counter(
    "rag_pipeline_step_errors_total", "Errors per pipeline step", ["step", "error_type"]
)

# Answer quality metrics
answer_length = Histogram(
    "rag_answer_length_chars",
    "Length of generated answers in characters",
    buckets=(0, 50, 100, 200, 500, 1000, 2000, 5000),
)

answer_completeness = Histogram(
    "rag_answer_completeness",
    "Completeness score of answers",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# HyDE metrics
hyde_enabled_counter = Counter(
    "rag_hyde_enabled_total", "Requests with HyDE enabled", ["endpoint"]
)

hyde_improvement = Histogram(
    "rag_hyde_improvement",
    "Retrieval score improvement from HyDE",
    buckets=(-0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.5),
)


class MetricsCollector:
    """Utility class for collecting metrics."""

    @staticmethod
    def record_request(endpoint: str, status: str):
        """Record a request."""
        request_counter.labels(endpoint=endpoint, status=status).inc()

    @staticmethod
    def record_latency(endpoint: str, step: str, duration: float):
        """Record latency for a step."""
        latency_histogram.labels(endpoint=endpoint, step=step).observe(duration)

    @staticmethod
    @contextmanager
    def timer(endpoint: str, step: str):
        """Context manager for timing operations."""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            latency_histogram.labels(endpoint=endpoint, step=step).observe(duration)

    @staticmethod
    def record_tokens(model: str, prompt_tokens: int, completion_tokens: int):
        """Record token usage."""
        token_counter.labels(model=model, type="prompt").inc(prompt_tokens)
        token_counter.labels(model=model, type="completion").inc(completion_tokens)

    @staticmethod
    def record_cache(cache_type: str, hit: bool):
        """Record cache hit/miss."""
        if hit:
            cache_hits.labels(cache_type=cache_type).inc()
        else:
            cache_misses.labels(cache_type=cache_type).inc()

    @staticmethod
    def update_index_size(index_type: str, size: int):
        """Update index size gauge."""
        index_size.labels(index_type=index_type).set(size)

    @staticmethod
    def record_retrieval(method: str, chunk_count: int, scores: list):
        """Record retrieval metrics."""
        retrieval_chunks.labels(method=method).observe(chunk_count)
        for score in scores[:10]:  # Sample first 10 scores
            retrieval_scores.labels(method=method).observe(score)

    @staticmethod
    def record_rerank(original_scores: list, reranked_scores: list):
        """Record reranking metrics."""
        if original_scores and reranked_scores:
            # Calculate average gain
            avg_original = sum(original_scores[:5]) / min(5, len(original_scores))
            avg_reranked = sum(reranked_scores[:5]) / min(5, len(reranked_scores))
            gain = avg_reranked - avg_original
            rerank_gain.observe(gain)

    @staticmethod
    def record_generation(confidence: float, citation_count_val: int):
        """Record generation metrics."""
        generation_confidence.observe(confidence)
        citation_count.observe(citation_count_val)

    @staticmethod
    def record_cove(verification_rate: float):
        """Record CoVe metrics."""
        cove_verification_rate.observe(verification_rate)

    @staticmethod
    def record_error(endpoint: str, error_type: str):
        """Record an error."""
        error_counter.labels(endpoint=endpoint, error_type=error_type).inc()

    @staticmethod
    def record_rate_limit(client_id: str):
        """Record rate limit exceeded."""
        rate_limit_exceeded.labels(client_id=client_id).inc()

    @staticmethod
    def record_pipeline_step(step: str, duration: float, error: Optional[str] = None):
        """Record pipeline step metrics."""
        pipeline_step_duration.labels(step=step).observe(duration)
        if error:
            pipeline_step_errors.labels(step=step, error_type=error).inc()

    @staticmethod
    def record_citation_metrics(
        endpoint: str, has_citations: bool, precision: float = None
    ):
        """Record citation metrics."""
        # Update citation rate (rolling average would be better in production)
        current_rate = citation_rate.labels(endpoint=endpoint)._value.get() or 0.0
        new_rate = (current_rate * 0.9) + (1.0 if has_citations else 0.0) * 0.1
        citation_rate.labels(endpoint=endpoint).set(new_rate)

        if precision is not None:
            citation_precision.observe(precision)

    @staticmethod
    def record_cove_adjustment(adjustment_type: str):
        """Record CoVe adjustment."""
        cove_adjustments.labels(adjustment_type=adjustment_type).inc()

    @staticmethod
    def record_answer_quality(length: int, completeness: float = None):
        """Record answer quality metrics."""
        answer_length.observe(length)
        if completeness is not None:
            answer_completeness.observe(completeness)

    @staticmethod
    def record_hyde(endpoint: str, enabled: bool, improvement: float = None):
        """Record HyDE metrics."""
        if enabled:
            hyde_enabled_counter.labels(endpoint=endpoint).inc()
        if improvement is not None:
            hyde_improvement.observe(improvement)

    @staticmethod
    def increment_counter(
        metric_name: str, labels: Dict[str, str] = None, value: float = 1.0
    ):
        """Generic counter increment method for evaluation metrics."""
        # Map metric names to actual counter objects
        metric_mapping = {
            "request_counter": request_counter,
            "error_counter": error_counter,
            "token_counter": token_counter,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "index_query_counter": index_query_counter,
            "cove_adjustments": cove_adjustments,
            "rate_limit_exceeded": rate_limit_exceeded,
            "pipeline_step_errors": pipeline_step_errors,
            "hyde_enabled_counter": hyde_enabled_counter,
        }

        if metric_name in metric_mapping:
            metric = metric_mapping[metric_name]
            if labels:
                metric.labels(**labels).inc(value)
            else:
                metric.inc(value)
        else:
            # For custom evaluation metrics, create dynamic counters
            if not hasattr(MetricsCollector, "_custom_counters"):
                MetricsCollector._custom_counters = {}

            if metric_name not in MetricsCollector._custom_counters:
                # Create a new counter for evaluation metrics
                safe_name = metric_name.replace(".", "_").replace("-", "_")
                MetricsCollector._custom_counters[metric_name] = Counter(
                    f"rag_{safe_name}_total",
                    f"Custom evaluation metric: {metric_name}",
                    list(labels.keys()) if labels else [],
                )

            counter = MetricsCollector._custom_counters[metric_name]
            if labels:
                counter.labels(**labels).inc(value)
            else:
                counter.inc(value)

    @staticmethod
    def get_timing_breakdown(timings: Dict[str, float]) -> Dict[str, float]:
        """Calculate timing breakdown percentages."""
        total = sum(timings.values())
        if total == 0:
            return {}
        return {k: (v / total) * 100 for k, v in timings.items()}


def get_metrics() -> str:
    """Get Prometheus metrics in text format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST
