"""
Unit Tests for Page Rank Caching

Tests cover:
1. LRU cache functionality (hit/miss, eviction, TTL)
2. Cache key generation
3. Query embedding caching
4. Cache statistics
5. Cache invalidation
6. Integration with PageReranker

Usage:
    pytest tests/test_page_rank_caching.py -v
"""

import time
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from app.rag.page_reranker import LRUCache, PageReranker, get_page_reranker

# ============================================================================
# TEST LRUCACHE
# ============================================================================


class TestLRUCache:
    """Test LRU cache implementation"""

    def test_cache_initialization(self):
        """Test cache initialization"""
        cache = LRUCache(maxsize=100, ttl=60)

        assert cache.maxsize == 100
        assert cache.ttl == 60
        assert cache.hits == 0
        assert cache.misses == 0
        assert len(cache.cache) == 0

    def test_cache_put_and_get(self):
        """Test basic put and get operations"""
        cache = LRUCache(maxsize=10, ttl=0)  # No TTL

        # Put value
        cache.put("key1", "value1")

        # Get value
        value = cache.get("key1")
        assert value == "value1"
        assert cache.hits == 1
        assert cache.misses == 0

    def test_cache_miss(self):
        """Test cache miss"""
        cache = LRUCache(maxsize=10, ttl=0)

        value = cache.get("nonexistent")
        assert value is None
        assert cache.hits == 0
        assert cache.misses == 1

    def test_cache_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = LRUCache(maxsize=3, ttl=0)

        # Fill cache
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        assert len(cache.cache) == 3

        # Add one more - should evict key1 (oldest)
        cache.put("key4", "value4")

        assert len(cache.cache) == 3
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key4") == "value4"  # New entry exists

    def test_cache_ttl_expiry(self):
        """Test TTL expiry"""
        cache = LRUCache(maxsize=10, ttl=1)  # 1 second TTL

        # Put value
        cache.put("key1", "value1")

        # Should be available immediately
        assert cache.get("key1") == "value1"

        # Wait for TTL to expire
        time.sleep(1.1)

        # Should be expired
        assert cache.get("key1") is None
        assert cache.misses == 1  # Counted as miss

    def test_cache_lru_order(self):
        """Test that recently used items are not evicted"""
        cache = LRUCache(maxsize=2, ttl=0)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        # Access key1 (marks as recently used)
        cache.get("key1")

        # Add key3 - should evict key2 (not key1)
        cache.put("key3", "value3")

        assert cache.get("key1") == "value1"  # Still exists
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"  # New entry

    def test_cache_clear(self):
        """Test cache clearing"""
        cache = LRUCache(maxsize=10, ttl=0)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.get("key1")  # Hit
        cache.get("key3")  # Miss

        assert len(cache.cache) == 2
        assert cache.hits == 1
        assert cache.misses == 1

        # Clear cache
        cache.clear()

        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_cache_stats(self):
        """Test cache statistics"""
        cache = LRUCache(maxsize=10, ttl=60)

        # Add some data
        cache.put("key1", "value1")
        cache.put("key2", "value2")

        # Some hits and misses
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key3")  # Miss

        stats = cache.stats()

        assert stats["size"] == 2
        assert stats["maxsize"] == 10
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
        assert stats["ttl"] == 60


# ============================================================================
# TEST PAGERERANKER CACHING
# ============================================================================


class TestPageRerankerCaching:
    """Test caching integration in PageReranker"""

    @pytest.fixture
    def mock_reranker(self):
        """Create PageReranker with mocked dependencies"""
        with patch("app.rag.page_reranker._pipeline_config") as mock_config:
            # Configure mock config
            mock_config.ENABLE_PAGE_RANK_CACHE = True
            mock_config.PAGE_RANK_CACHE_SIZE = 100
            mock_config.PAGE_RANK_CACHE_TTL = 60
            mock_config.ENABLE_QUERY_EMBED_CACHE = True
            mock_config.QUERY_EMBED_CACHE_SIZE = 50
            mock_config.ENABLE_PAGE_SEMANTIC = (
                False  # Disable semantic for simple tests
            )
            mock_config.page_bm25_index_path = Mock(exists=Mock(return_value=False))
            mock_config.text_by_page_path = Mock(exists=Mock(return_value=False))
            mock_config.page_embeddings_path = Mock(exists=Mock(return_value=False))
            mock_config.page_metadata_path = Mock(exists=Mock(return_value=False))

            reranker = PageReranker()
            return reranker

    def test_cache_initialization(self, mock_reranker):
        """Test that caches are initialized"""
        assert mock_reranker._rank_cache is not None
        assert mock_reranker._embed_cache is not None
        assert isinstance(mock_reranker._rank_cache, LRUCache)
        assert isinstance(mock_reranker._embed_cache, LRUCache)

    def test_cache_key_generation(self, mock_reranker):
        """Test cache key generation"""
        key1 = mock_reranker._make_cache_key("test query", "doc1", 5, 0.0, False)
        key2 = mock_reranker._make_cache_key("test query", "doc1", 5, 0.0, False)
        key3 = mock_reranker._make_cache_key("different query", "doc1", 5, 0.0, False)

        # Same params should generate same key
        assert key1 == key2

        # Different params should generate different key
        assert key1 != key3

        # Keys should be hex strings (MD5 hash)
        assert len(key1) == 32
        assert all(c in "0123456789abcdef" for c in key1)

    def test_cache_key_with_semantic(self, mock_reranker):
        """Test cache key includes semantic weights when enabled"""
        key_bm25 = mock_reranker._make_cache_key("test", "doc1", 5, 0.0, False)
        key_semantic = mock_reranker._make_cache_key("test", "doc1", 5, 0.0, True)

        # Should be different when semantic is enabled
        assert key_bm25 != key_semantic

    def test_clear_caches(self, mock_reranker):
        """Test cache clearing functionality"""
        # Add some data to caches
        mock_reranker._rank_cache.put("key1", [(1, 0.9)])
        mock_reranker._embed_cache.put("query1", np.array([0.1, 0.2]))

        assert len(mock_reranker._rank_cache.cache) == 1
        assert len(mock_reranker._embed_cache.cache) == 1

        # Clear caches
        mock_reranker.clear_caches()

        assert len(mock_reranker._rank_cache.cache) == 0
        assert len(mock_reranker._embed_cache.cache) == 0

    def test_get_cache_stats(self, mock_reranker):
        """Test cache statistics retrieval"""
        # Generate some cache activity
        mock_reranker._rank_cache.put("key1", [(1, 0.9)])
        mock_reranker._rank_cache.get("key1")  # Hit
        mock_reranker._rank_cache.get("key2")  # Miss

        stats = mock_reranker.get_cache_stats()

        assert "rank_cache" in stats
        assert "embed_cache" in stats

        rank_stats = stats["rank_cache"]
        assert rank_stats["size"] == 1
        assert rank_stats["hits"] == 1
        assert rank_stats["misses"] == 1
        assert rank_stats["hit_rate"] == 0.5

    def test_cache_stats_disabled(self):
        """Test cache stats when caching is disabled"""
        with patch("app.rag.page_reranker._pipeline_config") as mock_config:
            mock_config.ENABLE_PAGE_RANK_CACHE = False
            mock_config.ENABLE_QUERY_EMBED_CACHE = False
            mock_config.page_bm25_index_path = Mock(exists=Mock(return_value=False))
            mock_config.text_by_page_path = Mock(exists=Mock(return_value=False))
            mock_config.page_embeddings_path = Mock(exists=Mock(return_value=False))
            mock_config.page_metadata_path = Mock(exists=Mock(return_value=False))

            reranker = PageReranker()
            stats = reranker.get_cache_stats()

            # When disabled, should return disabled status
            assert stats["rank_cache"]["enabled"] is False or stats["rank_cache"] == {
                "enabled": False
            }
            assert stats["embed_cache"]["enabled"] is False or stats["embed_cache"] == {
                "enabled": False
            }


# ============================================================================
# TEST CACHE INTEGRATION WITH RANKING
# ============================================================================


class TestCacheIntegration:
    """Test cache integration with actual ranking operations"""

    @pytest.fixture
    def mock_reranker_with_index(self):
        """Create PageReranker with mocked BM25 index"""
        with patch("app.rag.page_reranker._pipeline_config") as mock_config:
            mock_config.ENABLE_PAGE_RANK_CACHE = True
            mock_config.PAGE_RANK_CACHE_SIZE = 100
            mock_config.PAGE_RANK_CACHE_TTL = 60
            mock_config.ENABLE_QUERY_EMBED_CACHE = True
            mock_config.QUERY_EMBED_CACHE_SIZE = 50
            mock_config.ENABLE_PAGE_SEMANTIC = False
            mock_config.page_bm25_index_path = Mock(exists=Mock(return_value=False))
            mock_config.text_by_page_path = Mock(exists=Mock(return_value=True))
            mock_config.page_embeddings_path = Mock(exists=Mock(return_value=False))
            mock_config.page_metadata_path = Mock(exists=Mock(return_value=False))

            reranker = PageReranker()

            # Mock BM25 index
            mock_bm25 = Mock()
            mock_bm25.get_scores = Mock(return_value=np.array([0.5, 0.8, 0.3, 0.9]))
            reranker._page_index = mock_bm25

            # Mock page lookup
            reranker._page_lookup = {
                ("doc1", 1): 0,
                ("doc1", 2): 1,
                ("doc1", 3): 2,
                ("doc2", 1): 3,
            }

            return reranker

    def test_ranking_caches_results(self, mock_reranker_with_index):
        """Test that ranking results are cached"""
        reranker = mock_reranker_with_index

        # First call - should compute and cache
        result1 = reranker.rank_pages_for_doc("test query", "doc1", top_k=2)

        # Check cache stats
        stats_before = reranker.get_cache_stats()
        assert stats_before["rank_cache"]["size"] == 1
        assert stats_before["rank_cache"]["misses"] == 1

        # Second call with same params - should hit cache
        result2 = reranker.rank_pages_for_doc("test query", "doc1", top_k=2)

        # Results should be identical
        assert result1 == result2

        # Cache stats should show hit
        stats_after = reranker.get_cache_stats()
        assert stats_after["rank_cache"]["hits"] == 1
        assert stats_after["rank_cache"]["size"] == 1  # Still only 1 entry

    def test_different_queries_different_cache_entries(self, mock_reranker_with_index):
        """Test that different queries create different cache entries"""
        reranker = mock_reranker_with_index

        # Two different queries
        result1 = reranker.rank_pages_for_doc("query1", "doc1", top_k=2)
        result2 = reranker.rank_pages_for_doc("query2", "doc1", top_k=2)

        # Should have 2 cache entries
        stats = reranker.get_cache_stats()
        assert stats["rank_cache"]["size"] == 2
        assert stats["rank_cache"]["misses"] == 2  # Both were cache misses

    def test_cache_respects_parameters(self, mock_reranker_with_index):
        """Test that cache differentiates based on parameters"""
        reranker = mock_reranker_with_index

        # Same query but different top_k
        result1 = reranker.rank_pages_for_doc("test", "doc1", top_k=2)
        result2 = reranker.rank_pages_for_doc("test", "doc1", top_k=3)

        # Should be different cache entries
        stats = reranker.get_cache_stats()
        assert stats["rank_cache"]["size"] == 2

        # Results might be different length
        assert len(result1) <= 2
        assert len(result2) <= 3


# ============================================================================
# TEST PERFORMANCE IMPACT
# ============================================================================


class TestCachePerformance:
    """Test cache performance characteristics"""

    def test_cache_hit_is_faster(self):
        """Test that cache hits are significantly faster than misses"""
        cache = LRUCache(maxsize=100, ttl=0)

        # Simulate expensive computation
        expensive_value = list(range(1000))
        cache.put("key1", expensive_value)

        # Measure cache hit time
        start = time.time()
        for _ in range(100):
            cache.get("key1")
        hit_time = time.time() - start

        # Cache hits should be very fast
        assert hit_time < 0.01  # Should be sub-millisecond per hit

    def test_cache_memory_bounded(self):
        """Test that cache respects size limit"""
        cache = LRUCache(maxsize=10, ttl=0)

        # Add more entries than maxsize
        for i in range(20):
            cache.put(f"key{i}", f"value{i}")

        # Should only keep maxsize entries
        assert len(cache.cache) == 10

        # Oldest entries should be evicted
        assert cache.get("key0") is None
        assert cache.get("key19") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
