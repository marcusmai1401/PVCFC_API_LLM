"""
Structured Logging System for PVCFC RAG API

Provides:
- JSON-formatted logs
- Contextual logging (trace_id, user_id, request_id)
- Log level management
- Integration with existing loguru setup
- ELK/Splunk compatible format

Usage:
    from app.core.structured_logging import get_logger, log_context
    
    # Get logger with context
    logger = get_logger(__name__)
    
    # Use context manager for request tracking
    with log_context(trace_id="req_123", user_id="user_456"):
        logger.info("Processing request", extra={"query": "test"})
"""

import contextvars
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

# Context variables for request tracking
trace_id_var = contextvars.ContextVar("trace_id", default=None)
request_id_var = contextvars.ContextVar("request_id", default=None)
user_id_var = contextvars.ContextVar("user_id", default=None)
user_role_var = contextvars.ContextVar("user_role", default=None)


class StructuredLogger:
    """
    Structured logging wrapper for loguru

    Automatically adds context (trace_id, user_id, etc.) to all log messages.
    Formats logs as JSON for machine parsing.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger

        Args:
            name: Logger name (usually __name__)
        """
        self.name = name
        self._logger = logger.bind(logger_name=name)

    def _build_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build log context with current contextual information"""
        context = {
            "logger": self.name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Add context variables if available
        trace_id = trace_id_var.get()
        if trace_id:
            context["trace_id"] = trace_id

        request_id = request_id_var.get()
        if request_id:
            context["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            context["user_id"] = user_id

        user_role = user_role_var.get()
        if user_role:
            context["user_role"] = user_role

        # Merge with extra fields
        if extra:
            context.update(extra)

        return context

    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        context = self._build_context(kwargs.get("extra"))
        self._logger.debug(message, **context)

    def info(self, message: str, **kwargs):
        """Log info message with context"""
        context = self._build_context(kwargs.get("extra"))
        self._logger.info(message, **context)

    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        context = self._build_context(kwargs.get("extra"))
        self._logger.warning(message, **context)

    def error(self, message: str, **kwargs):
        """Log error message with context"""
        context = self._build_context(kwargs.get("extra"))
        self._logger.error(message, **context)

    def critical(self, message: str, **kwargs):
        """Log critical message with context"""
        context = self._build_context(kwargs.get("extra"))
        self._logger.critical(message, **context)

    def exception(self, message: str, **kwargs):
        """Log exception with context and traceback"""
        context = self._build_context(kwargs.get("extra"))
        self._logger.exception(message, **context)


def get_logger(name: str) -> StructuredLogger:
    """
    Get structured logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


class LogContext:
    """
    Context manager for setting log context

    Usage:
        with log_context(trace_id="req_123", user_id="user_456"):
            logger.info("Processing request")
    """

    def __init__(
        self,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
    ):
        """
        Initialize log context

        Args:
            trace_id: Trace ID for request tracing
            request_id: Request ID for correlation
            user_id: User identifier
            user_role: User role (guest, user, admin)
        """
        self.trace_id = trace_id
        self.request_id = request_id
        self.user_id = user_id
        self.user_role = user_role
        self.tokens = []

    def __enter__(self):
        """Set context variables"""
        if self.trace_id:
            self.tokens.append(trace_id_var.set(self.trace_id))
        if self.request_id:
            self.tokens.append(request_id_var.set(self.request_id))
        if self.user_id:
            self.tokens.append(user_id_var.set(self.user_id))
        if self.user_role:
            self.tokens.append(user_role_var.set(self.user_role))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset context variables"""
        for token in self.tokens:
            token.var.reset(token)


def log_context(
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
) -> LogContext:
    """
    Create log context manager

    Args:
        trace_id: Trace ID for request tracing
        request_id: Request ID for correlation
        user_id: User identifier
        user_role: User role

    Returns:
        LogContext instance
    """
    return LogContext(trace_id, request_id, user_id, user_role)


def json_formatter(record: dict) -> str:
    """
    Format log record as JSON

    Args:
        record: Loguru record dict

    Returns:
        JSON-formatted log string
    """
    # Extract core fields
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add context if available
    extra = record.get("extra", {})
    if extra:
        # Add trace_id, request_id, user_id if present
        for key in ["trace_id", "request_id", "user_id", "user_role", "logger_name"]:
            if key in extra:
                log_entry[key] = extra[key]

        # Add other extra fields under 'context'
        context = {k: v for k, v in extra.items() if k not in log_entry}
        if context:
            log_entry["context"] = context

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": str(record["exception"].type.__name__),
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback,
        }

    return json.dumps(log_entry) + "\n"


def configure_structured_logging(
    json_output: bool = True,
    log_file: Optional[str] = None,
    log_level: str = "INFO",
    rotation: str = "100 MB",
    retention: str = "30 days",
):
    """
    Configure structured logging system

    Args:
        json_output: Whether to use JSON format (vs human-readable)
        log_file: Path to log file (None for stdout only)
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        rotation: Log rotation setting (e.g., "100 MB", "1 day")
        retention: Log retention period (e.g., "30 days", "1 week")
    """
    # Remove default logger
    logger.remove()

    # Console output (human-readable or JSON)
    if json_output:
        logger.add(
            sys.stdout,
            format=json_formatter,
            level=log_level,
            colorize=False,
        )
    else:
        # Human-readable format for development
        logger.add(
            sys.stdout,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{extra[trace_id]}</cyan> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=log_level,
            colorize=True,
        )

    # File output (always JSON for machine parsing)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=json_formatter,
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression="gz",
            serialize=False,
        )

    logger.info(
        f"Structured logging configured: json={json_output}, level={log_level}, file={log_file}"
    )


# Pre-configured loggers for common use cases
def get_request_logger() -> StructuredLogger:
    """Get logger for HTTP request handling"""
    return get_logger("app.request")


def get_rag_logger() -> StructuredLogger:
    """Get logger for RAG pipeline"""
    return get_logger("app.rag")


def get_security_logger() -> StructuredLogger:
    """Get logger for security events"""
    return get_logger("app.security")


def get_health_logger() -> StructuredLogger:
    """Get logger for health checks"""
    return get_logger("app.health")


def get_metrics_logger() -> StructuredLogger:
    """Get logger for metrics collection"""
    return get_logger("app.metrics")
