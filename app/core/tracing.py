"""
Distributed tracing for RAG pipeline.
"""
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Represents a tracing span."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = None
    status: str = "ok"
    error: Optional[str] = None

    def finish(self, status: str = "ok", error: Optional[str] = None):
        """Finish the span."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.error = error

    def add_tag(self, key: str, value: Any):
        """Add a tag to the span."""
        if self.tags is None:
            self.tags = {}
        self.tags[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary."""
        data = asdict(self)
        data["timestamp"] = datetime.fromtimestamp(self.start_time).isoformat()
        return data


class Tracer:
    """Simple tracer for distributed tracing."""

    def __init__(self):
        self.spans: Dict[str, Span] = {}
        self.current_trace_id: Optional[str] = None
        self.span_stack: list = []

    def start_trace(self, trace_id: str):
        """Start a new trace."""
        self.current_trace_id = trace_id
        self.spans = {}
        self.span_stack = []

    def start_span(self, operation: str, span_id: str) -> Span:
        """Start a new span."""
        parent_span_id = self.span_stack[-1] if self.span_stack else None

        span = Span(
            trace_id=self.current_trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation=operation,
            start_time=time.time(),
        )

        self.spans[span_id] = span
        self.span_stack.append(span_id)

        logger.debug(f"Started span: {operation} [{span_id}]")
        return span

    def end_span(self, span_id: str, status: str = "ok", error: Optional[str] = None):
        """End a span."""
        if span_id in self.spans:
            span = self.spans[span_id]
            span.finish(status=status, error=error)

            if self.span_stack and self.span_stack[-1] == span_id:
                self.span_stack.pop()

            logger.debug(
                f"Ended span: {span.operation} [{span_id}] - {span.duration_ms:.0f}ms"
            )

    @contextmanager
    def span(self, operation: str, span_id: Optional[str] = None):
        """Context manager for tracing a span."""
        if span_id is None:
            import uuid

            span_id = str(uuid.uuid4())[:8]

        span = self.start_span(operation, span_id)
        try:
            yield span
            self.end_span(span_id, status="ok")
        except Exception as e:
            self.end_span(span_id, status="error", error=str(e))
            raise

    def get_trace(self) -> Dict[str, Any]:
        """Get the complete trace."""
        return {
            "trace_id": self.current_trace_id,
            "spans": [span.to_dict() for span in self.spans.values()],
            "total_spans": len(self.spans),
            "total_duration_ms": self._calculate_total_duration(),
        }

    def _calculate_total_duration(self) -> float:
        """Calculate total trace duration."""
        if not self.spans:
            return 0

        min_start = min(span.start_time for span in self.spans.values())
        max_end = max(span.end_time or span.start_time for span in self.spans.values())
        return (max_end - min_start) * 1000

    def export_trace(self) -> str:
        """Export trace as JSON."""
        return json.dumps(self.get_trace(), indent=2)


# Global tracer instance
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Get or create the global tracer."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def start_trace(trace_id: str):
    """Start a new trace."""
    tracer = get_tracer()
    tracer.start_trace(trace_id)


@contextmanager
def trace_span(operation: str, **tags):
    """Trace a span with optional tags."""
    tracer = get_tracer()
    with tracer.span(operation) as span:
        for key, value in tags.items():
            span.add_tag(key, value)
        yield span


def add_trace_tag(key: str, value: Any):
    """Add a tag to the current span."""
    tracer = get_tracer()
    if tracer.span_stack:
        current_span_id = tracer.span_stack[-1]
        if current_span_id in tracer.spans:
            tracer.spans[current_span_id].add_tag(key, value)


def trace_operation(operation_name: str):
    """Decorator to trace a function or method."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            with trace_span(operation_name) as span:
                span.add_tag("function", func.__name__)
                span.add_tag("module", func.__module__)
                try:
                    result = func(*args, **kwargs)
                    span.add_tag("status", "success")
                    return result
                except Exception as e:
                    span.add_tag("status", "error")
                    span.add_tag("error", str(e))
                    raise

        return wrapper

    return decorator


def get_current_trace() -> Optional[Dict[str, Any]]:
    """Get the current trace."""
    tracer = get_tracer()
    if tracer.current_trace_id:
        return tracer.get_trace()
    return None


# Pipeline-specific tracing helpers
@contextmanager
def trace_query_transform(**kwargs):
    """Trace query transformation step."""
    with trace_span("query_transform", **kwargs) as span:
        span.add_tag("step", "query_transform")
        span.add_tag("execution_mode", kwargs.get("execution_mode", "production"))
        span.add_tag("hyde_enabled", kwargs.get("hyde_enabled", False))
        yield span


@contextmanager
def trace_retrieval(**kwargs):
    """Trace retrieval step."""
    with trace_span("retrieval", **kwargs) as span:
        span.add_tag("step", "retrieval")
        span.add_tag("k_bm25", kwargs.get("k_bm25", 0))
        span.add_tag("k_faiss", kwargs.get("k_faiss", 0))
        span.add_tag("final_k", kwargs.get("final_k", 0))
        yield span


@contextmanager
def trace_rerank(**kwargs):
    """Trace reranking step."""
    with trace_span("rerank", **kwargs) as span:
        span.add_tag("step", "rerank")
        span.add_tag("top_k", kwargs.get("top_k", 0))
        span.add_tag("model", kwargs.get("model", "unknown"))
        yield span


@contextmanager
def trace_generation(**kwargs):
    """Trace generation step."""
    with trace_span("generation", **kwargs) as span:
        span.add_tag("step", "generation")
        span.add_tag("model", kwargs.get("model", "unknown"))
        span.add_tag("tier", kwargs.get("tier", "heavy"))
        span.add_tag("max_tokens", kwargs.get("max_tokens", 0))
        yield span


@contextmanager
def trace_cove_verification(**kwargs):
    """Trace CoVe verification step."""
    with trace_span("cove_verification", **kwargs) as span:
        span.add_tag("step", "cove_verification")
        span.add_tag("enabled", kwargs.get("enabled", True))
        span.add_tag("claims_count", kwargs.get("claims_count", 0))
        yield span


class TracingMiddleware:
    """Middleware for automatic request tracing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            method = scope["method"]

            # Skip health checks and metrics
            if path in ["/healthz", "/metrics"]:
                await self.app(scope, receive, send)
                return

            # Extract or generate trace ID (use X-Trace-ID to match LoggingMiddleware)
            headers = dict(scope.get("headers", []))
            trace_id = headers.get(
                b"x-trace-id", headers.get(b"X-Trace-ID", b"")
            ).decode()
            if not trace_id:
                import uuid

                trace_id = str(uuid.uuid4())

            # Start trace
            tracer = get_tracer()
            tracer.start_trace(trace_id)

            # Create request span
            with tracer.span(f"{method} {path}", span_id="request") as span:
                span.add_tag("http.method", method)
                span.add_tag("http.path", path)

                # Inject trace ID into response headers (use X-Trace-ID to match LoggingMiddleware)
                async def send_wrapper(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        headers.append((b"X-Trace-ID", trace_id.encode()))
                        message["headers"] = headers

                        # Add status code to span
                        span.add_tag("http.status_code", message.get("status", 200))

                    await send(message)

                await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)
