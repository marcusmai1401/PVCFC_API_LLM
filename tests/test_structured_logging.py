"""
Unit tests for Structured Logging System

Tests:
- StructuredLogger class and methods
- Log context management (trace_id, user_id, etc.)
- Context variables (ContextVar)
- JSON formatter
- Logger factory functions
- Configuration
"""

import json
import sys
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from app.core.structured_logging import (
    LogContext,
    StructuredLogger,
    get_health_logger,
    get_logger,
    get_metrics_logger,
    get_rag_logger,
    get_request_logger,
    get_security_logger,
    json_formatter,
    log_context,
    request_id_var,
    trace_id_var,
    user_id_var,
    user_role_var,
)


class TestStructuredLogger:
    """Test StructuredLogger class"""

    def test_logger_creation(self):
        """Test logger instance creation"""
        logger = StructuredLogger("test_logger")
        assert logger.name == "test_logger"
        assert logger._logger is not None

    def test_build_context_basic(self):
        """Test basic context building"""
        logger = StructuredLogger("test")
        context = logger._build_context()

        assert "logger" in context
        assert context["logger"] == "test"
        assert "timestamp" in context
        assert context["timestamp"].endswith("Z")

    def test_build_context_with_trace_id(self):
        """Test context with trace_id"""
        logger = StructuredLogger("test")

        # Set trace_id
        token = trace_id_var.set("trace_123")
        try:
            context = logger._build_context()
            assert context["trace_id"] == "trace_123"
        finally:
            trace_id_var.reset(token)

    def test_build_context_with_all_vars(self):
        """Test context with all context variables"""
        logger = StructuredLogger("test")

        # Set all context vars
        t1 = trace_id_var.set("trace_123")
        t2 = request_id_var.set("req_456")
        t3 = user_id_var.set("user_789")
        t4 = user_role_var.set("admin")

        try:
            context = logger._build_context()
            assert context["trace_id"] == "trace_123"
            assert context["request_id"] == "req_456"
            assert context["user_id"] == "user_789"
            assert context["user_role"] == "admin"
        finally:
            trace_id_var.reset(t1)
            request_id_var.reset(t2)
            user_id_var.reset(t3)
            user_role_var.reset(t4)

    def test_build_context_with_extra(self):
        """Test context with extra fields"""
        logger = StructuredLogger("test")
        extra = {"query": "test query", "count": 42}

        context = logger._build_context(extra)

        assert context["query"] == "test query"
        assert context["count"] == 42

    def test_info_logging(self):
        """Test info level logging"""
        logger = StructuredLogger("test")
        # Just verify method is callable (actual logging tested via loguru)
        logger.info("Test message")
        logger.info("Test with extra", extra={"key": "value"})

    def test_debug_logging(self):
        """Test debug level logging"""
        logger = StructuredLogger("test")
        logger.debug("Debug message")

    def test_warning_logging(self):
        """Test warning level logging"""
        logger = StructuredLogger("test")
        logger.warning("Warning message")

    def test_error_logging(self):
        """Test error level logging"""
        logger = StructuredLogger("test")
        logger.error("Error message")

    def test_critical_logging(self):
        """Test critical level logging"""
        logger = StructuredLogger("test")
        logger.critical("Critical message")

    def test_exception_logging(self):
        """Test exception logging"""
        logger = StructuredLogger("test")
        try:
            raise ValueError("Test error")
        except ValueError:
            logger.exception("Exception occurred")


class TestLogContext:
    """Test LogContext context manager"""

    def test_context_manager_basic(self):
        """Test basic context manager usage"""
        with log_context(trace_id="trace_123"):
            assert trace_id_var.get() == "trace_123"

        # Context should be reset after exit
        assert trace_id_var.get() is None

    def test_context_manager_all_fields(self):
        """Test context manager with all fields"""
        with log_context(
            trace_id="trace_123",
            request_id="req_456",
            user_id="user_789",
            user_role="admin",
        ):
            assert trace_id_var.get() == "trace_123"
            assert request_id_var.get() == "req_456"
            assert user_id_var.get() == "user_789"
            assert user_role_var.get() == "admin"

        # All should be reset
        assert trace_id_var.get() is None
        assert request_id_var.get() is None
        assert user_id_var.get() is None
        assert user_role_var.get() is None

    def test_context_manager_partial_fields(self):
        """Test context manager with partial fields"""
        with log_context(trace_id="trace_123", user_id="user_789"):
            assert trace_id_var.get() == "trace_123"
            assert request_id_var.get() is None
            assert user_id_var.get() == "user_789"
            assert user_role_var.get() is None

    def test_context_manager_nested(self):
        """Test nested context managers"""
        with log_context(trace_id="outer_trace"):
            assert trace_id_var.get() == "outer_trace"

            with log_context(trace_id="inner_trace"):
                assert trace_id_var.get() == "inner_trace"

            # Should revert to outer context
            assert trace_id_var.get() == "outer_trace"

        # Should be completely reset
        assert trace_id_var.get() is None

    def test_log_context_class_directly(self):
        """Test LogContext class directly"""
        ctx = LogContext(trace_id="trace_123", user_id="user_456")

        with ctx:
            assert trace_id_var.get() == "trace_123"
            assert user_id_var.get() == "user_456"

        assert trace_id_var.get() is None

    def test_context_with_exception(self):
        """Test context cleanup on exception"""
        try:
            with log_context(trace_id="trace_123"):
                assert trace_id_var.get() == "trace_123"
                raise ValueError("Test error")
        except ValueError:
            pass

        # Context should still be cleaned up
        assert trace_id_var.get() is None


class TestGetLoggerFunctions:
    """Test logger factory functions"""

    def test_get_logger(self):
        """Test generic get_logger"""
        logger = get_logger("test.module")
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "test.module"

    def test_get_request_logger(self):
        """Test request logger"""
        logger = get_request_logger()
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "app.request"

    def test_get_rag_logger(self):
        """Test RAG logger"""
        logger = get_rag_logger()
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "app.rag"

    def test_get_security_logger(self):
        """Test security logger"""
        logger = get_security_logger()
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "app.security"

    def test_get_health_logger(self):
        """Test health logger"""
        logger = get_health_logger()
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "app.health"

    def test_get_metrics_logger(self):
        """Test metrics logger"""
        logger = get_metrics_logger()
        assert isinstance(logger, StructuredLogger)
        assert logger.name == "app.metrics"


class TestJSONFormatter:
    """Test JSON formatter"""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting"""
        from datetime import datetime

        from loguru import logger as loguru_logger

        # Create a proper level object
        level_obj = type("Level", (), {"name": "INFO"})()

        record = {
            "time": datetime(2025, 10, 31, 10, 30, 0),
            "level": level_obj,
            "name": "test_logger",
            "message": "Test message",
            "function": "test_func",
            "line": 42,
            "extra": {},
            "exception": None,
        }

        result = json_formatter(record)
        data = json.loads(result.strip())

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test message"
        assert data["function"] == "test_func"
        assert data["line"] == 42

    def test_json_formatter_with_context(self):
        """Test JSON formatting with context"""
        from datetime import datetime

        level_obj = type("Level", (), {"name": "INFO"})()

        record = {
            "time": datetime(2025, 10, 31, 10, 30, 0),
            "level": level_obj,
            "name": "test_logger",
            "message": "Test message",
            "function": "test_func",
            "line": 42,
            "extra": {
                "trace_id": "trace_123",
                "request_id": "req_456",
                "user_id": "user_789",
                "custom_field": "custom_value",
            },
            "exception": None,
        }

        result = json_formatter(record)
        data = json.loads(result.strip())

        assert data["trace_id"] == "trace_123"
        assert data["request_id"] == "req_456"
        assert data["user_id"] == "user_789"
        assert data["context"]["custom_field"] == "custom_value"

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception"""
        from datetime import datetime

        level_obj = type("Level", (), {"name": "ERROR"})()

        # Create mock exception
        exc_type = ValueError
        exc_value = ValueError("Test error")

        mock_exception = Mock()
        mock_exception.type = exc_type
        mock_exception.value = exc_value
        mock_exception.traceback = "traceback here"

        record = {
            "time": datetime(2025, 10, 31, 10, 30, 0),
            "level": level_obj,
            "name": "test_logger",
            "message": "Error occurred",
            "function": "test_func",
            "line": 42,
            "extra": {},
            "exception": mock_exception,
        }

        result = json_formatter(record)
        data = json.loads(result.strip())

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "Test error" in data["exception"]["value"]


class TestIntegration:
    """Integration tests for structured logging"""

    def test_logger_with_context_integration(self):
        """Test logger with context integration"""
        logger = get_logger("integration_test")

        with log_context(trace_id="int_trace", user_id="int_user"):
            context = logger._build_context()
            assert context["trace_id"] == "int_trace"
            assert context["user_id"] == "int_user"

    def test_multiple_loggers_same_context(self):
        """Test multiple loggers share same context"""
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")

        with log_context(trace_id="shared_trace"):
            ctx1 = logger1._build_context()
            ctx2 = logger2._build_context()

            assert ctx1["trace_id"] == "shared_trace"
            assert ctx2["trace_id"] == "shared_trace"
            assert ctx1["logger"] == "logger1"
            assert ctx2["logger"] == "logger2"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
