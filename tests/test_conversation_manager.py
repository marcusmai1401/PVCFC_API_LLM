"""
Tests for conversation manager.
"""

import time

import pytest

from app.core.conversation.manager import ConversationManager, ConversationTurn


@pytest.fixture
def conv_manager():
    """Create conversation manager for testing"""
    try:
        manager = ConversationManager(
            redis_url="redis://localhost:6379",
            ttl_hours=1,  # Short TTL for testing
            max_turns_per_conversation=10,
        )
        # Test connection
        health = manager.health_check()
        if health["status"] != "healthy":
            pytest.skip("Redis not available")
        yield manager
        # Cleanup - no specific cleanup needed, TTL will handle it
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


def test_create_conversation(conv_manager):
    """Test conversation creation"""
    conv_id = conv_manager.create_conversation(user_id="test_user", language="vi")
    assert conv_id is not None
    assert len(conv_id) > 0

    # Get metadata
    meta = conv_manager.get_metadata(conv_id)
    assert meta is not None
    assert meta["user_id"] == "test_user"
    assert meta["language"] == "vi"
    assert meta["total_turns"] == 0

    # Cleanup
    conv_manager.clear_conversation(conv_id)


def test_add_turns(conv_manager):
    """Test adding turns to conversation"""
    conv_id = conv_manager.create_conversation()

    # Add user turn
    success = conv_manager.add_turn(
        conv_id, role="user", content="What is K06101 pressure?"
    )
    assert success

    # Add assistant turn
    success = conv_manager.add_turn(
        conv_id,
        role="assistant",
        content="K06101 operating pressure is 15 bar",
        metadata={"model": "gemini-2.5-pro", "confidence": 0.95},
    )
    assert success

    # Get history
    history = conv_manager.get_history(conv_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert "K06101" in history[0]["content"]

    # Cleanup
    conv_manager.clear_conversation(conv_id)


def test_history_limit(conv_manager):
    """Test max_turns limit enforcement"""
    conv_id = conv_manager.create_conversation()

    # Add 15 turns (exceeds max of 10)
    for i in range(15):
        conv_manager.add_turn(
            conv_id, role="user" if i % 2 == 0 else "assistant", content=f"Turn {i}"
        )

    # Should only keep last 10 turns
    history = conv_manager.get_history(conv_id)
    assert len(history) == 10
    assert "Turn 5" in history[0]["content"]  # Oldest kept
    assert "Turn 14" in history[-1]["content"]  # Newest

    # Cleanup
    conv_manager.clear_conversation(conv_id)


def test_build_llm_history(conv_manager):
    """Test LLM history formatting"""
    conv_id = conv_manager.create_conversation()

    conv_manager.add_turn(conv_id, role="user", content="Hello")
    conv_manager.add_turn(conv_id, role="assistant", content="Hi there")

    # OpenAI format
    openai_history = conv_manager.build_llm_history(conv_id, format="openai")
    assert len(openai_history) == 2
    assert openai_history[0]["role"] == "user"
    assert openai_history[1]["role"] == "assistant"
    assert openai_history[0]["content"] == "Hello"

    # Gemini format
    gemini_history = conv_manager.build_llm_history(conv_id, format="gemini")
    assert len(gemini_history) == 2
    assert gemini_history[0]["role"] == "user"
    assert gemini_history[1]["role"] == "model"  # Gemini uses "model"
    assert gemini_history[0]["parts"] == ["Hello"]

    # Cleanup
    conv_manager.clear_conversation(conv_id)


def test_health_check(conv_manager):
    """Test health check"""
    health = conv_manager.health_check()
    assert health["status"] == "healthy"
    assert health["redis_connected"] is True
    assert "total_conversations" in health


def test_concurrent_add_turns_no_race_condition(conv_manager):
    """
    Test that concurrent add_turn calls don't cause race conditions.

    BUG-004 FIX VERIFICATION:
    This test verifies that the Lua script atomic implementation prevents:
    - Turn count corruption
    - Lost turns
    - TTL race conditions

    Previously, 4 separate Redis operations could interleave, causing incorrect
    total_turns counts. Now with atomic Lua script, all concurrent operations
    should produce correct results.
    """
    import threading
    import time

    conv_id = conv_manager.create_conversation(user_id="concurrent_test")

    # Track successful additions
    success_count = {"count": 0}
    lock = threading.Lock()

    def add_turns_batch(thread_id, num_turns=10):
        """Add multiple turns from a thread"""
        for i in range(num_turns):
            success = conv_manager.add_turn(
                conv_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Thread {thread_id}, Turn {i}",
                metadata={"thread_id": thread_id, "turn_index": i},
            )
            if success:
                with lock:
                    success_count["count"] += 1
            # Small random delay to increase race condition likelihood
            time.sleep(0.001)

    # Spawn 5 threads, each adding 10 turns = 50 total
    num_threads = 5
    turns_per_thread = 10
    expected_total = num_threads * turns_per_thread

    threads = [
        threading.Thread(target=add_turns_batch, args=(i, turns_per_thread))
        for i in range(num_threads)
    ]

    # Start all threads simultaneously
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join(timeout=10)

    # Verify results
    # 1. All additions succeeded
    assert (
        success_count["count"] == expected_total
    ), f"Expected {expected_total} successful adds, got {success_count['count']}"

    # 2. History has correct length (respecting max_turns=10 limit)
    history = conv_manager.get_history(conv_id)
    expected_length = min(expected_total, conv_manager.max_turns)
    assert (
        len(history) == expected_length
    ), f"Expected history length {expected_length}, got {len(history)}"

    # 3. Metadata total_turns matches history length
    meta = conv_manager.get_metadata(conv_id)
    assert meta is not None, "Metadata should exist"
    assert (
        meta["total_turns"] == expected_length
    ), f"Metadata total_turns should be {expected_length}, got {meta['total_turns']}"

    # 4. No duplicate turns (all turns have unique content)
    contents = [turn["content"] for turn in history]
    # With trimming, we keep last N turns, so check uniqueness of kept turns
    assert len(contents) == len(
        set(contents)
    ), "History should not have duplicate turns (race condition indicator)"

    # Cleanup
    conv_manager.clear_conversation(conv_id)

    print(
        f"✅ Race condition test passed: {expected_total} concurrent additions handled correctly"
    )
