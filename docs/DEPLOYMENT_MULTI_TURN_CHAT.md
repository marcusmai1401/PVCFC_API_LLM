# Deployment Guide: Multi-Turn Chat

## Quick Deployment Steps

### Step 1: Install Dependencies

```powershell
# Make sure you're in the project directory
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# Install/upgrade redis if needed (already in requirements.txt)
pip install redis==5.0.1

# Or install all requirements
pip install -r requirements.txt
```

### Step 2: Configure Environment

```powershell
# Copy env.example to .env if not already done
if (!(Test-Path ".env")) {
    Copy-Item "env.example" ".env"
}

# Edit .env and configure:
# - GEMINI_API_KEY or OPENAI_API_KEY
# - LLM_PROVIDER=gemini or openai
# - LLM_MODEL_LIGHT and LLM_MODEL_HEAVY

# Redis is pre-configured with defaults:
# REDIS_URL=redis://localhost:6379
# CONVERSATION_TTL_HOURS=24
# MAX_TURNS_PER_CONVERSATION=50
# MAX_CONVERSATION_CONTEXT_TOKENS=8000
# SUMMARIZE_EVERY_N_TURNS=8
# ENABLE_PII_REDACTION=true
```

### Step 3: Start Redis

```powershell
# Start Redis with docker-compose
docker-compose up -d redis

# Verify Redis is running
docker ps | Select-String redis

# Test connection
docker exec pvcfc_redis redis-cli ping
# Should return: PONG
```

### Step 4: Start API Server

```powershell
# Option 1: Use convenience script
.\launchers\start_with_redis.ps1

# Option 2: Manual start
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 5: Verify Deployment

```powershell
# Check health endpoint
curl http://localhost:8000/healthz | ConvertFrom-Json

# Should include:
# {
#   "status": "healthy",
#   "conversation_manager": {
#     "status": "healthy",
#     "redis_connected": true,
#     "total_conversations": 0
#   }
# }
```

### Step 6: Test Multi-Turn

See `docs/MULTI_TURN_CHAT_TESTING.md` for comprehensive tests.

Quick test:

```powershell
# Turn 1
$t1 = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body '{"query":"What is K06101?","language":"en"}'

$convId = $t1.conversation_id
Write-Host "Conversation ID: $convId"

# Turn 2
$t2 = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body "{`"query`":`"What is its pressure?`",`"conversation_id`":`"$convId`",`"language`":`"en`"}"

Write-Host "Answer: $($t2.answer)"
Write-Host "Turn count: $($t2.conversation_turn_count)"
```

## Production Considerations

### Redis Security

For production, set a password:

```ini
# In .env
REDIS_PASSWORD=your_secure_password_here
```

Update docker-compose.yml:

```yaml
services:
  redis:
    command: redis-server --appendonly yes --requirepass your_secure_password_here
```

### Redis Persistence

Redis is configured with AOF (Append-Only File) persistence by default:

```yaml
command: redis-server --appendonly yes
```

For additional safety, enable RDB snapshots:

```yaml
command: redis-server --appendonly yes --save 60 1000
```

This saves to disk every 60 seconds if 1000+ keys changed.

### Scaling Considerations

For high-availability:

1. **Redis Sentinel** (automatic failover)
2. **Redis Cluster** (sharding for >10k conversations)
3. **Separate Redis instance** from other services

### Monitoring

Monitor these metrics:

```powershell
# Redis memory usage
docker exec pvcfc_redis redis-cli INFO memory | Select-String "used_memory_human"

# Number of conversations
docker exec pvcfc_redis redis-cli DBSIZE

# Check for errors
docker logs pvcfc_redis --tail 50
```

### Backup & Recovery

Redis data is in Docker volume `redis_data`.

Backup:

```powershell
docker exec pvcfc_redis redis-cli SAVE
docker cp pvcfc_redis:/data/dump.rdb ./backups/redis_backup_$(Get-Date -Format 'yyyyMMdd').rdb
```

Restore:

```powershell
docker stop pvcfc_redis
docker cp ./backups/redis_backup_20251020.rdb pvcfc_redis:/data/dump.rdb
docker start pvcfc_redis
```

## Rollback Plan

If issues occur:

### Option 1: Disable Conversation Features

```ini
# In .env
CONVERSATION_TTL_HOURS=0  # Effectively disables
```

Restart API. System falls back to single-turn mode.

### Option 2: Stop Redis

```powershell
docker stop pvcfc_redis
```

API will gracefully degrade to single-turn mode (no errors).

### Option 3: Code Rollback

Since changes are backward compatible, you can:

```powershell
git revert <commit_hash>
```

Or manually remove conversation-related code.

## Configuration Tuning

### Conversation TTL

Adjust based on usage patterns:

```ini
# Short sessions (chatbot-style)
CONVERSATION_TTL_HOURS=2

# Medium sessions (work day)
CONVERSATION_TTL_HOURS=12

# Long sessions (multi-day projects)
CONVERSATION_TTL_HOURS=72
```

### Summarization Frequency

```ini
# Frequent summarization (save tokens)
SUMMARIZE_EVERY_N_TURNS=5

# Less frequent (keep more context)
SUMMARIZE_EVERY_N_TURNS=12
```

### Token Budget

```ini
# Smaller budget (cost optimization)
MAX_CONVERSATION_CONTEXT_TOKENS=4000

# Larger budget (quality optimization)
MAX_CONVERSATION_CONTEXT_TOKENS=16000
```

## Troubleshooting

### Issue: "ConversationManager not initialized"

**Cause**: Redis connection failed on startup

**Solution**:
1. Check Redis is running: `docker ps | Select-String redis`
2. Check Redis health: `docker exec pvcfc_redis redis-cli ping`
3. Check API logs for Redis connection errors
4. Verify `REDIS_URL` in `.env`

### Issue: Conversations expire too quickly

**Cause**: TTL too short

**Solution**: Increase `CONVERSATION_TTL_HOURS` in `.env`

### Issue: High Redis memory usage

**Cause**: Too many active conversations

**Solutions**:
1. Reduce TTL to expire sooner
2. Reduce `MAX_TURNS_PER_CONVERSATION`
3. Enable more aggressive summarization
4. Increase Redis memory limit in docker-compose.yml

### Issue: Summarization not working

**Cause**: LLM not configured or fails

**Solution**:
1. Check LLM configuration in `.env`
2. Verify API keys are valid
3. Check logs for summarization errors
4. Summarization uses light-tier LLM (check `LLM_MODEL_LIGHT`)

## Performance Optimization

### Reduce Latency

```ini
# Use faster summarization
SUMMARIZE_EVERY_N_TURNS=12  # Less frequent

# Smaller history window
MAX_TURNS_PER_CONVERSATION=20
```

### Reduce Costs

```ini
# More aggressive summarization
SUMMARIZE_EVERY_N_TURNS=5

# Smaller token budget
MAX_CONVERSATION_CONTEXT_TOKENS=4000

# Use cheaper light model for summarization
LLM_MODEL_LIGHT=gemini-2.5-flash
```

### Improve Quality

```ini
# Keep more history
MAX_TURNS_PER_CONVERSATION=100
MAX_CONVERSATION_CONTEXT_TOKENS=12000

# Less frequent summarization
SUMMARIZE_EVERY_N_TURNS=15
```

## Best Practices

1. **Start Small**: Use default settings first, tune based on metrics
2. **Monitor Redis**: Track memory and key count
3. **Review Logs**: Check for conversation errors
4. **Test Thoroughly**: Use provided test guide before production
5. **Backup Redis**: Regular backups if persistence is critical

## Support

- **User Guide**: `docs/MULTI_TURN_CHAT_GUIDE.md`
- **Testing**: `docs/MULTI_TURN_CHAT_TESTING.md`
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`
- **Changelog**: `CHANGELOG.md`
