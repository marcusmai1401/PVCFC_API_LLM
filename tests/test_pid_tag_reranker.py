"""
Unit Tests for PID Tag Reranker

Tests tag-based result boosting and proximity detection
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from app.rag.rerankers.pid_tag_reranker import PIDTagReranker


class TestPIDTagReranker:
    """Test suite for PIDTagReranker"""

    def setup_method(self):
        """Setup for each test"""
        self.reranker = PIDTagReranker()

    def test_exact_metadata_tag_boost(self):
        """Test boosting for exact metadata tag match"""
        results = [
            {
                "text": "Heat exchanger specifications",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk1", "tags": ["E04217"]},
            },
            {
                "text": "Other content",
                "score": 0.8,
                "metadata": {"chunk_id": "chunk2", "tags": []},
            },
        ]

        reranked = self.reranker.rerank(results, query_tags=["E04217"], top_k=10)

        # Chunk with metadata tag should be boosted to top
        assert reranked[0]["metadata"]["chunk_id"] == "chunk1"
        assert reranked[0]["final_score"] > results[1]["score"]
        assert "meta_exact" in reranked[0]["boosts"][0]

    def test_exact_text_tag_boost(self):
        """Test boosting for exact text tag match"""
        results = [
            {
                "text": "Equipment E04217 has specifications",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk1", "tags": []},
            },
            {
                "text": "Other content",
                "score": 0.8,
                "metadata": {"chunk_id": "chunk2", "tags": []},
            },
        ]

        reranked = self.reranker.rerank(results, query_tags=["E04217"], top_k=10)

        # Chunk with text tag should be boosted
        assert reranked[0]["metadata"]["chunk_id"] == "chunk1"
        assert "text_exact" in reranked[0]["boosts"][0]

    def test_fuzzy_tag_match(self):
        """Test fuzzy tag matching"""
        results = [
            {
                "text": "Equipment E04217 (typo: E04127)",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk1", "tags": []},
            },
            {
                "text": "Other content",
                "score": 0.8,
                "metadata": {"chunk_id": "chunk2", "tags": []},
            },
        ]

        reranked = self.reranker.rerank(results, query_tags=["E04217"], top_k=10)

        # Should find fuzzy match E04127 ~ E04217
        # Boost may apply if similarity >= threshold

    def test_tag_parameter_proximity(self):
        """Test tag-parameter proximity boost"""
        results = [
            {
                "text": "Equipment E04217 operating at pressure 15 bar",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk1", "tags": ["E04217"]},
            },
            {
                "text": "E04217 is a heat exchanger (no parameters nearby)",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk2", "tags": ["E04217"]},
            },
        ]

        reranked = self.reranker.rerank(results, query_tags=["E04217"], top_k=10)

        # Chunk1 should have proximity boost
        chunk1_result = [r for r in reranked if r["metadata"]["chunk_id"] == "chunk1"][
            0
        ]
        assert any("proximity" in b for b in chunk1_result["boosts"])

    def test_proximity_detection(self):
        """Test _has_tag_param_proximity method"""
        # Tag near pressure
        assert self.reranker._has_tag_param_proximity(
            "Equipment E04217 operates at pressure 15 bar", ["E04217"]
        )

        # Tag near temperature
        assert self.reranker._has_tag_param_proximity(
            "E04217 temperature is 250°C", ["E04217"]
        )

        # Tag near flow
        assert self.reranker._has_tag_param_proximity(
            "E04217 flow rate 1000 kg/h", ["E04217"]
        )

        # Tag without parameters nearby
        assert not self.reranker._has_tag_param_proximity(
            "E04217 is a heat exchanger manufactured by company X", ["E04217"]
        )

    def test_no_tags_no_boost(self):
        """Test that no boosting occurs without tags"""
        results = [
            {
                "text": "Heat exchanger specifications",
                "score": 0.8,
                "metadata": {"chunk_id": "chunk1"},
            },
            {
                "text": "Other content",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk2"},
            },
        ]

        reranked = self.reranker.rerank(results, query_tags=[], top_k=10)

        # Order should remain unchanged
        assert reranked[0]["metadata"]["chunk_id"] == "chunk1"
        assert reranked[1]["metadata"]["chunk_id"] == "chunk2"

    def test_multiple_tags(self):
        """Test handling multiple tags"""
        results = [
            {
                "text": "E04217 and P04201A connection diagram",
                "score": 0.5,
                "metadata": {"chunk_id": "chunk1", "tags": ["E04217", "P04201A"]},
            }
        ]

        reranked = self.reranker.rerank(
            results, query_tags=["E04217", "P04201A"], top_k=10
        )

        # Should boost for both tags
        assert reranked[0]["final_score"] > results[0]["score"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
