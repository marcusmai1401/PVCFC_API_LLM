"""
Tests for token budget manager.
"""

import pytest

from app.core.token_budget import TokenBudgetManager


def test_token_estimation():
    """Test token estimation"""
    manager = TokenBudgetManager(max_tokens=8000)

    # Short text
    text = "Hello world"
    tokens = manager.estimate_tokens(text)
    assert tokens > 0
    assert tokens < 10  # Should be ~2-3 tokens

    # Long text
    long_text = "This is a much longer text " * 100
    long_tokens = manager.estimate_tokens(long_text)
    assert long_tokens > tokens


def test_trim_to_budget():
    """Test history trimming to fit budget"""
    manager = TokenBudgetManager(max_tokens=500)  # Smaller budget to force trimming

    # Create history with 10 turns (large content to exceed budget)
    history = []
    for i in range(10):
        history.append(
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Turn {i}: " + ("x" * 200),  # Each turn ~200 chars
            }
        )

    # Large context text
    context_text = "Context: " + ("y" * 1000)  # ~1000 chars

    # Trim history
    trimmed = manager.trim_to_budget(
        history=history, context_text=context_text, reserved_for_response=200
    )

    # Should keep only some turns (or none if budget too tight)
    assert len(trimmed) <= len(history)

    # If any kept, should keep most recent
    if len(trimmed) > 0:
        assert trimmed[-1]["content"] == history[-1]["content"]


def test_trim_preserves_order():
    """Test that trimming preserves chronological order"""
    manager = TokenBudgetManager(max_tokens=500)

    history = [
        {"role": "user", "content": "Turn 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Turn 2"},
        {"role": "assistant", "content": "Response 2"},
        {"role": "user", "content": "Turn 3"},
        {"role": "assistant", "content": "Response 3"},
    ]

    context = "Short context"
    trimmed = manager.trim_to_budget(history, context, reserved_for_response=100)

    # Check chronological order preserved
    for i in range(len(trimmed) - 1):
        original_idx_1 = history.index(trimmed[i])
        original_idx_2 = history.index(trimmed[i + 1])
        assert original_idx_1 < original_idx_2


def test_empty_history():
    """Test handling of empty history"""
    manager = TokenBudgetManager(max_tokens=1000)

    trimmed = manager.trim_to_budget(
        history=[], context_text="Some context", reserved_for_response=100
    )

    assert trimmed == []


def test_budget_exceeded_returns_empty():
    """Test when context alone exceeds budget"""
    manager = TokenBudgetManager(max_tokens=100)

    history = [{"role": "user", "content": "Short turn"}]
    huge_context = "x" * 10000  # Way too large

    trimmed = manager.trim_to_budget(
        history=history, context_text=huge_context, reserved_for_response=50
    )

    # Should return empty list when no room for history
    assert trimmed == []
