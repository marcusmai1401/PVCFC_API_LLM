# Multi-Turn Chat - Quick Reference Card

## 1-Minute Setup

```powershell
# 1. Start Redis
docker-compose up -d redis

# 2. Start API
uvicorn app.main:app --reload

# 3. Verify
curl http://localhost:8000/healthz
```

## API Usage

### Start Conversation

```bash
POST /ask
{
  "query": "What is K06101?",
  "language": "en"
}

# Response includes conversation_id
```

### Continue Conversation

```bash
POST /ask
{
  "query": "What is its pressure?",
  "conversation_id": "<from-previous-response>",
  "language": "en"
}

# System understands "its" = K06101
```

### New Conversation

Simply omit `conversation_id` or send a different one.

## Configuration (.env)

```ini
REDIS_URL=redis://localhost:6379
CONVERSATION_TTL_HOURS=24
MAX_TURNS_PER_CONVERSATION=50
MAX_CONVERSATION_CONTEXT_TOKENS=8000
SUMMARIZE_EVERY_N_TURNS=8
ENABLE_PII_REDACTION=true
```

## Common Commands

```powershell
# Check Redis health
docker exec pvcfc_redis redis-cli ping

# View conversations
docker exec pvcfc_redis redis-cli KEYS "conv:meta:*"

# Check API health
curl http://localhost:8000/healthz | ConvertFrom-Json | Select -ExpandProperty conversation_manager

# Run tests
pytest tests/test_conversation_*.py -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis not connecting | `docker-compose up -d redis` |
| Module not found: redis | `pip install redis==5.0.1` |
| Conversation expired | Normal after 24h, start new |
| No conversation_id | Redis unavailable, check health |

## Features

- ✅ Context memory across turns
- ✅ Auto-summarization (every 8 turns)
- ✅ PII redaction (emails, phones)
- ✅ 24-hour conversation lifetime
- ✅ Horizontal scaling ready
- ✅ Backward compatible

## Limits

- 50 turns max per conversation
- 24 hours TTL
- 8000 tokens context budget
- Auto-trim oldest turns

## Documentation

- Full guide: `docs/MULTI_TURN_CHAT_GUIDE.md`
- Testing: `docs/MULTI_TURN_CHAT_TESTING.md`
- Deployment: `docs/DEPLOYMENT_MULTI_TURN_CHAT.md`
