"""
Tests for conversation summarizer.
"""

import pytest

from app.core.conversation.summarizer import ConversationSummarizer


def test_should_summarize_logic():
    """Test summarization trigger logic"""
    summarizer = ConversationSummarizer(summarize_every_n_turns=8)

    # Not time to summarize yet
    assert not summarizer.should_summarize(turn_count=5, last_summarized_turn=0)
    assert not summarizer.should_summarize(turn_count=7, last_summarized_turn=0)

    # Time to summarize
    assert summarizer.should_summarize(turn_count=8, last_summarized_turn=0)
    assert summarizer.should_summarize(turn_count=10, last_summarized_turn=0)

    # Already summarized recently
    assert not summarizer.should_summarize(turn_count=12, last_summarized_turn=10)

    # Time for next summarization
    assert summarizer.should_summarize(turn_count=18, last_summarized_turn=10)


def test_create_summary_turn():
    """Test creating a summary turn"""
    summarizer = ConversationSummarizer()

    summary = "User asked about K06101, I explained it's a CO2 compressor."
    turn = summarizer.create_summary_turn(summary)

    assert turn["role"] == "system"
    assert "[Conversation Summary]" in turn["content"]
    assert "K06101" in turn["content"]


def test_summarize_history_short():
    """Test that short history is not summarized"""
    summarizer = ConversationSummarizer()

    # Only 1 turn
    history = [{"role": "user", "content": "Hello"}]
    summary = summarizer.summarize_history(history, model_tier="light")

    # Should return None for too short history
    assert summary is None


def test_summarize_history_empty():
    """Test empty history"""
    summarizer = ConversationSummarizer()

    summary = summarizer.summarize_history([], model_tier="light")
    assert summary is None
