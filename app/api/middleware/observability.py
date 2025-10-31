"""
Observability Middleware for FastAPI

Provides automatic:
- Request/response logging with structured context
- Metrics collection (latency, status codes, sizes)
- Trace ID generation and propagation
- Error tracking

Usage:
    from app.api.middleware.observability import ObservabilityMiddleware
    
    app.add_middleware(ObservabilityMiddleware)
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.structured_logging import get_request_logger, log_context
from app.core.metrics_week3 import week3_metrics

# Import existing metrics if available
try:
    from app.core.metrics import request_counter, latency_histogram
    HAS_LEGACY_METRICS = True
except ImportError:
    HAS_LEGACY_METRICS = False


logger = get_request_logger()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for comprehensive observability

    Automatically tracks:
    - Request/response logging
    - Prometheus metrics
    - Trace IDs
    - Performance metrics
    """

    def __init__(self, app: ASGIApp):
        """Initialize middleware"""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with observability tracking

        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint

        Returns:
            Response with headers
        """
        # Generate trace ID if not present
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

        # Extract user context (if available from auth headers)
        user_id = request.headers.get("X-User-Id", "anonymous")
        user_role = request.headers.get("X-User-Role", "guest")

        # Get request details
        method = request.method
        path = self._normalize_path(request.url.path)
        
        # Get request size
        request_size = int(request.headers.get("Content-Length", 0))

        # Start metrics tracking
        start_time = time.time()
        week3_metrics.track_http_request_start(method, path)

        # Set log context for this request
        with log_context(
            trace_id=trace_id,
            request_id=request_id,
            user_id=user_id,
            user_role=user_role,
        ):
            # Log incoming request
            logger.info(
                f"Request started: {method} {path}",
                extra={
                    "method": method,
                    "path": path,
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("User-Agent", "unknown"),
                },
            )

            try:
                # Process request
                response = await call_next(request)

                # Calculate metrics
                duration = time.time() - start_time
                status_code = response.status_code
                
                # Get response size (if available)
                response_size = int(response.headers.get("Content-Length", 0))

                # Track HTTP metrics
                week3_metrics.track_http_request_end(method, path)
                week3_metrics.track_http_sizes(
                    method, path, request_size, response_size
                )

                # Track errors
                if status_code >= 400:
                    week3_metrics.track_http_error(method, path, status_code)

                # Legacy metrics (if available)
                if HAS_LEGACY_METRICS:
                    request_counter.labels(
                        endpoint=path,
                        status="success" if status_code < 400 else "error",
                    ).inc()
                    latency_histogram.labels(endpoint=path, step="total").observe(
                        duration
                    )

                # Log response
                log_level = "error" if status_code >= 400 else "info"
                getattr(logger, log_level)(
                    f"Request completed: {method} {path} - {status_code}",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round(duration * 1000, 2),
                        "request_size_bytes": request_size,
                        "response_size_bytes": response_size,
                    },
                )

                # Add trace headers to response
                response.headers["X-Trace-Id"] = trace_id
                response.headers["X-Request-Id"] = request_id

                return response

            except Exception as e:
                # Calculate duration
                duration = time.time() - start_time

                # Track metrics
                week3_metrics.track_http_request_end(method, path)
                week3_metrics.track_http_error(method, path, 500)

                # Legacy metrics
                if HAS_LEGACY_METRICS:
                    request_counter.labels(endpoint=path, status="error").inc()

                # Log exception
                logger.exception(
                    f"Request failed: {method} {path}",
                    extra={
                        "method": method,
                        "path": path,
                        "duration_ms": round(duration * 1000, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )

                # Re-raise to let FastAPI handle it
                raise

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for metrics (remove IDs, UUIDs)

        Args:
            path: Request path

        Returns:
            Normalized path for grouping
        """
        # Replace UUIDs with placeholder
        import re

        # UUID pattern
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{id}",
            path,
            flags=re.IGNORECASE,
        )

        # Numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        # Keep only first 3 path segments to avoid cardinality explosion
        parts = path.split("/")[:4]
        return "/".join(parts)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Lightweight middleware for metrics only (no logging)

    Use this if you already have logging middleware
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track metrics only"""
        method = request.method
        path = request.url.path
        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Track metrics
            if HAS_LEGACY_METRICS:
                request_counter.labels(
                    endpoint=path,
                    status="success" if response.status_code < 400 else "error",
                ).inc()
                latency_histogram.labels(endpoint=path, step="total").observe(duration)

            return response

        except Exception:
            duration = time.time() - start_time

            # Track error metrics
            if HAS_LEGACY_METRICS:
                request_counter.labels(endpoint=path, status="error").inc()

            raise


# Utility functions for manual instrumentation


def track_operation(operation_name: str, **extra):
    """
    Context manager for tracking operations

    Usage:
        with track_operation("database_query", table="users"):
            result = db.query("SELECT ...")
    """

    class OperationTracker:
        def __init__(self, name: str, extra_context: dict):
            self.name = name
            self.extra = extra_context
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            logger.debug(f"Operation started: {self.name}", extra=self.extra)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start_time
            duration_ms = round(duration * 1000, 2)

            if exc_type:
                logger.error(
                    f"Operation failed: {self.name}",
                    extra={
                        **self.extra,
                        "duration_ms": duration_ms,
                        "error_type": exc_type.__name__,
                        "error": str(exc_val),
                    },
                )
            else:
                logger.debug(
                    f"Operation completed: {self.name}",
                    extra={**self.extra, "duration_ms": duration_ms},
                )

    return OperationTracker(operation_name, extra)
