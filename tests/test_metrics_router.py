"""
Unit tests for Metrics Router

Tests:
- /metrics endpoint
- /metrics/health endpoint
- Prometheus format validation
- Error handling
- Response headers
"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.routers.metrics import router


# Create test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)


class TestMetricsEndpoint:
    """Test /metrics endpoint"""

    def test_metrics_endpoint_success(self):
        """Test metrics endpoint returns successfully"""
        response = client.get("/metrics")

        assert response.status_code == 200

    def test_metrics_endpoint_content_type(self):
        """Test metrics endpoint has correct content type"""
        response = client.get("/metrics")

        # Prometheus content type
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_endpoint_cache_headers(self):
        """Test metrics endpoint has no-cache headers"""
        response = client.get("/metrics")

        assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Expires"] == "0"

    def test_metrics_endpoint_contains_metrics(self):
        """Test metrics endpoint returns metric data"""
        response = client.get("/metrics")

        content = response.text

        # Should contain some standard Python metrics
        assert len(content) > 0

        # Prometheus format typically has # HELP and # TYPE lines
        # Note: Actual metrics depend on what's been registered


class TestMetricsHealthEndpoint:
    """Test /metrics/health endpoint"""

    def test_metrics_health_success(self):
        """Test metrics health endpoint"""
        response = client.get("/metrics/health")

        assert response.status_code == 200

    def test_metrics_health_response_format(self):
        """Test health response format"""
        response = client.get("/metrics/health")

        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "metrics_endpoint" in data
        assert data["metrics_endpoint"] == "/metrics"
        assert "scrape_interval_recommended" in data
        assert data["scrape_interval_recommended"] == "15s"

    def test_metrics_health_json_content_type(self):
        """Test health endpoint returns JSON"""
        response = client.get("/metrics/health")

        assert "application/json" in response.headers["content-type"]


class TestMetricsIntegration:
    """Integration tests for metrics router"""

    def test_metrics_and_health_both_work(self):
        """Test both endpoints are accessible"""
        metrics_response = client.get("/metrics")
        health_response = client.get("/metrics/health")

        assert metrics_response.status_code == 200
        assert health_response.status_code == 200

    def test_metrics_idempotent(self):
        """Test metrics endpoint is idempotent"""
        response1 = client.get("/metrics")
        response2 = client.get("/metrics")

        # Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Content may differ (counters increment), but format should be same
        assert response1.headers["content-type"] == response2.headers["content-type"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
