"""
Redis HA Sentinel Failover Test Script

Tests:
1. Sentinel master discovery
2. Automatic failover on master failure
3. Data persistence across failover
4. Distributed cache cross-instance sharing

Usage:
    python scripts/test_redis_ha.py --test failover
    python scripts/test_redis_ha.py --test cache
    python scripts/test_redis_ha.py --test all
"""

import argparse
import sys
import time
from typing import List, Tuple

import redis
from redis.sentinel import Sentinel


def test_sentinel_discovery() -> Tuple[bool, str]:
    """Test if sentinels can discover the master."""
    print("\n=== TEST 1: Sentinel Master Discovery ===")
    
    try:
        # Connect to sentinels
        sentinels = [
            ('localhost', 26379),
            ('localhost', 26380),
            ('localhost', 26381),
        ]
        
        sentinel = Sentinel(
            sentinels,
            socket_timeout=1.0,
            socket_connect_timeout=0.5,
        )
        
        # Discover master
        master_info = sentinel.discover_master('mymaster')
        print(f"✓ Master discovered: {master_info[0]}:{master_info[1]}")
        
        # Check sentinel status
        for i, (host, port) in enumerate(sentinels, 1):
            try:
                sent_conn = redis.Redis(host=host, port=port, socket_timeout=1)
                masters = sent_conn.execute_command('SENTINEL', 'MASTERS')
                print(f"✓ Sentinel-{i} ({host}:{port}) is healthy")
            except Exception as e:
                print(f"✗ Sentinel-{i} ({host}:{port}) error: {e}")
                return False, f"Sentinel-{i} unhealthy"
        
        return True, "All sentinels can discover master"
    
    except Exception as e:
        return False, f"Sentinel discovery failed: {e}"


def test_failover(password: str) -> Tuple[bool, str]:
    """Test automatic failover by stopping master."""
    print("\n=== TEST 2: Sentinel Automatic Failover ===")
    
    try:
        # Connect via sentinel
        sentinels = [
            ('localhost', 26379),
            ('localhost', 26380),
            ('localhost', 26381),
        ]
        
        sentinel = Sentinel(
            sentinels,
            socket_timeout=1.0,
            password=password,
        )
        
        # Get master connection
        master = sentinel.master_for('mymaster', socket_timeout=1)
        
        # Seed test data
        test_keys = {
            'pvcfc:test:1': 'failover_test_data_1',
            'pvcfc:test:2': 'failover_test_data_2',
            'pvcfc:test:3': 'failover_test_data_3',
        }
        
        print("Seeding test data in master...")
        for key, value in test_keys.items():
            master.set(key, value)
            print(f"  SET {key} = {value}")
        
        # Verify data before failover
        print("\nVerifying data before failover...")
        for key in test_keys:
            value = master.get(key)
            if value != test_keys[key].encode():
                return False, f"Pre-failover data mismatch for {key}"
            print(f"  ✓ {key} = {value.decode()}")
        
        print("\n⚠️  MANUAL STEP REQUIRED:")
        print("     Run in another terminal: docker stop redis-master")
        print("     Waiting 15 seconds for failover to complete...")
        input("     Press Enter after stopping redis-master...")
        
        # Wait for failover
        time.sleep(15)
        
        # Get new master connection (sentinel should auto-discover)
        print("\nReconnecting via sentinel (should get new master)...")
        new_master = sentinel.master_for('mymaster', socket_timeout=1)
        
        # Verify data persisted
        print("Verifying data after failover...")
        for key in test_keys:
            value = new_master.get(key)
            if value is None:
                return False, f"Data lost for {key} after failover"
            if value != test_keys[key].encode():
                return False, f"Data corrupted for {key} after failover"
            print(f"  ✓ {key} = {value.decode()}")
        
        # Get new master info
        new_master_info = sentinel.discover_master('mymaster')
        print(f"\n✓ New master: {new_master_info[0]}:{new_master_info[1]}")
        
        return True, "Failover successful with data persistence"
    
    except Exception as e:
        return False, f"Failover test failed: {e}"


def test_distributed_cache() -> Tuple[bool, str]:
    """Test distributed cache cross-instance sharing."""
    print("\n=== TEST 3: Distributed Cache Cross-Instance ===")
    
    try:
        # Import cache manager
        import os
        import sys
        sys.path.insert(0, os.path.abspath('.'))
        
        from app.core.cache_manager import get_cache
        from app.core.redis_client import get_redis_factory
        
        # Initialize Redis client factory
        print("Initializing Redis client...")
        factory = get_redis_factory()
        factory.initialize()
        print("✓ Redis client initialized")
        
        # Get cache instances (simulating 2 different app instances)
        cache_a = get_cache(namespace="test_instance_a")
        cache_b = get_cache(namespace="test_instance_a")  # Same namespace!
        
        # Test 1: Write on instance A, read on instance B
        print("\nTest 1: Cross-instance cache sharing")
        test_key = "test:cross_instance"
        test_value = {"message": "Hello from instance A", "timestamp": time.time()}
        
        print(f"  Instance A: SET {test_key}")
        cache_a.set(test_key, test_value, ttl=300)
        
        print(f"  Instance B: GET {test_key}")
        cached_value = cache_b.get(test_key)
        
        if cached_value is None:
            return False, "Cache miss on instance B (should be shared)"
        
        if cached_value != test_value:
            return False, f"Value mismatch: {cached_value} != {test_value}"
        
        print(f"  ✓ Cache hit on instance B: {cached_value}")
        
        # Test 2: TTL expiration
        print("\nTest 2: TTL expiration validation")
        ttl_key = "test:ttl_expiry"
        cache_a.set(ttl_key, "short_lived", ttl=3)
        print(f"  SET {ttl_key} with TTL=3s")
        
        # Immediate read should hit
        value = cache_b.get(ttl_key)
        if value is None:
            return False, "TTL key not found immediately"
        print(f"  ✓ Immediate read: {value}")
        
        # Wait for expiration
        print("  Waiting 4 seconds for expiration...")
        time.sleep(4)
        
        value = cache_b.get(ttl_key)
        if value is not None:
            return False, f"TTL key should expire but got: {value}"
        print(f"  ✓ Key expired after TTL")
        
        # Test 3: Batch operations
        print("\nTest 3: Batch operations (set_many/get_many)")
        batch_data = {
            "batch:1": {"id": 1, "name": "Alice"},
            "batch:2": {"id": 2, "name": "Bob"},
            "batch:3": {"id": 3, "name": "Charlie"},
        }
        
        count = cache_a.set_many(batch_data, ttl=300)
        print(f"  SET_MANY: {count}/{len(batch_data)} keys")
        
        if count != len(batch_data):
            return False, f"set_many failed: {count}/{len(batch_data)}"
        
        results = cache_b.get_many(list(batch_data.keys()))
        print(f"  GET_MANY: {len(results)}/{len(batch_data)} keys")
        
        if len(results) != len(batch_data):
            return False, f"get_many failed: {len(results)}/{len(batch_data)}"
        
        for key in batch_data:
            if results.get(key) != batch_data[key]:
                return False, f"Batch value mismatch for {key}"
        
        print("  ✓ All batch operations successful")
        
        # Show stats
        print("\nCache Statistics:")
        stats_a = cache_a.get_stats()
        stats_b = cache_b.get_stats()
        print(f"  Instance A: {stats_a}")
        print(f"  Instance B: {stats_b}")
        
        return True, "All distributed cache tests passed"
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Distributed cache test failed: {e}"


def main():
    parser = argparse.ArgumentParser(description='Test Redis HA and Distributed Cache')
    parser.add_argument(
        '--test',
        choices=['discovery', 'failover', 'cache', 'all'],
        default='all',
        help='Test to run',
    )
    parser.add_argument(
        '--password',
        default='pvcfc_redis_2025_secure',
        help='Redis password',
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("REDIS HA & DISTRIBUTED CACHE TEST SUITE")
    print("=" * 60)
    
    results = []
    
    if args.test in ['discovery', 'all']:
        success, message = test_sentinel_discovery()
        results.append(('Sentinel Discovery', success, message))
    
    if args.test in ['failover', 'all']:
        success, message = test_failover(args.password)
        results.append(('Sentinel Failover', success, message))
    
    if args.test in ['cache', 'all']:
        success, message = test_distributed_cache()
        results.append(('Distributed Cache', success, message))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, success, message in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} | {test_name}: {message}")
        if not success:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
