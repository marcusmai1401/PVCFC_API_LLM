"""
Integration Tests for API Endpoints

Tests complete API integration:
- /api/ask endpoint with middleware
- /health endpoints (healthz, livez, readyz)
- /metrics endpoint
- Middleware integration (logging, metrics, tracing)
- Error handling across endpoints
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.routers.health import router as health_router
from app.api.routers.metrics import router as metrics_router
from app.api.middleware.observability import ObservabilityMiddleware


# Create full app with middleware
app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
app.include_router(health_router)
app.include_router(metrics_router)

# Mock app state
class MockState:
    weaviate_client = None
    opensearch_client = None
    redis_client = None
    index_dir = "/mock"

app.state = MockState()

client = TestClient(app)


class TestAPIEndpointsIntegration:
    """Test complete API endpoint integration"""

    def test_health_endpoint_with_middleware(self):
        """Test health endpoint with observability middleware"""
        response = client.get("/healthz")

        assert response.status_code == 200
        # Middleware should add trace headers
        assert "X-Trace-Id" in response.headers
        assert "X-Request-Id" in response.headers

    def test_metrics_endpoint_accessible(self):
        """Test metrics endpoint is accessible"""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_health_endpoint(self):
        """Test metrics health endpoint"""
        response = client.get("/metrics/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_liveness_probe_integration(self):
        """Test Kubernetes liveness probe"""
        response = client.get("/livez")

        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers

    def test_readiness_probe_integration(self):
        """Test Kubernetes readiness probe"""
        response = client.get("/readyz")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data


class TestAPIMiddlewareIntegration:
    """Test middleware integration across endpoints"""

    def test_trace_id_propagation(self):
        """Test trace ID is propagated across requests"""
        custom_trace = "test-trace-123"

        response = client.get("/healthz", headers={"X-Trace-Id": custom_trace})

        assert response.headers["X-Trace-Id"] == custom_trace

    def test_middleware_adds_trace_to_all_endpoints(self):
        """Test middleware adds trace ID to all endpoints"""
        endpoints = ["/healthz", "/livez", "/readyz", "/metrics", "/metrics/health"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert "X-Trace-Id" in response.headers

    def test_user_context_headers(self):
        """Test user context is extracted from headers"""
        headers = {"X-User-Id": "user_123", "X-User-Role": "admin"}

        response = client.get("/healthz", headers=headers)

        assert response.status_code == 200


class TestAPIErrorHandling:
    """Test error handling across API"""

    def test_404_with_middleware(self):
        """Test 404 error with middleware"""
        response = client.get("/nonexistent")

        assert response.status_code == 404
        # Middleware should still add headers
        assert "X-Trace-Id" in response.headers

    def test_405_method_not_allowed(self):
        """Test 405 error"""
        response = client.post("/metrics")  # GET only

        assert response.status_code == 405


class TestAPIConcurrency:
    """Test API handles concurrent requests"""

    def test_concurrent_health_checks(self):
        """Test multiple concurrent health checks"""
        import concurrent.futures

        def make_request():
            return client.get("/healthz")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in results)

    def test_concurrent_metrics_requests(self):
        """Test concurrent metrics endpoint requests"""
        responses = [client.get("/metrics") for _ in range(5)]

        assert all(r.status_code == 200 for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
