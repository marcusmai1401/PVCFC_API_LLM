"""
Tests for the health checker system

Validates:
- Component health checks
- Overall status aggregation
- Liveness vs readiness probes
- Graceful degradation
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.core.health_checker import ComponentHealth, HealthChecker, HealthStatus


@pytest.fixture
def mock_app_state():
    """Mock FastAPI app state with all components"""
    state = Mock()

    # Mock Weaviate retriever
    weaviate_retriever = Mock()
    weaviate_retriever.health_check.return_value = {
        "status": "healthy",
        "collection": "test_collection",
        "ready": True,
    }
    state.weaviate_retriever = weaviate_retriever

    # Mock OpenSearch retriever
    opensearch_retriever = Mock()
    opensearch_retriever.health_check.return_value = {
        "status": "healthy",
        "index": "test_index",
        "cluster_health": "green",
    }
    state.opensearch_retriever = opensearch_retriever

    # Mock conversation manager (Redis)
    conversation_manager = Mock()
    conversation_manager.health_check.return_value = {
        "status": "healthy",
        "total_conversations": 42,
        "ttl_hours": 24,
    }
    state.conversation_manager = conversation_manager

    return state


@pytest.fixture
def health_checker(mock_app_state):
    """Create health checker with mocked state"""
    return HealthChecker(mock_app_state)


@pytest.mark.asyncio
async def test_liveness_check(health_checker):
    """Liveness check should always succeed (quick check)"""
    result = await health_checker.check_all(check_type="liveness")

    assert result["status"] == "healthy"
    assert result["type"] == "liveness"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_readiness_check_all_healthy(health_checker):
    """Readiness check with all components healthy"""
    result = await health_checker.check_all(check_type="readiness")

    assert result["status"] == "healthy"
    assert result["type"] == "readiness"
    assert "check_duration_ms" in result
    assert "components" in result

    # Should have all 4 components
    components = result["components"]
    assert len(components) == 4

    component_names = {c["name"] for c in components}
    assert component_names == {"weaviate", "opensearch", "redis", "filesystem"}

    # All should be healthy
    for component in components:
        assert component["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_check_weaviate_unhealthy(health_checker):
    """Readiness check with Weaviate down"""
    # Make Weaviate unhealthy
    health_checker.app_state.weaviate_retriever.health_check.return_value = {
        "status": "unhealthy",
        "error": "Connection refused",
    }

    result = await health_checker.check_all(check_type="readiness")

    # System should be degraded (only 1/4 unhealthy)
    assert result["status"] == "degraded"

    # Find Weaviate component
    weaviate = next(c for c in result["components"] if c["name"] == "weaviate")
    assert weaviate["status"] == "unhealthy"
    assert "error" in weaviate["message"].lower()


@pytest.mark.asyncio
async def test_readiness_check_multiple_unhealthy(health_checker):
    """Readiness check with multiple components down"""
    # Make Weaviate and OpenSearch unhealthy
    health_checker.app_state.weaviate_retriever.health_check.return_value = {
        "status": "unhealthy",
        "error": "Connection refused",
    }
    health_checker.app_state.opensearch_retriever.health_check.return_value = {
        "status": "unhealthy",
        "error": "Index not found",
    }

    result = await health_checker.check_all(check_type="readiness")

    # System should be degraded (2/4 unhealthy)
    assert result["status"] == "degraded"

    # Count unhealthy components
    unhealthy_count = sum(1 for c in result["components"] if c["status"] == "unhealthy")
    assert unhealthy_count == 2


@pytest.mark.asyncio
async def test_readiness_check_majority_unhealthy(health_checker):
    """Readiness check with majority of components down"""
    # Make 3 out of 4 components unhealthy
    health_checker.app_state.weaviate_retriever.health_check.return_value = {
        "status": "unhealthy",
        "error": "Connection refused",
    }
    health_checker.app_state.opensearch_retriever.health_check.return_value = {
        "status": "unhealthy",
        "error": "Index not found",
    }
    health_checker.app_state.conversation_manager.health_check.return_value = {
        "status": "unhealthy",
        "error": "Redis connection timeout",
    }

    result = await health_checker.check_all(check_type="readiness")

    # System should be UNHEALTHY (>50% unhealthy)
    assert result["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_weaviate_health_check_disabled(health_checker):
    """Weaviate health check when disabled in settings"""
    with patch("app.core.health_checker.settings") as mock_settings:
        mock_settings.weaviate_enabled = False

        result = await health_checker.check_weaviate()

        assert result.name == "weaviate"
        assert result.status == HealthStatus.DEGRADED
        assert "disabled" in result.message.lower()


@pytest.mark.asyncio
async def test_weaviate_health_check_not_initialized(health_checker):
    """Weaviate health check when retriever not initialized"""
    health_checker.app_state.weaviate_retriever = None

    result = await health_checker.check_weaviate()

    assert result.name == "weaviate"
    assert result.status == HealthStatus.DEGRADED
    assert "not initialized" in result.message.lower()


@pytest.mark.asyncio
async def test_weaviate_health_check_exception(health_checker):
    """Weaviate health check with exception"""
    health_checker.app_state.weaviate_retriever.health_check.side_effect = Exception(
        "Connection timeout"
    )

    result = await health_checker.check_weaviate()

    assert result.name == "weaviate"
    assert result.status == HealthStatus.UNHEALTHY
    assert result.latency_ms is not None
    assert "timeout" in result.message.lower()


@pytest.mark.asyncio
async def test_opensearch_health_check_fallback(health_checker):
    """OpenSearch health check fallback to client.info()"""
    # Remove health_check method to trigger fallback
    del health_checker.app_state.opensearch_retriever.health_check

    # Mock client.info()
    mock_client = Mock()
    mock_client.info.return_value = {"version": {"number": "2.11.0"}}
    health_checker.app_state.opensearch_retriever.client = mock_client

    result = await health_checker.check_opensearch()

    assert result.name == "opensearch"
    assert result.status == HealthStatus.HEALTHY
    assert result.metadata["version"] == "2.11.0"


@pytest.mark.asyncio
async def test_redis_health_check_not_initialized(health_checker):
    """Redis health check when conversation manager not initialized"""
    health_checker.app_state.conversation_manager = None

    result = await health_checker.check_redis()

    assert result.name == "redis"
    assert result.status == HealthStatus.DEGRADED
    assert "not initialized" in result.message.lower()


@pytest.mark.asyncio
async def test_filesystem_health_check(health_checker):
    """Filesystem health check with paths"""
    with patch("app.core.health_checker.settings") as mock_settings:
        mock_settings.index_dir = "/tmp/test_index"
        mock_settings.artifacts_dir = "/tmp/test_artifacts"

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            result = await health_checker.check_filesystem()

            assert result.name == "filesystem"
            assert result.status == HealthStatus.HEALTHY
            assert result.metadata["checked_paths"] == 2


@pytest.mark.asyncio
async def test_filesystem_health_check_missing_paths(health_checker):
    """Filesystem health check with missing paths"""
    with patch("app.core.health_checker.settings") as mock_settings:
        mock_settings.index_dir = "/tmp/test_index"
        mock_settings.artifacts_dir = "/tmp/test_artifacts"

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            result = await health_checker.check_filesystem()

            assert result.name == "filesystem"
            assert result.status == HealthStatus.DEGRADED
            assert "missing" in result.message.lower()
            assert result.metadata["missing_count"] == 2


@pytest.mark.asyncio
async def test_component_health_latency_tracking(health_checker):
    """All components should track latency"""
    result = await health_checker.check_all(check_type="readiness")

    for component in result["components"]:
        assert component["latency_ms"] is not None
        assert component["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_parallel_health_checks(health_checker):
    """Health checks should run in parallel"""

    # Add artificial delays to check parallelism
    async def slow_check(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"status": "healthy"}

    health_checker.app_state.weaviate_retriever.health_check = slow_check
    health_checker.app_state.opensearch_retriever.health_check = slow_check
    health_checker.app_state.conversation_manager.health_check = slow_check

    import time

    start = time.time()
    result = await health_checker.check_all(check_type="readiness")
    duration = time.time() - start

    # If parallel, should take ~100ms, not 300ms+
    # (We have 3 slow checks + 1 fast check)
    assert duration < 0.3  # Should be much faster than serial execution
    assert result["status"] in ["healthy", "degraded", "unhealthy"]


@pytest.mark.asyncio
async def test_health_check_exception_handling(health_checker):
    """Health checker should handle exceptions gracefully"""

    async def failing_check():
        raise RuntimeError("Simulated failure")

    # Patch one of the check methods to raise exception
    with patch.object(
        health_checker, "check_weaviate", side_effect=failing_check
    ) as mock_check:
        result = await health_checker.check_all(check_type="readiness")

        # Should still return a result, not crash
        assert "status" in result
        assert "components" in result

        # The failed component should be marked as unhealthy
        # (exception is caught by asyncio.gather with return_exceptions=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
