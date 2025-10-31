"""
Integration tests for conversation flow with API.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_single_turn_backward_compatible():
    """Test that single-turn queries work without conversation_id"""
    # Skip if retriever is not initialized (local test env without indices)
    if not hasattr(app.state, "retriever") or app.state.retriever is None:
        pytest.skip("Retriever not initialized; skip integration test")
    response = client.post(
        "/ask",
        json={
            "query": "What is CO2 compressor?",
            "language": "en",
            "max_context": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should have answer
    assert "answer" in data
    assert len(data["answer"]) > 0

    # Should auto-create conversation_id
    assert "conversation_id" in data
    if data["conversation_id"]:
        # If conversation manager is available
        assert "is_new_conversation" in data
        assert data["is_new_conversation"] is True


def test_multi_turn_conversation():
    """Test multi-turn conversation flow"""
    # Skip if retriever is not initialized (local test env without indices)
    if not hasattr(app.state, "retriever") or app.state.retriever is None:
        pytest.skip("Retriever not initialized; skip integration test")
    # First turn - create conversation
    response1 = client.post(
        "/ask",
        json={
            "query": "What is K06101?",
            "language": "en",
            "max_context": 5,
        },
    )

    assert response1.status_code == 200
    data1 = response1.json()

    conv_id = data1.get("conversation_id")
    if not conv_id:
        pytest.skip("Conversation manager not available")

    assert data1.get("is_new_conversation") is True
    assert data1.get("conversation_turn_count", 0) >= 2

    # Second turn - continue conversation
    response2 = client.post(
        "/ask",
        json={
            "query": "What is its pressure?",  # Should infer "it" = K06101
            "conversation_id": conv_id,
            "language": "en",
            "max_context": 5,
        },
    )

    assert response2.status_code == 200
    data2 = response2.json()

    assert data2.get("conversation_id") == conv_id
    assert data2.get("is_new_conversation") is False
    assert data2.get("conversation_turn_count", 0) >= 4  # 2 + 2 more


def test_health_includes_redis():
    """Test that health endpoint includes conversation manager status"""
    response = client.get("/healthz")
    assert response.status_code == 200

    data = response.json()
    assert "conversation_manager" in data

    # Should have status (healthy, unhealthy, or not_configured)
    assert "status" in data["conversation_manager"]
