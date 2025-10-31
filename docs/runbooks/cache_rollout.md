# Distributed Cache Rollout Runbook

**Version:** 1.0  
**Last Updated:** 2025-10-31  
**Owner:** Infrastructure Team

---

## Overview

This runbook covers the rollout of Redis-backed distributed cache to replace in-memory TTLCache.

**Benefits:**
- Horizontal scaling: Cache shared across application instances
- Consistent hit rates across all instances
- Reduced per-instance memory footprint
- Zero cache warming needed for new instances

**Feature Flag:** `USE_DISTRIBUTED_CACHE` (default: `false`)

---

## Architecture

### Before (In-Memory Cache)
```
Instance A                Instance B
┌─────────────────┐      ┌─────────────────┐
│ TTLCache        │      │ TTLCache        │
│ - query:123 → X │      │ - Empty cache   │
│ - query:456 → Y │      │ - query:456 → Y │
└─────────────────┘      └─────────────────┘
```

**Problem:** Cache not shared, duplicate computations, inconsistent hit rates.

### After (Distributed Cache)
```
Instance A                Instance B
┌─────────────────┐      ┌─────────────────┐
│ CacheClient     │      │ CacheClient     │
└────────┬────────┘      └────────┬────────┘
         │                         │
         └──────────┬──────────────┘
                    │
         ┌──────────▼────────────┐
         │ Redis (Distributed)   │
         │ pvcfc:query:123 → X   │
         │ pvcfc:query:456 → Y   │
         └───────────────────────┘
```

**Solution:** Single source of truth, cache shared across all instances.

---

## Pre-Rollout Checklist

### Infrastructure
- [ ] Redis HA (Sentinel) is deployed and healthy
- [ ] Redis has sufficient memory for cache workload
  - Estimate: ~100MB per 10k cache entries (depends on payload size)
  - Check: `docker exec redis-master redis-cli -a changeme info memory`
- [ ] Redis maxmemory policy is `allkeys-lru` (evicts old keys when full)
- [ ] Monitoring/alerting configured for Redis metrics

### Application
- [ ] Code deployed with distributed cache implementation
- [ ] Feature flag `USE_DISTRIBUTED_CACHE=false` (disabled initially)
- [ ] Application can reach Redis Sentinel endpoints
- [ ] No errors in application logs related to Redis

### Testing
- [ ] Unit tests passing (30+ cache tests)
- [ ] Integration test in dev environment successful
- [ ] Performance baseline established (baseline latency, hit rate)

---

## Rollout Plan

### Phase 1: Staging Environment (Day 1)

#### Step 1: Enable Feature Flag

```bash
# Update .env on staging app servers
USE_DISTRIBUTED_CACHE=true

# Verify other Redis settings
REDIS_MODE=sentinel
REDIS_SENTINELS=sentinel-1:26379,sentinel-2:26379,sentinel-3:26379
CACHE_NAMESPACE=pvcfc
CACHE_DEFAULT_TTL=3600
```

#### Step 2: Restart Application

```bash
# Restart all staging instances
docker restart staging-app-1
docker restart staging-app-2

# Or with kubernetes
kubectl rollout restart deployment/pvcfc-api -n staging
```

#### Step 3: Verify Cache Initialization

```bash
# Check app logs for cache mode
docker logs staging-app-1 | grep "Using DistributedCache"

# Expected: "Using DistributedCache for namespace: <namespace>"
```

#### Step 4: Validate Cross-Instance Cache Sharing

```bash
# Test on Instance A
curl -X POST http://staging-app-1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "conversation_id": "cache-test-001"}'

# Check Redis for cache entry
docker exec redis-master redis-cli -a changeme KEYS "pvcfc:*"

# Test on Instance B (should see cache hit)
curl -X POST http://staging-app-2:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "conversation_id": "cache-test-001"}'

# Check app logs for cache hit on instance B
docker logs staging-app-2 | grep "Cache hit"
```

#### Step 5: Monitor Metrics (48 hours)

**Key Metrics:**
- Cache hit rate (should improve vs in-memory)
- P50/P95/P99 latency (should stay same or improve)
- Redis memory usage (should grow gradually)
- Redis CPU usage (should be <20%)
- Application error rate (should be 0%)

```bash
# Check cache stats via application endpoint
curl http://staging-app-1:8000/cache-stats

# Or via Redis directly
docker exec redis-master redis-cli -a changeme INFO stats | grep keyspace_hits
docker exec redis-master redis-cli -a changeme INFO stats | grep keyspace_misses
```

**Success Criteria:**
- No increase in errors or latency
- Cache hit rate ≥ in-memory baseline
- Cross-instance cache sharing verified

---

### Phase 2: Canary Production (Day 3)

**Strategy:** Enable on 10% of production instances first.

#### Step 1: Select Canary Instances

```bash
# Enable feature flag on 1-2 production instances
# On canary instances only:
USE_DISTRIBUTED_CACHE=true

# Restart canary instances
docker restart prod-app-canary-1
```

#### Step 2: Monitor Canary (4 hours minimum)

```bash
# Compare metrics: canary vs control group
# Canary instances
curl http://prod-app-canary-1:8000/metrics | grep cache_hit_rate

# Control instances (still using in-memory)
curl http://prod-app-1:8000/metrics | grep cache_hit_rate
```

**Watch for:**
- Latency regression (P95 increase >10%)
- Error rate increase
- Redis connection errors
- Memory leaks

**Decision Point:**
- ✅ Proceed to full rollout if metrics look good
- ❌ Rollback if any issues detected

---

### Phase 3: Full Production Rollout (Day 4)

#### Step 1: Enable for All Instances

```bash
# Update .env for all production instances
USE_DISTRIBUTED_CACHE=true

# Rolling restart (one at a time to avoid downtime)
# With kubernetes
kubectl set env deployment/pvcfc-api USE_DISTRIBUTED_CACHE=true -n production
kubectl rollout status deployment/pvcfc-api -n production

# Or manually with Docker
for instance in prod-app-{1..10}; do
  docker restart $instance
  sleep 30  # Wait for health check
done
```

#### Step 2: Verify Full Rollout

```bash
# Check all instances are using distributed cache
for instance in prod-app-{1..10}; do
  echo "=== $instance ==="
  docker logs $instance | grep "Using DistributedCache"
done

# All should show: "Using DistributedCache"
```

#### Step 3: Warm Up Cache (Optional)

```bash
# Run common queries to populate cache
# Example: top 100 frequent queries
for query in $(cat top_queries.txt); do
  curl -X POST http://prod-app-1:8000/api/ask \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$query\"}"
  sleep 0.1
done
```

#### Step 4: Monitor Production (7 days)

**Daily Checks:**
```bash
# Cache hit rate
docker exec redis-master redis-cli -a changeme INFO stats | grep keyspace

# Redis memory usage
docker exec redis-master redis-cli -a changeme INFO memory | grep used_memory_human

# Application health
curl http://prod-app-1:8000/health
```

**Alerting Thresholds:**
- Redis memory >70% of maxmemory → Warning
- Redis memory >90% of maxmemory → Critical
- Cache hit rate drops >20% → Investigate
- Redis connection errors >1% → Critical

---

## Rollback Procedure

### Scenario 1: Issues Detected During Canary

```bash
# 1. Disable feature flag on canary instances
USE_DISTRIBUTED_CACHE=false

# 2. Restart canary instances
docker restart prod-app-canary-1

# 3. Monitor for stabilization
# 4. Investigate root cause before retrying
```

### Scenario 2: Issues During Full Rollout

```bash
# 1. Immediate rollback via feature flag
# Update .env on all instances
USE_DISTRIBUTED_CACHE=false

# 2. Rolling restart
kubectl set env deployment/pvcfc-api USE_DISTRIBUTED_CACHE=false -n production

# 3. Verify all instances back to in-memory cache
for instance in prod-app-{1..10}; do
  docker logs $instance | grep "Using TTLCache"
done

# 4. Clear Redis cache namespace (optional, to save memory)
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:*" | \
  xargs docker exec redis-master redis-cli -a changeme DEL
```

**Rollback Time:** <5 minutes (feature flag + rolling restart)

---

## Operational Procedures

### Clear Cache Namespace

**When to use:** Cache corruption, deployment with breaking changes, manual invalidation.

```bash
# Clear all keys in namespace
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:retrieval:*" | \
  xargs docker exec redis-master redis-cli -a changeme DEL

# Or clear entire pvcfc namespace
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:*" | \
  xargs docker exec redis-master redis-cli -a changeme DEL

# Verify cleared
docker exec redis-master redis-cli -a changeme KEYS "pvcfc:*"
# Expected: (empty array)
```

### Inspect Cache Keys

```bash
# List all cache keys (first 100)
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:*" --count 100

# Get value of specific key
docker exec redis-master redis-cli -a changeme GET "pvcfc:retrieval:query_hash_123"

# Get TTL of key (seconds remaining)
docker exec redis-master redis-cli -a changeme TTL "pvcfc:retrieval:query_hash_123"

# Count keys in namespace
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:retrieval:*" --count 10000 | wc -l
```

### Adjust TTL

```bash
# Update default TTL in .env
CACHE_DEFAULT_TTL=7200  # 2 hours instead of 1 hour

# Restart application to pick up new TTL
docker restart prod-app-1

# New keys will use new TTL, old keys keep their original TTL
```

### Monitor Cache Performance

```bash
# Cache stats from application
curl http://localhost:8000/cache-stats

# Redis stats
docker exec redis-master redis-cli -a changeme INFO stats

# Key metrics:
# - keyspace_hits: Total cache hits
# - keyspace_misses: Total cache misses
# - Hit rate = hits / (hits + misses) * 100
```

---

## Troubleshooting

### Issue: Low Cache Hit Rate

**Symptoms:**
- Hit rate <30% (expected: >50% after warmup)

**Possible Causes:**
1. TTL too short (cache expires before reuse)
2. High query variance (few repeat queries)
3. Cache keys not namespaced correctly

**Solution:**
```bash
# Check TTL setting
echo $CACHE_DEFAULT_TTL  # Should be 3600+ seconds

# Check key distribution
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:*" --count 100

# Increase TTL if needed
CACHE_DEFAULT_TTL=7200
docker restart <app-instances>
```

### Issue: Redis Memory Full

**Symptoms:**
- Redis logs: "OOM command not allowed when used memory > 'maxmemory'"
- Cache writes failing

**Solution:**
```bash
# Check memory usage
docker exec redis-master redis-cli -a changeme INFO memory

# Option 1: Increase maxmemory
docker exec redis-master redis-cli -a changeme CONFIG SET maxmemory 1gb

# Option 2: Clear old/unused keys
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:*" | \
  xargs docker exec redis-master redis-cli -a changeme DEL

# Option 3: Reduce TTL to expire keys faster
CACHE_DEFAULT_TTL=1800  # 30 minutes
```

### Issue: Cache Stampede

**Symptoms:**
- Multiple instances computing same expensive query simultaneously
- High CPU/latency spikes when cache expires

**Solution:**
```python
# Use lock in application code
from app.core.cache_manager import get_cache

cache = get_cache(namespace="retrieval")

# Try to acquire lock before computation
if cache.lock("expensive_query_123", timeout=30):
    try:
        result = expensive_computation()
        cache.set("expensive_query_123", result, ttl=3600)
    finally:
        cache.unlock("expensive_query_123")
else:
    # Another instance is computing, wait and retry
    time.sleep(0.5)
    result = cache.get("expensive_query_123")
```

### Issue: Stale Cache After Deployment

**Symptoms:**
- Old data returned after code changes

**Solution:**
```bash
# Clear cache during deployment
# In deployment script:
docker exec redis-master redis-cli -a changeme --scan --pattern "pvcfc:*" | \
  xargs docker exec redis-master redis-cli -a changeme DEL

# Or increment cache namespace version
CACHE_NAMESPACE=pvcfc_v2  # Forces new keyspace
```

---

## Performance Benchmarks

### Expected Performance

| Metric | In-Memory (TTLCache) | Distributed (Redis) | Delta |
|--------|----------------------|---------------------|-------|
| Cache get latency | <1ms | 1-3ms | +2ms |
| Cache set latency | <1ms | 2-5ms | +4ms |
| Hit rate (single instance) | 40-60% | 40-60% | 0% |
| Hit rate (multiple instances) | 40-60% | 60-80% | +20-40% |
| Memory per instance | 100-500MB | 10-50MB | -90% |

**Conclusion:** Slight latency increase (~2-5ms) is acceptable tradeoff for:
- Consistent hit rates across instances
- Reduced memory footprint
- Horizontal scaling capability

---

## Monitoring & Alerts

### Key Metrics to Track

```promql
# Cache hit rate
sum(rate(cache_hits_total[5m])) / 
(sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# Redis memory usage
redis_memory_used_bytes / redis_memory_max_bytes

# Cache operation latency
histogram_quantile(0.95, cache_operation_duration_seconds_bucket)
```

### Alert Rules (Prometheus)

```yaml
# Redis memory critical
- alert: RedisMemoryCritical
  expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
  for: 5m
  annotations:
    summary: "Redis memory usage above 90%"
    
# Cache hit rate drop
- alert: CacheHitRateLow
  expr: cache_hit_rate < 0.3
  for: 15m
  annotations:
    summary: "Cache hit rate below 30%"
```

---

## Related Documentation

- [Redis HA Failover Runbook](./redis_ha_failover.md)
- [Week 1 Quick Start Guide](../WEEK1_QUICKSTART.md)
- [Implementation Summary](../../WEEK1_IMPLEMENTATION_SUMMARY.md)

---

**End of Runbook**
