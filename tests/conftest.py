"""
Pytest configuration và fixtures
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """FastAPI test client"""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables cho testing"""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("VERSION", "test-version")
    monkeypatch.setenv("COMMIT_SHA", "test-commit-sha")
