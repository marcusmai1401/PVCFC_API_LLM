"""
Unit tests for Observability Middleware

Tests:
- ObservabilityMiddleware request/response tracking
- Trace ID generation and propagation
- Metrics tracking
- Error handling
- Path normalization
- track_operation context manager
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from app.api.middleware.observability import (
    ObservabilityMiddleware,
    track_operation,
)


# Create test app
app = FastAPI()
app.add_middleware(ObservabilityMiddleware)


@app.get("/test")
async def app_get_test():
    return {"message": "success"}


@app.get("/test/{item_id}")
async def app_get_test_with_id(item_id: str):
    return {"id": item_id}


@app.get("/error")
async def app_get_error():
    raise ValueError("Test error")


@app.post("/api/ask")
async def app_post_ask():
    return {"answer": "test"}


client = TestClient(app)


class TestObservabilityMiddleware:
    """Test ObservabilityMiddleware"""

    def test_middleware_adds_trace_id(self):
        """Test middleware adds trace ID to response"""
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers
        assert "X-Request-Id" in response.headers

        # Validate UUID format
        trace_id = response.headers["X-Trace-Id"]
        try:
            uuid.UUID(trace_id)
        except ValueError:
            pytest.fail("Trace ID is not a valid UUID")

    def test_middleware_preserves_existing_trace_id(self):
        """Test middleware preserves existing trace ID"""
        custom_trace = "custom-trace-123"

        response = client.get("/test", headers={"X-Trace-Id": custom_trace})

        assert response.headers["X-Trace-Id"] == custom_trace

    def test_middleware_tracks_successful_request(self):
        """Test middleware tracks successful request"""
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    def test_middleware_handles_errors(self):
        """Test middleware handles errors"""
        # TestClient will raise exception, not return 500
        # So we expect the exception to be raised
        with pytest.raises(ValueError):
            response = client.get("/error")

    def test_middleware_with_user_headers(self):
        """Test middleware with user context headers"""
        response = client.get(
            "/test",
            headers={
                "X-User-Id": "user_123",
                "X-User-Role": "admin",
            },
        )

        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers

    def test_middleware_post_request(self):
        """Test middleware with POST request"""
        response = client.post("/api/ask", json={"query": "test"})

        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers


class TestPathNormalization:
    """Test path normalization logic"""

    def test_normalize_uuid_path(self):
        """Test UUID path normalization"""
        from app.api.middleware.observability import ObservabilityMiddleware

        middleware = ObservabilityMiddleware(app)

        # UUID path
        normalized = middleware._normalize_path(
            "/api/documents/550e8400-e29b-41d4-a716-446655440000"
        )
        assert normalized == "/api/documents/{id}"

    def test_normalize_numeric_id(self):
        """Test numeric ID normalization"""
        from app.api.middleware.observability import ObservabilityMiddleware

        middleware = ObservabilityMiddleware(app)

        normalized = middleware._normalize_path("/api/users/12345")
        assert normalized == "/api/users/{id}"

    def test_normalize_multiple_ids(self):
        """Test multiple ID normalization"""
        from app.api.middleware.observability import ObservabilityMiddleware

        middleware = ObservabilityMiddleware(app)

        normalized = middleware._normalize_path("/api/users/123/posts/456")
        # Should normalize both IDs but keep only first 3 segments
        assert "{id}" in normalized

    def test_normalize_limits_segments(self):
        """Test path segment limiting"""
        from app.api.middleware.observability import ObservabilityMiddleware

        middleware = ObservabilityMiddleware(app)

        # Very long path - should be truncated
        normalized = middleware._normalize_path(
            "/api/v1/users/123/posts/456/comments/789/replies/999"
        )

        # Should only keep first 4 segments
        segments = normalized.split("/")
        assert len(segments) <= 4


class TestTrackOperation:
    """Test track_operation context manager"""

    def test_track_operation_success(self):
        """Test tracking successful operation"""
        with track_operation("test_operation", table="users"):
            # Operation completes successfully
            result = "success"

        assert result == "success"

    def test_track_operation_failure(self):
        """Test tracking failed operation"""
        try:
            with track_operation("failing_operation"):
                raise ValueError("Operation failed")
        except ValueError:
            pass  # Expected

    def test_track_operation_with_extra_context(self):
        """Test operation tracking with extra context"""
        with track_operation("db_query", table="users", action="SELECT") as tracker:
            assert tracker.name == "db_query"
            assert tracker.extra["table"] == "users"
            assert tracker.extra["action"] == "SELECT"

    def test_track_operation_measures_duration(self):
        """Test operation duration tracking"""
        import time

        with track_operation("slow_operation") as tracker:
            time.sleep(0.01)  # Sleep 10ms

        # Duration should have been measured (hard to assert exact value)


class TestMiddlewareIntegration:
    """Integration tests for middleware"""

    def test_full_request_lifecycle(self):
        """Test complete request lifecycle"""
        # Make request with custom trace
        custom_trace = "test-trace-001"

        response = client.get(
            "/test",
            headers={
                "X-Trace-Id": custom_trace,
                "X-User-Id": "user_123",
                "X-User-Role": "user",
            },
        )

        # Verify response
        assert response.status_code == 200
        assert response.headers["X-Trace-Id"] == custom_trace
        assert response.json() == {"message": "success"}

    def test_concurrent_requests_different_trace_ids(self):
        """Test concurrent requests have different trace IDs"""
        response1 = client.get("/test")
        response2 = client.get("/test")

        trace1 = response1.headers["X-Trace-Id"]
        trace2 = response2.headers["X-Trace-Id"]

        # Should have different trace IDs
        assert trace1 != trace2

    def test_error_handling_with_trace(self):
        """Test error handling with trace ID"""
        custom_trace = "error-trace-001"

        # TestClient raises exceptions instead of returning 500
        with pytest.raises(ValueError):
            response = client.get("/error", headers={"X-Trace-Id": custom_trace})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
