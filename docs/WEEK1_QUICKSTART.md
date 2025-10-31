# Week 1 Critical Infrastructure - Quick Start Guide

## 🚀 Quick Start: Test Redis HA + Secret Redaction

### Prerequisites
- Docker and Docker Compose installed
- Python 3.11+
- Redis CLI (for manual testing)

---

## Option 1: Test Redis Sentinel HA (Recommended)

### 1. Start Redis HA Stack

```bash
# Navigate to project root
cd /path/to/PVCFC-RAG-API

# Start Redis HA stack (master, replica, 3 sentinels)
docker compose -f docker-compose.redis-ha.yml up -d

# Wait for services to be healthy (~10-15 seconds)
docker compose -f docker-compose.redis-ha.yml ps
```

**Expected Output:**
```
NAME                IMAGE          STATUS
redis-master        redis:7-alpine healthy
redis-replica-1     redis:7-alpine healthy
redis-sentinel-1    redis:7-alpine healthy
redis-sentinel-2    redis:7-alpine healthy
redis-sentinel-3    redis:7-alpine healthy
```

### 2. Verify Sentinel Configuration

```bash
# Check sentinel status
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel masters

# Should show master info with status "master"
```

**Expected Output:**
```
1) "name"
2) "mymaster"
3) "ip"
4) "redis-master"
5) "port"
6) "6379"
7) "flags"
8) "master"
...
```

### 3. Configure Application for Sentinel Mode

Create or update `.env`:

```bash
# Redis High Availability
REDIS_MODE=sentinel
REDIS_SENTINELS=localhost:26379,localhost:26380,localhost:26381
REDIS_SENTINEL_SERVICE=mymaster
REDIS_PASSWORD=changeme
REDIS_DB=0
REDIS_SOCKET_CONNECT_TIMEOUT_MS=200
REDIS_SOCKET_TIMEOUT_MS=1000

# Leave distributed cache disabled for now
USE_DISTRIBUTED_CACHE=false
```

### 4. Start Application

```bash
# Install dependencies (if not already)
pip install -r requirements.txt

# Start app
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Check logs for:**
```
INFO: Redis client initialized successfully in sentinel mode
INFO: Redis Sentinel initialized: service=mymaster, sentinels=3
INFO: Logging initialized with secret redaction
```

### 5. Test Automatic Failover

**Terminal 1:** Monitor sentinel logs
```bash
docker compose -f docker-compose.redis-ha.yml logs -f redis-sentinel-1
```

**Terminal 2:** Seed test data and stop master
```bash
# Add test data
docker exec redis-master redis-cli -a changeme SET pvcfc:test "failover-test"

# Verify data is written
docker exec redis-master redis-cli -a changeme GET pvcfc:test
# Output: "failover-test"

# Simulate master failure
docker stop redis-master
```

**Terminal 1 (Sentinel logs):** Watch for failover messages (~5-10 seconds)
```
+vote-for-leader ... (Sentinels voting for new master)
+elected-leader ... (Quorum reached)
+failover-state-reconf-slaves ... (Promoting replica)
+switch-master mymaster redis-master 6379 redis-replica-1 6379
```

**Terminal 3:** Verify app still works
```bash
# App should automatically reconnect to new master
# Check health endpoint
curl http://localhost:8000/health

# Check conversation endpoint (uses Redis)
curl http://localhost:8000/api/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "conversation_id": "test-123"}'
```

### 6. Verify Data Persistence

```bash
# Start old master back as replica
docker start redis-master

# Wait a few seconds for replication sync
sleep 5

# Check if data still exists
docker exec redis-replica-1 redis-cli -a changeme GET pvcfc:test
# Output: "failover-test" (data preserved!)
```

### 7. Cleanup

```bash
# Stop Redis HA stack
docker compose -f docker-compose.redis-ha.yml down

# Remove volumes (optional - removes data)
docker compose -f docker-compose.redis-ha.yml down -v
```

---

## Option 2: Test Secret Redaction (Standalone)

### 1. Start App in Single Redis Mode

```bash
# Update .env for single mode
REDIS_MODE=single
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional, leave empty for no auth

# Start local Redis (if not running)
docker run -d -p 6379:6379 redis:7-alpine

# Start app
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Send Request with Secrets

```bash
# Send request with API key in header
curl http://localhost:8000/api/ask -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-proj-test123456789012345678901234567890" \
  -d '{"query": "What is the API key?", "api_key": "sk-secret-key-abc123"}'
```

### 3. Verify Redaction in Logs

```bash
# Check app logs (console)
# Should show: Authorization: Bearer [REDACTED]
# Should NOT show: sk-proj-test123456789012345678901234567890

# Check file logs
grep -i "sk-" logs/app.log
# Should find ONLY "sk-[REDACTED]", never raw keys

grep -i "Bearer" logs/requests.jsonl
# Should show "Bearer [REDACTED]"
```

**Example Redacted Log Entry:**
```json
{
  "timestamp": "2025-10-31T10:00:00.000Z",
  "level": "INFO",
  "message": "Request started: /api/ask",
  "headers": {
    "authorization": "Bearer [REDACTED]"
  },
  "body": {
    "api_key": "sk-[REDACTED]"
  }
}
```

---

## Option 3: Run Unit Tests

### Secret Redaction Tests

```bash
# Run all redaction tests
pytest tests/unit/test_logging_filter.py -v

# Run specific test
pytest tests/unit/test_logging_filter.py::TestSecretRedactionFilter::test_openai_api_key_redaction -v

# Run performance benchmarks
pytest tests/unit/test_logging_filter.py -k "performance" -v
```

**Expected Output:**
```
tests/unit/test_logging_filter.py::TestSecretRedactionFilter::test_openai_api_key_redaction PASSED
tests/unit/test_logging_filter.py::TestSecretRedactionFilter::test_gemini_api_key_redaction PASSED
tests/unit/test_logging_filter.py::TestSecretRedactionFilter::test_bearer_token_redaction PASSED
tests/unit/test_logging_filter.py::TestSecretRedactionFilter::test_performance_large_log_message PASSED
...
========================= 25 passed in 0.15s =========================
```

---

## Troubleshooting

### Issue: Sentinels can't reach master

**Symptom:** Sentinels log `+sdown master mymaster`

**Solution:**
```bash
# Check Redis master is running
docker ps | grep redis-master

# Check network connectivity
docker exec redis-sentinel-1 ping redis-master

# Check master password is set correctly
docker exec redis-master redis-cli -a changeme PING
```

### Issue: App fails to connect to Redis

**Symptom:** `Failed to initialize Redis client: Connection refused`

**Solution:**
```bash
# Verify REDIS_MODE in .env matches your setup
# For Sentinel: REDIS_MODE=sentinel
# For Single: REDIS_MODE=single

# Verify REDIS_SENTINELS points to correct hosts
# For Docker: use container names (redis-sentinel-1, redis-sentinel-2, redis-sentinel-3)
# For localhost: use localhost:26379,localhost:26380,localhost:26381

# Check Redis logs
docker logs redis-master
docker logs redis-sentinel-1
```

### Issue: Secrets still visible in logs

**Symptom:** Raw API keys appear in `logs/app.log`

**Solution:**
```bash
# Verify redaction filter is imported
grep "from app.core.logging_filter import redact_secrets" app/core/logging.py

# Check logging initialization message
grep "Logging initialized with secret redaction" logs/app.log

# If still leaking, restart app to pick up new code
uvicorn app.main:app --reload
```

### Issue: Failover takes >10 seconds

**Expected:** 5-10 seconds typical, up to 15 seconds acceptable

**If longer:**
```bash
# Check sentinel down-after-milliseconds (default: 5000ms)
docker exec redis-sentinel-1 redis-cli -p 26379 \
  SENTINEL CONFIG GET down-after-milliseconds mymaster

# Check sentinel failover-timeout (default: 10000ms)
docker exec redis-sentinel-1 redis-cli -p 26379 \
  SENTINEL CONFIG GET failover-timeout mymaster

# Reduce for faster failover (careful in production!)
docker exec redis-sentinel-1 redis-cli -p 26379 \
  SENTINEL SET mymaster down-after-milliseconds 3000
```

---

## Verification Checklist

### Redis HA
- [ ] All 5 containers (master, replica, 3 sentinels) are healthy
- [ ] Sentinels report master status correctly
- [ ] App connects successfully in sentinel mode
- [ ] Failover completes in <10 seconds
- [ ] Data persists across failover
- [ ] App reconnects automatically (no manual intervention)

### Secret Redaction
- [ ] API keys (sk-*, AIza*, hf_*) are redacted
- [ ] Bearer tokens are redacted
- [ ] Passwords are masked (********)
- [ ] Connection string credentials are redacted
- [ ] No plain-text secrets in `logs/app.log`
- [ ] No plain-text secrets in `logs/requests.jsonl`
- [ ] Unit tests pass (25+ cases)

---

## Performance Baselines

### Redis Sentinel
- **Failover time:** 5-10 seconds (typical), <15s (acceptable)
- **Connection overhead:** <5ms vs single mode
- **Throughput:** No measurable difference (<1% impact)

### Secret Redaction
- **Overhead per log:** <1ms (10KB message)
- **Overhead per secret:** <0.25ms (20 secrets in one message)
- **False positive rate:** 0% (innocent strings not redacted)

---

## Next Steps

1. **Complete Testing:** Run through all verification checklists above
2. **Manual Validation:** Test failover with real app workload
3. **Document Findings:** Note actual failover times, any issues encountered
4. **Move to Day 4-5:** Implement distributed cache once Redis HA is validated

---

## Support

- **Documentation:** See `WEEK1_IMPLEMENTATION_SUMMARY.md` for full details
- **Issues:** Check `TROUBLESHOOTING.md` for common problems
- **Runbooks:** Coming in Day 5 (`docs/runbooks/redis_ha_failover.md`)

---

**Happy Testing!** 🚀
