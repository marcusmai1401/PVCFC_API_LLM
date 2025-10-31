# Redis HA Failover Runbook

**Version:** 1.0  
**Last Updated:** 2025-10-31  
**Owner:** Infrastructure Team

---

## Overview

This runbook covers Redis Sentinel high availability operations:
- Normal operation monitoring
- Failover scenarios (planned and unplanned)
- Recovery procedures
- Troubleshooting common issues

**Architecture:**
- 1 Redis master (read/write)
- 1 Redis replica (read-only, failover candidate)
- 3 Redis Sentinels (quorum=2 for automatic failover)

**Expected Failover Time:** 5-10 seconds (typical), <15s (acceptable)

---

## Prerequisites

- Docker and Docker Compose installed
- Access to application servers and Redis containers
- Redis CLI available
- Monitoring dashboard access (optional)

---

## 1. Normal Operation Monitoring

### Check Redis Cluster Health

```bash
# Check all containers are running
docker compose -f docker-compose.redis-ha.yml ps

# Expected: 5 containers healthy (master, replica, 3 sentinels)
```

**Expected Output:**
```
NAME                STATUS
redis-master        Up (healthy)
redis-replica-1     Up (healthy)
redis-sentinel-1    Up (healthy)
redis-sentinel-2    Up (healthy)
redis-sentinel-3    Up (healthy)
```

### Check Sentinel Status

```bash
# Check sentinel masters
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel masters

# Look for:
# - name: mymaster
# - flags: master
# - num-slaves: 1
# - num-other-sentinels: 2
# - quorum: 2
```

### Check Replication Status

```bash
# On master
docker exec redis-master redis-cli -a changeme info replication

# Expected:
# role:master
# connected_slaves:1
# slave0: ip=redis-replica-1, state=online

# On replica
docker exec redis-replica-1 redis-cli -a changeme info replication

# Expected:
# role:slave
# master_host:redis-master
# master_link_status:up
```

### Check Application Connection

```bash
# Application should log Redis mode
docker logs <app-container> | grep "Redis client initialized"

# Expected: "Redis client initialized successfully in sentinel mode"
```

---

## 2. Planned Failover (Maintenance)

**Use Case:** Upgrade master Redis, apply configuration changes, or test HA.

### Step 1: Pre-Failover Checks

```bash
# 1. Verify replication lag is minimal
docker exec redis-master redis-cli -a changeme info replication | grep master_repl_offset
docker exec redis-replica-1 redis-cli -a changeme info replication | grep slave_repl_offset

# Offsets should be within ~100 bytes
```

```bash
# 2. Check application health
curl http://localhost:8000/health

# Expected: 200 OK
```

```bash
# 3. Notify team (if production)
# - Post in #infrastructure Slack channel
# - Update status page
```

### Step 2: Trigger Failover

**Method 1: Stop master (simulates failure)**
```bash
# Stop master
docker stop redis-master

# Sentinels will detect and promote replica (~5-10s)
```

**Method 2: Manual failover (graceful)**
```bash
# Force failover via Sentinel
docker exec redis-sentinel-1 redis-cli -p 26379 \
  sentinel failover mymaster

# This is cleaner as Sentinel orchestrates the switch
```

### Step 3: Monitor Failover Progress

```bash
# Watch sentinel logs in real-time
docker compose -f docker-compose.redis-ha.yml logs -f redis-sentinel-1

# Look for these events:
# +vote-for-leader ...
# +elected-leader ...
# +failover-state-send-slaveof-noone ...
# +failover-end ...
# +switch-master mymaster ...
```

**Expected Timeline:**
- 0-5s: Sentinels detect master down (`+sdown`, `+odown`)
- 5-8s: Quorum reached, leader elected, replica promoted
- 8-10s: New master ready, clients reconnected

### Step 4: Verify New Master

```bash
# Check new master role
docker exec redis-replica-1 redis-cli -a changeme role

# Expected: "master" (was "slave" before)
```

```bash
# Check sentinel view
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel masters

# ip and port should now point to redis-replica-1
```

```bash
# Verify application reconnected
docker logs <app-container> | tail -20

# Should NOT see Redis connection errors
```

### Step 5: Bring Old Master Back as Replica

```bash
# Start old master (will become replica)
docker start redis-master

# Wait for replication sync (~5-10 seconds)
sleep 10

# Verify it's now a replica
docker exec redis-master redis-cli -a changeme role

# Expected: "slave" pointing to redis-replica-1
```

### Step 6: Post-Failover Validation

```bash
# 1. Test write on new master
docker exec redis-replica-1 redis-cli -a changeme SET test:failover "success"
docker exec redis-replica-1 redis-cli -a changeme GET test:failover

# Expected: "success"
```

```bash
# 2. Verify replication to old master (now replica)
sleep 2
docker exec redis-master redis-cli -a changeme GET test:failover

# Expected: "success" (replicated from new master)
```

```bash
# 3. Application health check
curl http://localhost:8000/health

# Expected: 200 OK
```

```bash
# 4. Check sentinel quorum
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel ckquorum mymaster

# Expected: OK 2 usable Sentinels. Quorum and failover authorization can be reached
```

---

## 3. Unplanned Failover (Master Crash)

**Scenario:** Redis master crashes unexpectedly.

### Automatic Recovery

**No manual intervention needed!** Sentinels will:
1. Detect master down within 5 seconds
2. Elect new leader
3. Promote replica to master
4. Reconfigure application clients

**Your job:** Monitor and validate.

### Step 1: Detect Failure

```bash
# Check Sentinel logs for failure events
docker logs redis-sentinel-1 | grep -A5 "+sdown"

# Timestamps will show:
# +sdown (subjective down): One sentinel thinks master is down
# +odown (objective down): Quorum agrees master is down
# +failover-triggered: Automatic failover started
```

### Step 2: Monitor Automatic Failover

```bash
# Follow sentinel logs in real-time
docker compose -f docker-compose.redis-ha.yml logs -f redis-sentinel-1

# Wait for "+switch-master" event
```

### Step 3: Validate Application Health

```bash
# Application should automatically reconnect (no code changes!)
curl http://localhost:8000/health

# If unhealthy, check app logs for Redis errors
docker logs <app-container> | grep -i redis
```

### Step 4: Investigate Root Cause

```bash
# Check why master crashed
docker logs redis-master | tail -100

# Common causes:
# - OOM (maxmemory exceeded)
# - Container killed by OOMKiller
# - Docker daemon restart
# - Network partition
```

### Step 5: Recover Failed Master

```bash
# If container crashed, restart it
docker start redis-master

# It will automatically rejoin as replica
# Verify after 10 seconds
docker exec redis-master redis-cli -a changeme role
```

---

## 4. Failback (Optional)

**Use Case:** Restore original master/replica topology.

### Manual Failback Procedure

```bash
# 1. Verify old master is healthy as replica
docker exec redis-master redis-cli -a changeme info replication

# 2. Trigger failover back to old master
docker exec redis-sentinel-1 redis-cli -p 26379 \
  sentinel failover mymaster

# 3. Wait for switch (5-10s)
# 4. Verify roles reversed
docker exec redis-master redis-cli -a changeme role  # Should be "master"
docker exec redis-replica-1 redis-cli -a changeme role  # Should be "slave"
```

**Note:** Failback is optional. Sentinels handle asymmetry fine.

---

## 5. Troubleshooting

### Issue: Sentinels Can't Reach Master

**Symptoms:**
- `+sdown master mymaster` in sentinel logs
- Master is actually up

**Solution:**
```bash
# Check network connectivity
docker exec redis-sentinel-1 ping redis-master

# Check master is responding
docker exec redis-master redis-cli -a changeme PING

# Check password is correct
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel get-master-addr-by-name mymaster

# Restart sentinel if needed
docker restart redis-sentinel-1
```

### Issue: Quorum Not Reached

**Symptoms:**
- `+odown` but no failover
- Logs: "Not enough good slaves to failover"

**Solution:**
```bash
# Check sentinel count
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel sentinels mymaster

# Should show 2 other sentinels
# If missing, restart sentinel containers
docker restart redis-sentinel-2 redis-sentinel-3
```

### Issue: Split-Brain (Two Masters)

**Symptoms:**
- Both redis-master and redis-replica-1 report role:master

**Solution:**
```bash
# 1. Identify which is the sentinel-approved master
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel get-master-addr-by-name mymaster

# 2. Manually demote the other one
# (Replace <wrong-master> with container name)
docker exec <wrong-master> redis-cli -a changeme SLAVEOF redis-master 6379

# 3. Restart sentinels to resync state
docker compose -f docker-compose.redis-ha.yml restart redis-sentinel-{1,2,3}
```

### Issue: Application Not Reconnecting

**Symptoms:**
- Failover succeeded but app still reports Redis errors

**Solution:**
```bash
# 1. Check app is using Sentinel mode
docker logs <app-container> | grep "Redis.*sentinel"

# 2. Verify sentinel addresses in app config
# Should be: redis-sentinel-1:26379,redis-sentinel-2:26379,redis-sentinel-3:26379

# 3. Restart app to force reconnect
docker restart <app-container>

# 4. Check app can reach sentinels
docker exec <app-container> nc -zv redis-sentinel-1 26379
```

### Issue: Slow Failover (>15 seconds)

**Possible Causes:**
- `down-after-milliseconds` too high (default: 5000ms)
- Network latency between sentinels
- Heavy load on Redis master

**Solution:**
```bash
# Reduce down-after-milliseconds (careful in production!)
docker exec redis-sentinel-1 redis-cli -p 26379 \
  sentinel set mymaster down-after-milliseconds 3000

# This change persists across restarts in sentinel.conf
```

---

## 6. Metrics to Monitor

### Key Metrics

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Failover time | <10s | 10-15s | >15s |
| Replication lag | <100 bytes | 100-1KB | >1KB |
| Sentinel quorum | 3/3 | 2/3 | <2/3 |
| Master uptime | >24h | 1-24h | <1h (frequent restarts) |

### Dashboard Queries (Prometheus)

```promql
# Failover events
increase(redis_sentinel_failovers_total[1h])

# Replication lag
redis_connected_slaves_lag_seconds

# Sentinel health
up{job="redis-sentinel"}
```

---

## 7. Rollback to Single Mode

**When to use:** Sentinel is causing instability, need to revert temporarily.

### Procedure

```bash
# 1. Update .env
REDIS_MODE=single
REDIS_HOST=redis-master
REDIS_PORT=6379
# Comment out REDIS_SENTINELS

# 2. Restart application
docker restart <app-container>

# App will now connect directly to master (no HA)

# 3. Stop Sentinel stack (after traffic drains)
docker compose -f docker-compose.redis-ha.yml down

# Note: This is a temporary measure. Fix Sentinel issues and re-enable!
```

---

## 8. Common Commands Reference

```bash
# Sentinel info
docker exec redis-sentinel-1 redis-cli -p 26379 info sentinel

# Check all masters
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel masters

# Check master address
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel get-master-addr-by-name mymaster

# Check sentinel peers
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel sentinels mymaster

# Check master replicas
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel replicas mymaster

# Force failover
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel failover mymaster

# Reset sentinel (dangerous! loses state)
docker exec redis-sentinel-1 redis-cli -p 26379 sentinel reset mymaster
```

---

## 9. Incident Response Checklist

### During Incident

- [ ] Confirm master is down (check `docker ps`, sentinel logs)
- [ ] Verify sentinels detected failure (`+sdown`, `+odown` events)
- [ ] Wait for automatic failover (5-10s)
- [ ] Check application health (`/health` endpoint)
- [ ] Verify new master is serving traffic
- [ ] Post incident update to #incidents channel

### Post-Incident

- [ ] Recover failed master as replica
- [ ] Investigate root cause (OOM, crash, network)
- [ ] Document in incident log
- [ ] Update monitoring/alerting if needed
- [ ] Schedule postmortem (for critical incidents)

---

## 10. Contact Information

- **On-Call Engineer:** [PagerDuty](https://pagerduty.com)
- **Slack Channel:** #infrastructure
- **Runbook Source:** `docs/runbooks/redis_ha_failover.md`
- **Related Docs:**
  - [Week 1 Quick Start](../WEEK1_QUICKSTART.md)
  - [Cache Rollout Runbook](./cache_rollout.md)

---

**End of Runbook**
