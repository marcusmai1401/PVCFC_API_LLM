# Manual Testing Guide - Week 1 Redis HA & Distributed Cache

## Prerequisites

1. **Docker Desktop running** (WSL2 backend on Windows)
2. **Python environment activated** with dependencies installed
3. **.env file updated** with Redis HA config (already done ✓)

---

## Step 1: Start Redis HA Stack

### 1.1 Start Docker Compose

```powershell
# Navigate to project directory
cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC

# Start Redis HA stack (master + replica + 3 sentinels)
docker compose -f docker-compose.redis-ha.yml up -d

# Wait for all containers to be healthy (~30 seconds)
Start-Sleep -Seconds 30
```

### 1.2 Verify Containers Running

```powershell
# Check container status
docker ps --filter "name=redis" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Expected Output:**
```
NAMES                STATUS                    PORTS
redis-master         Up 30 seconds (healthy)   0.0.0.0:6379->6379/tcp
redis-replica-1      Up 30 seconds (healthy)   0.0.0.0:6380->6379/tcp
redis-sentinel-1     Up 30 seconds (healthy)   0.0.0.0:26379->26379/tcp
redis-sentinel-2     Up 30 seconds (healthy)   0.0.0.0:26380->26379/tcp
redis-sentinel-3     Up 30 seconds (healthy)   0.0.0.0:26381->26379/tcp
```

### 1.3 Check Sentinel Master Discovery

```powershell
# Check sentinel 1 can see master
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel masters

# Check replication status
docker exec redis-master redis-cli -a pvcfc_redis_2025_secure info replication
```

**Expected:** Master with 1 connected replica

---

## Step 2: Test Sentinel Failover (TODO 7d50c7d7)

### 2.1 Run Discovery Test

```powershell
# Test sentinel master discovery
python scripts/test_redis_ha.py --test discovery
```

**Expected:** All 3 sentinels discover master successfully

### 2.2 Run Failover Test

```powershell
# Start failover test (will prompt for manual step)
python scripts/test_redis_ha.py --test failover
```

**During test execution:**

1. Script will seed test data in master
2. Script will **wait for you to stop master**
3. In **another PowerShell terminal**, run:
   ```powershell
   docker stop redis-master
   ```
4. Press Enter in test script to continue
5. Script verifies:
   - New master promoted (redis-replica-1)
   - Data persisted across failover
   - Failover completed in < 10 seconds

### 2.3 Verify Failover in Logs

```powershell
# Check sentinel logs for failover events
docker logs redis-sentinel-1 | Select-String -Pattern "failover"

# Check new master
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel get-master-addr-by-name mymaster
```

### 2.4 Restart Old Master (becomes replica)

```powershell
# Restart old master (will rejoin as replica)
docker start redis-master

# Wait for rejoin
Start-Sleep -Seconds 10

# Verify replication
docker exec redis-master redis-cli -a pvcfc_redis_2025_secure info replication
```

---

## Step 3: Test Distributed Cache (TODO 0ce5ee26)

### 3.1 Run Cache Cross-Instance Test

```powershell
# Test distributed cache sharing between instances
python scripts/test_redis_ha.py --test cache
```

**Tests performed:**
1. ✓ Write on instance A, read on instance B (cache shared)
2. ✓ TTL expiration (3 seconds)
3. ✓ Batch operations (set_many/get_many)
4. ✓ Cache statistics

### 3.2 Manual Cache Verification (Optional)

```powershell
# Start Python REPL
python

# In Python:
from app.core.cache_manager import get_cache

# Simulate instance A
cache_a = get_cache(namespace="manual_test")
cache_a.set("test:key", {"msg": "Hello from A"}, ttl=600)

# Simulate instance B
cache_b = get_cache(namespace="manual_test")
result = cache_b.get("test:key")
print(result)  # Should show: {'msg': 'Hello from A'}

# Check stats
print(cache_a.get_stats())
print(cache_b.get_stats())
```

---

## Step 4: Run Existing Test Suite (TODO dc9ddbbe)

### 4.1 Run Unit Tests

```powershell
# Run all tests
pytest -v

# Run only new Week 1 tests
pytest tests/unit/test_distributed_cache.py -v
pytest tests/unit/test_logging_filter.py -v

# Run with coverage
pytest --cov=app.core.distributed_cache --cov=app.core.logging_filter
```

### 4.2 Check Test Results

**Expected:**
- ✓ All existing tests pass (no regressions)
- ✓ New distributed cache tests pass
- ✓ Logging filter tests pass
- Coverage > 80% for new modules

---

## Step 5: Definition of Done Checklist (TODO 17c0becb)

### 5.1 Redis Sentinel Checklist

- [ ] **Failover under 10 seconds**
  - Verified in Step 2.2 test output
  - Check sentinel logs: `docker logs redis-sentinel-1`
  
- [ ] **Data persisted across failover**
  - Verified: test keys present after failover
  
- [ ] **No app code changes needed**
  - App uses `redis_client.get_redis()` factory
  - Sentinel discovery automatic

### 5.2 Secret Redaction Checklist

- [ ] **No secrets in logs**
  - Check `logs/app.log` for any raw API keys
  - Search: `cat logs/app.log | Select-String -Pattern "sk-|AIza|Bearer "`
  - Expected: All masked as `sk-***REDACTED***`

- [ ] **Redaction filter applied**
  - Verified in `app/core/logging.py`
  - Unit tests pass: `pytest tests/unit/test_logging_filter.py`

### 5.3 Distributed Cache Checklist

- [ ] **Cache shared across instances**
  - Verified in Step 3.1 test
  
- [ ] **TTL expiration works**
  - Verified in Step 3.1 test (3s TTL)
  
- [ ] **Feature flag toggling**
  - `.env` has `USE_DISTRIBUTED_CACHE=true`
  - Can set to `false` to revert to in-memory cache

### 5.4 Testing Checklist

- [ ] **All unit tests pass**
  - Verified in Step 4.1
  
- [ ] **No regressions**
  - Existing test suite green
  
- [ ] **New tests added**
  - `test_distributed_cache.py` ✓
  - `test_logging_filter.py` ✓

### 5.5 Rollback Documentation Checklist

- [ ] **Redis HA rollback**
  - Documented in `docs/runbooks/redis_ha_failover.md`
  - Set `REDIS_MODE=single` to revert
  
- [ ] **Cache rollback**
  - Documented in `docs/runbooks/cache_rollout.md`
  - Set `USE_DISTRIBUTED_CACHE=false` to revert
  
- [ ] **Clear cache if needed**
  - Command: `docker exec redis-master redis-cli -a pvcfc_redis_2025_secure FLUSHDB`

---

## Step 6: Performance Smoke Test (Optional)

### 6.1 Start Application

```powershell
# Terminal 1: Start app instance 1
$env:API_PORT = 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Start app instance 2
$env:API_PORT = 8001
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 6.2 Test Cache Sharing Between Running Instances

```powershell
# Send request to instance 1 (port 8000)
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get

# Send request to instance 2 (port 8001)
Invoke-RestMethod -Uri "http://localhost:8001/health" -Method Get

# Monitor Redis keys being created
docker exec redis-master redis-cli -a pvcfc_redis_2025_secure KEYS "pvcfc:*"
```

### 6.3 Monitor Cache Stats

```powershell
# Check cache hit rate in app logs
Get-Content logs/app.log | Select-String -Pattern "Cache (hit|miss)"

# Check Redis memory usage
docker exec redis-master redis-cli -a pvcfc_redis_2025_secure INFO memory | Select-String -Pattern "used_memory_human"
```

---

## Cleanup

### Stop Redis Stack

```powershell
# Stop all containers
docker compose -f docker-compose.redis-ha.yml down

# Remove volumes (WARNING: deletes all data)
docker compose -f docker-compose.redis-ha.yml down -v
```

### Revert Feature Flag (if needed)

```powershell
# Edit .env and set:
# USE_DISTRIBUTED_CACHE=false
# REDIS_MODE=single
```

---

## Success Criteria Summary

| Criteria | Status | Evidence |
|----------|--------|----------|
| Redis Sentinel failover < 10s | ⬜ | Test output + logs |
| Data persists across failover | ⬜ | Test verification |
| Secrets redacted in logs | ⬜ | Log inspection |
| Cache shared across instances | ⬜ | Cross-instance test |
| TTL expiration accurate | ⬜ | TTL test (3s) |
| All tests pass | ⬜ | Pytest output |
| Rollback documented | ✓ | Runbooks exist |
| Feature flag toggles | ✓ | .env config |

**Mark items as complete after running tests!**

---

## Troubleshooting

### Sentinels can't discover master
```powershell
# Check sentinel config
docker exec redis-sentinel-1 cat /tmp/sentinel.conf

# Check network connectivity
docker exec redis-sentinel-1 ping redis-master
```

### Cache not shared between instances
```powershell
# Verify Redis connection
docker exec redis-master redis-cli -a pvcfc_redis_2025_secure PING

# Check app logs for Redis errors
Get-Content logs/app.log | Select-String -Pattern "Redis"
```

### Tests fail with import errors
```powershell
# Ensure in project root
cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC

# Reinstall dependencies
pip install -r requirements.txt
```

---

**Next Steps:** After all tests pass, proceed to Week 2 (Circuit Breakers, Health Checks, Doc ID Validation)
