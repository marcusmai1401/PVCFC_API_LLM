"""
Tests cho health endpoint
"""
import json
from datetime import datetime


def test_health_endpoint_returns_200(client):
    """Test health endpoint trả về status 200"""
    response = client.get("/healthz")
    assert response.status_code == 200


def test_health_endpoint_response_structure(client):
    """Test cấu trúc response của health endpoint"""
    response = client.get("/healthz")
    data = response.json()

    # Kiểm tra các field bắt buộc
    required_fields = {
        "status",
        "app_env",
        "version",
        "commit_sha",
        "uptime_seconds",
        "uptime_human",
        "llm_provider",
        "llm_provider_ready",
        "timestamp",
    }

    assert set(data.keys()) == required_fields


def test_health_endpoint_values(client, mock_env_vars):
    """Test values trong health endpoint response"""
    response = client.get("/healthz")
    data = response.json()

    assert data["status"] == "healthy"
    assert data["app_env"] in ["local", "dev", "prod"]
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0
    assert data["llm_provider"] in ["openai", "gemini", "none"]
    assert isinstance(data["llm_provider_ready"], bool)

    # Kiểm tra timestamp format
    timestamp = data["timestamp"]
    assert timestamp.endswith("Z")
    # Kiểm tra có parse được thành datetime không
    datetime.fromisoformat(timestamp.rstrip("Z"))


def test_health_endpoint_uptime_format(client):
    """Test format của uptime_human"""
    response = client.get("/healthz")
    data = response.json()

    uptime_human = data["uptime_human"]
    assert isinstance(uptime_human, str)
    assert len(uptime_human) > 0
    # Uptime phải có ít nhất "Xs" (X seconds)
    assert uptime_human.endswith("s")


def test_health_endpoint_has_trace_id(client):
    """Test health endpoint trả về X-Trace-ID header"""
    response = client.get("/healthz")

    assert "X-Trace-ID" in response.headers
    trace_id = response.headers["X-Trace-ID"]
    assert len(trace_id) > 0
    # UUID format check (có dấu gạch ngang)
    assert "-" in trace_id


def test_health_endpoint_with_llm_none(client, mock_env_vars):
    """Test health endpoint khi LLM_PROVIDER=none"""
    response = client.get("/healthz")
    data = response.json()

    assert data["llm_provider"] == "none"
    assert data["llm_provider_ready"] is False
