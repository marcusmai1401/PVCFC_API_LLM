"""
Tracing utility module for request tracing
"""
import logging
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Trace storage (in production, use Jaeger or similar)
_trace_store = deque(maxlen=1000)  # Keep last 1000 traces
_trace_lock = threading.Lock()


def generate_trace_id() -> str:
    """
    Generate unique trace ID

    Returns:
        Unique trace ID string
    """
    return str(uuid.uuid4())


def trace_request(
    operation: str, query: str, metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Start tracing a request

    Args:
        operation: Operation name (e.g., 'ask', 'locate', 'report')
        query: User query or request
        metadata: Additional metadata to include

    Returns:
        Trace ID for the request
    """
    trace_id = generate_trace_id()

    trace_entry = {
        "trace_id": trace_id,
        "operation": operation,
        "query": query[:500],  # Truncate long queries
        "start_time": time.time(),
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {},
        "spans": [],
    }

    with _trace_lock:
        _trace_store.append(trace_entry)

    logger.debug(f"Started trace {trace_id} for operation {operation}")

    return trace_id


def add_span(
    trace_id: str,
    span_name: str,
    duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Add a span to existing trace

    Args:
        trace_id: Trace ID to add span to
        span_name: Name of the span
        duration_ms: Duration of span in milliseconds
        metadata: Additional span metadata
    """
    with _trace_lock:
        for trace in _trace_store:
            if trace["trace_id"] == trace_id:
                span = {
                    "name": span_name,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata or {},
                }
                trace["spans"].append(span)
                logger.debug(f"Added span {span_name} to trace {trace_id}")
                break


def complete_trace(trace_id: str, status: str = "success", error: Optional[str] = None):
    """
    Complete a trace

    Args:
        trace_id: Trace ID to complete
        status: Final status of the trace
        error: Error message if applicable
    """
    with _trace_lock:
        for trace in _trace_store:
            if trace["trace_id"] == trace_id:
                trace["end_time"] = time.time()
                trace["duration_ms"] = (trace["end_time"] - trace["start_time"]) * 1000
                trace["status"] = status
                if error:
                    trace["error"] = error
                logger.debug(f"Completed trace {trace_id} with status {status}")
                break


def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    """
    Get trace by ID

    Args:
        trace_id: Trace ID to retrieve

    Returns:
        Trace data or None if not found
    """
    with _trace_lock:
        for trace in _trace_store:
            if trace["trace_id"] == trace_id:
                return trace.copy()
    return None


def get_recent_traces(limit: int = 10) -> list:
    """
    Get recent traces

    Args:
        limit: Maximum number of traces to return

    Returns:
        List of recent traces
    """
    with _trace_lock:
        traces = list(_trace_store)
        # Return most recent first
        return traces[-limit:][::-1]


def get_trace_summary() -> Dict[str, Any]:
    """
    Get summary of traces

    Returns:
        Dictionary with trace statistics
    """
    with _trace_lock:
        if not _trace_store:
            return {
                "total_traces": 0,
                "operations": {},
                "avg_duration_ms": 0,
                "error_rate": 0,
            }

        # Calculate statistics
        total = len(_trace_store)
        operations = {}
        total_duration = 0
        error_count = 0

        for trace in _trace_store:
            op = trace.get("operation", "unknown")
            operations[op] = operations.get(op, 0) + 1

            if "duration_ms" in trace:
                total_duration += trace["duration_ms"]

            if trace.get("status") == "error":
                error_count += 1

        return {
            "total_traces": total,
            "operations": operations,
            "avg_duration_ms": total_duration / total if total > 0 else 0,
            "error_rate": error_count / total if total > 0 else 0,
        }


class TraceContext:
    """
    Context manager for tracing operations
    """

    def __init__(
        self, operation: str, query: str = "", metadata: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.query = query
        self.metadata = metadata
        self.trace_id = None
        self.start_time = None

    def __enter__(self):
        self.trace_id = trace_request(self.operation, self.query, self.metadata)
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000

        if exc_type is None:
            complete_trace(self.trace_id, "success")
        else:
            complete_trace(
                self.trace_id, "error", str(exc_val) if exc_val else "Unknown error"
            )

        # Log summary
        logger.info(
            f"Trace {self.trace_id} completed: "
            f"operation={self.operation}, "
            f"duration={duration_ms:.2f}ms, "
            f"status={'error' if exc_type else 'success'}"
        )

    def add_span(
        self, name: str, duration_ms: float, metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a span to this trace"""
        if self.trace_id:
            add_span(self.trace_id, name, duration_ms, metadata)


# Export functions and classes
__all__ = [
    "generate_trace_id",
    "trace_request",
    "add_span",
    "complete_trace",
    "get_trace",
    "get_recent_traces",
    "get_trace_summary",
    "TraceContext",
]
