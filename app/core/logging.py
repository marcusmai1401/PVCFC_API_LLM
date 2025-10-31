"""
Cấu hình logging cho ứng dụng sử dụng loguru
Bao gồm middleware để log requests và mask sensitive data
"""
import json
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging_filter import redact_secrets


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware để log tất cả requests và responses với structured fields"""

    async def dispatch(self, request: Request, call_next):
        # Tạo trace_id và request_id duy nhất cho request
        trace_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())[:8]  # Short ID for easier tracking
        request.state.trace_id = trace_id
        request.state.request_id = request_id
        request.state.start_time = time.time()

        # Ghi log request
        start_time = time.time()

        # Extract endpoint info
        endpoint = request.url.path

        # Extract user info if available
        user_id = request.headers.get("X-User-ID", "anonymous")
        tenant_id = request.headers.get("X-Tenant-ID", "default")

        # Mask sensitive headers
        headers = dict(request.headers)
        headers = self._mask_sensitive_data(headers)

        # Structured log fields for request
        request_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "request_id": request_id,
            "method": request.method,
            "endpoint": endpoint,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "headers": headers,
            "event_type": "request_start",
        }

        logger.info(f"Request started: {endpoint}", extra=request_info)

        # Gọi handler tiếp theo
        try:
            response: Response = await call_next(request)

            # Tính latency và metrics
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract timing breakdown if available
            timing_breakdown = getattr(request.state, "timing_breakdown", {})
            citations = getattr(request.state, "citations", [])

            # Structured log fields for response
            response_info = {
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "request_id": request_id,
                "endpoint": endpoint,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "timing_breakdown": timing_breakdown,
                "citations_count": len(citations) if citations else 0,
                "citations": citations[:5]
                if citations
                else [],  # Log first 5 citations
                "event_type": "request_complete",
                "success": 200 <= response.status_code < 400,
            }

            logger.info(
                f"Request completed: {endpoint} [{response.status_code}]",
                extra=response_info,
            )

            # Thêm trace_id và request_id vào response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log lỗi với structured fields
            latency_ms = int((time.time() - start_time) * 1000)
            error_info = {
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": trace_id,
                "request_id": request_id,
                "endpoint": endpoint,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "error_stack": str(e.__traceback__)
                if hasattr(e, "__traceback__")
                else None,
                "latency_ms": latency_ms,
                "event_type": "request_error",
                "success": False,
            }
            logger.error(
                f"Request failed: {endpoint} [{type(e).__name__}]", extra=error_info
            )
            raise

    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive information trong logs"""
        masked = {}
        sensitive_keys = {
            "authorization",
            "x-api-key",
            "cookie",
            "openai_api_key",
            "gemini_api_key",
            "api-key",
            "password",
            "token",
            "access_token",
            "refresh_token",
        }

        for key, value in data.items():
            if key.lower() in sensitive_keys:
                masked[key] = "***MASKED***"
            else:
                # Also apply redaction filter to header values
                if isinstance(value, str):
                    masked[key] = redact_secrets(value)
                else:
                    masked[key] = value

        return masked


def setup_logging():
    """Thiết lập cấu hình logging với structured fields"""

    # Remove default handler
    logger.remove()

    # Custom JSON formatter for structured logging with secret redaction
    def json_formatter(record):
        """Format log record as JSON with structured fields and secret redaction"""
        extra = record["extra"]

        # Redact message
        message = redact_secrets(str(record["message"]))

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": message,
            "app_env": settings.app_env,
        }
        # Merge extra fields (also redact string values)
        for key, value in extra.items():
            if isinstance(value, str):
                log_entry[key] = redact_secrets(value)
            else:
                log_entry[key] = value

        return json.dumps(log_entry) + "\n"

    # Custom format function with redaction for console
    def redacted_format(record):
        """Format with secret redaction for console output"""
        # Redact message before formatting
        record["message"] = redact_secrets(str(record["message"]))
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> - "
            "<level>{message}</level> | "
            "<dim>{extra}</dim>\n"
        )

    # Console handler với format đẹp cho dev
    if settings.app_env in ["local", "dev"]:
        logger.add(
            sink=sys.stdout,
            format=redacted_format,
            level=settings.log_level,
            colorize=True,
        )

    # File handler với format JSON cho production
    if settings.app_env == "prod":
        logger.add(
            sink="logs/app.log",
            format=json_formatter,
            level=settings.log_level,
            rotation="50 MB",
            retention="30 days",
            compression="zip",
        )

    # Request logs luôn ghi ra file JSONL với structured format
    logger.add(
        sink="logs/requests.jsonl",
        format=json_formatter,
        level="INFO",
        filter=lambda record: "trace_id" in record["extra"],
        rotation="100 MB",
        retention="7 days",
    )

    # Metrics logs (separate file for metrics analysis)
    logger.add(
        sink="logs/metrics.jsonl",
        format=json_formatter,
        level="INFO",
        filter=lambda record: "timing_breakdown" in record["extra"]
        or "event_type" in record["extra"],
        rotation="50 MB",
        retention="14 days",
    )

    logger.info(
        f"Logging initialized with secret redaction - Level: {settings.log_level}, Env: {settings.app_env}"
    )


# Convenience functions cho structured logging
def get_logger_with_trace(request: Request = None):
    """Lấy logger với trace_id từ request"""
    if request and hasattr(request.state, "trace_id"):
        extra = {
            "trace_id": request.state.trace_id,
            "request_id": getattr(request.state, "request_id", None),
            "user_id": request.headers.get("X-User-ID", "anonymous"),
        }
        return logger.bind(**extra)
    return logger


def log_timing(
    request: Request, step: str, duration_ms: float, metadata: Dict[str, Any] = None
):
    """Log timing for a specific step in the pipeline"""
    logger_ctx = get_logger_with_trace(request)
    timing_info = {
        "step": step,
        "duration_ms": duration_ms,
        "event_type": "timing",
    }
    if metadata:
        timing_info.update(metadata)
    logger_ctx.info(f"Timing: {step} took {duration_ms:.2f}ms", extra=timing_info)


def log_citations(request: Request, citations: list, query: str = None):
    """Log citations used in response"""
    logger_ctx = get_logger_with_trace(request)
    citation_info = {
        "citations": citations,
        "citations_count": len(citations),
        "query": query,
        "event_type": "citations",
    }
    logger_ctx.info(f"Citations: {len(citations)} sources used", extra=citation_info)


def log_error(request: Request, error: Exception, context: str = None):
    """Log error with context"""
    logger_ctx = get_logger_with_trace(request)
    error_info = {
        "error": str(error),
        "error_type": type(error).__name__,
        "context": context,
        "event_type": "error",
    }
    logger_ctx.error(f"Error in {context}: {type(error).__name__}", extra=error_info)


def get_structured_logger(name: str, component: str = None) -> Any:
    """Get structured logger with component binding."""
    extra_fields = {"component": component} if component else {}
    return logger.bind(**extra_fields)


def get_trace_id() -> str:
    """Get current trace ID from context (for compatibility)"""
    # This is a placeholder - in production, use contextvars or request.state
    return str(uuid.uuid4())
