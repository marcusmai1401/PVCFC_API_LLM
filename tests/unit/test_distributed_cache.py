"""
Unit tests for DistributedCache and CacheFactory.

Tests:
- Basic get/set/delete operations
- TTL expiration
- Namespace isolation
- Batch operations (get_many, set_many)
- Atomic increment
- Lock acquisition/release
- Stats tracking
- Feature flag switching (distributed vs memory)
"""

import time
import threading
import pytest

# Check if Redis is available
try:
    from app.core.redis_client import get_redis_factory
    
    redis_available = True
    factory = get_redis_factory()
    try:
        factory.initialize()
        factory.ping()
    except Exception:
        redis_available = False
except Exception:
    redis_available = False


# Skip all tests if Redis unavailable
pytestmark = pytest.mark.skipif(
    not redis_available,
    reason="Redis not available for distributed cache tests"
)


from app.core.distributed_cache import DistributedCache
from app.core.cache_manager import CacheFactory, get_cache, TTLCacheWrapper


class TestDistributedCache:
    """Test suite for DistributedCache"""
    
    @pytest.fixture(autouse=True)
    def setup_cache(self):
        """Setup: create cache and clear namespace before each test"""
        self.cache = DistributedCache(namespace="test", default_ttl=60)
        self.cache.clear_namespace()
        yield
        # Cleanup: clear after test
        self.cache.clear_namespace()
    
    def test_set_and_get(self):
        """Test basic set and get operations"""
        key = "test_key"
        value = {"data": "test_value", "count": 42}
        
        # Set value
        result = self.cache.set(key, value)
        assert result is True
        
        # Get value
        cached = self.cache.get(key)
        assert cached == value
    
    def test_get_default(self):
        """Test get with default value when key doesn't exist"""
        default = {"default": True}
        cached = self.cache.get("nonexistent", default=default)
        assert cached == default
    
    def test_delete(self):
        """Test delete operation"""
        key = "delete_test"
        self.cache.set(key, "value")
        
        # Verify exists
        assert self.cache.exists(key) is True
        
        # Delete
        deleted = self.cache.delete(key)
        assert deleted is True
        
        # Verify gone
        assert self.cache.exists(key) is False
        assert self.cache.get(key) is None
    
    def test_ttl_expiration(self):
        """Test TTL expiration"""
        key = "ttl_test"
        value = "expires_soon"
        
        # Set with 1 second TTL
        self.cache.set(key, value, ttl=1)
        
        # Should exist immediately
        assert self.cache.get(key) == value
        
        # Wait for expiration
        time.sleep(1.2)
        
        # Should be gone
        assert self.cache.get(key) is None
    
    def test_namespace_isolation(self):
        """Test that different namespaces are isolated"""
        cache1 = DistributedCache(namespace="ns1")
        cache2 = DistributedCache(namespace="ns2")
        
        key = "shared_key"
        value1 = "value_from_ns1"
        value2 = "value_from_ns2"
        
        # Set in both namespaces
        cache1.set(key, value1)
        cache2.set(key, value2)
        
        # Values should be isolated
        assert cache1.get(key) == value1
        assert cache2.get(key) == value2
        
        # Cleanup
        cache1.clear_namespace()
        cache2.clear_namespace()
    
    def test_get_many(self):
        """Test batch get operation"""
        data = {
            "key1": {"value": 1},
            "key2": {"value": 2},
            "key3": {"value": 3},
        }
        
        # Set multiple keys
        for key, value in data.items():
            self.cache.set(key, value)
        
        # Get many (including non-existent key)
        keys = ["key1", "key2", "key3", "nonexistent"]
        result = self.cache.get_many(keys)
        
        # Should return only existing keys
        assert len(result) == 3
        assert result["key1"] == data["key1"]
        assert result["key2"] == data["key2"]
        assert result["key3"] == data["key3"]
        assert "nonexistent" not in result
    
    def test_set_many(self):
        """Test batch set operation"""
        data = {
            "bulk1": "value1",
            "bulk2": "value2",
            "bulk3": "value3",
        }
        
        # Set many
        count = self.cache.set_many(data, ttl=60)
        assert count == 3
        
        # Verify all set
        for key, value in data.items():
            assert self.cache.get(key) == value
    
    def test_incr_atomic(self):
        """Test atomic increment"""
        key = "counter"
        
        # Increment non-existent key (should start at 1)
        result = self.cache.incr(key)
        assert result == 1
        
        # Increment again
        result = self.cache.incr(key)
        assert result == 2
        
        # Increment by amount
        result = self.cache.incr(key, amount=5)
        assert result == 7
    
    def test_incr_concurrency(self):
        """Test atomic increment under concurrent access"""
        key = "concurrent_counter"
        num_threads = 10
        increments_per_thread = 100
        
        def increment_worker():
            for _ in range(increments_per_thread):
                self.cache.incr(key)
        
        # Start threads
        threads = [
            threading.Thread(target=increment_worker)
            for _ in range(num_threads)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify final count (should be exact due to atomicity)
        expected = num_threads * increments_per_thread
        actual = int(self.cache.get(key))
        assert actual == expected
    
    def test_lock_and_unlock(self):
        """Test lock acquisition and release"""
        key = "lock_test"
        
        # Acquire lock
        acquired = self.cache.lock(key, timeout=10)
        assert acquired is True
        
        # Try to acquire again (should fail)
        acquired_again = self.cache.lock(key)
        assert acquired_again is False
        
        # Release lock
        released = self.cache.unlock(key)
        assert released is True
        
        # Should be able to acquire now
        acquired_after = self.cache.lock(key)
        assert acquired_after is True
        
        # Cleanup
        self.cache.unlock(key)
    
    def test_lock_auto_expire(self):
        """Test lock auto-expiration"""
        key = "lock_expire"
        
        # Acquire with short timeout
        self.cache.lock(key, timeout=1)
        
        # Should be locked
        assert self.cache.lock(key) is False
        
        # Wait for expiration
        time.sleep(1.2)
        
        # Should be unlocked now
        assert self.cache.lock(key) is True
        
        # Cleanup
        self.cache.unlock(key)
    
    def test_stats_tracking(self):
        """Test cache statistics"""
        # Reset stats
        self.cache.reset_stats()
        
        # Perform operations
        self.cache.set("key1", "value1")
        self.cache.get("key1")  # Hit
        self.cache.get("key2")  # Miss
        self.cache.get("key3")  # Miss
        
        # Check stats
        stats = self.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 33.33  # 1/3 * 100
    
    def test_clear_namespace(self):
        """Test clearing entire namespace"""
        # Set multiple keys
        for i in range(5):
            self.cache.set(f"key{i}", f"value{i}")
        
        # Verify all exist
        for i in range(5):
            assert self.cache.exists(f"key{i}") is True
        
        # Clear namespace
        deleted = self.cache.clear_namespace()
        assert deleted == 5
        
        # Verify all gone
        for i in range(5):
            assert self.cache.exists(f"key{i}") is False
    
    def test_json_serialization(self):
        """Test JSON serialization of complex types"""
        complex_data = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {
                "inner": "value"
            }
        }
        
        self.cache.set("complex", complex_data)
        cached = self.cache.get("complex")
        
        assert cached == complex_data


class TestCacheFactory:
    """Test suite for CacheFactory and feature flag switching"""
    
    def teardown_method(self):
        """Clear factory instances after each test"""
        CacheFactory.clear_all()
    
    def test_get_distributed_cache(self, monkeypatch):
        """Test factory returns DistributedCache when flag enabled"""
        # Mock settings to enable distributed cache
        monkeypatch.setattr("app.core.cache_manager.settings.use_distributed_cache", True)
        
        cache = CacheFactory.get_cache(namespace="test_distributed")
        
        # Should be DistributedCache instance
        assert isinstance(cache, DistributedCache)
        
        # Cleanup
        if hasattr(cache, 'clear_namespace'):
            cache.clear_namespace()
    
    def test_get_ttl_cache(self, monkeypatch):
        """Test factory returns TTLCacheWrapper when flag disabled"""
        # Mock settings to disable distributed cache
        monkeypatch.setattr("app.core.cache_manager.settings.use_distributed_cache", False)
        
        cache = CacheFactory.get_cache(namespace="test_memory")
        
        # Should be TTLCacheWrapper instance
        assert isinstance(cache, TTLCacheWrapper)
    
    def test_cache_reuse(self):
        """Test that factory reuses cache instances for same namespace"""
        cache1 = CacheFactory.get_cache(namespace="reuse_test")
        cache2 = CacheFactory.get_cache(namespace="reuse_test")
        
        # Should be same instance
        assert cache1 is cache2
    
    def test_different_namespaces(self):
        """Test that different namespaces get different instances"""
        cache1 = CacheFactory.get_cache(namespace="ns1")
        cache2 = CacheFactory.get_cache(namespace="ns2")
        
        # Should be different instances
        assert cache1 is not cache2
    
    def test_get_cache_convenience(self):
        """Test convenience function"""
        cache = get_cache(namespace="convenience_test")
        
        # Should work like normal cache
        cache.set("test", "value")
        assert cache.get("test") == "value"
    
    def test_cache_backend_protocol(self):
        """Test that both cache types implement same interface"""
        # Test with distributed cache
        distributed = DistributedCache(namespace="protocol_test_dist")
        distributed.clear_namespace()
        
        # Test with memory cache
        memory = TTLCacheWrapper(namespace="protocol_test_mem")
        
        # Both should have same methods
        for cache in [distributed, memory]:
            assert hasattr(cache, 'get')
            assert hasattr(cache, 'set')
            assert hasattr(cache, 'delete')
            assert hasattr(cache, 'exists')
            assert hasattr(cache, 'get_many')
            assert hasattr(cache, 'set_many')
            assert hasattr(cache, 'get_stats')
        
        # Cleanup
        distributed.clear_namespace()


class TestTTLCacheWrapper:
    """Test suite for TTLCacheWrapper (backward compatibility)"""
    
    @pytest.fixture
    def cache(self):
        """Create fresh cache for each test"""
        return TTLCacheWrapper(namespace="ttl_test", default_ttl=60)
    
    def test_basic_operations(self, cache):
        """Test basic set/get/delete"""
        cache.set("key", "value")
        assert cache.get("key") == "value"
        
        cache.delete("key")
        assert cache.get("key") is None
    
    def test_namespace_key_building(self, cache):
        """Test that keys are namespaced"""
        cache.set("key", "value")
        
        # Internal key should be namespaced
        internal_key = cache._build_key("key")
        assert "ttl_test" in internal_key
    
    def test_stats(self, cache):
        """Test stats tracking"""
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        assert stats["backend"] == "ttl_cache"
        assert stats["hits"] == 1
        assert stats["misses"] == 1
    
    def test_batch_operations(self, cache):
        """Test get_many and set_many"""
        data = {"k1": "v1", "k2": "v2", "k3": "v3"}
        
        count = cache.set_many(data)
        assert count == 3
        
        result = cache.get_many(["k1", "k2", "k3"])
        assert len(result) == 3
        assert result["k1"] == "v1"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
