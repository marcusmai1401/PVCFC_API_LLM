# Multi-Turn Chat Testing Guide

Quick validation steps for the multi-turn conversation feature.

## Prerequisites

1. Redis is running:
   ```powershell
   docker-compose up -d redis
   docker exec pvcfc_redis redis-cli ping  # Should return PONG
   ```

2. API server is running:
   ```powershell
   .\launchers\start_with_redis.ps1
   # Or
   uvicorn app.main:app --reload
   ```

## Test 1: Health Check

Verify Redis is connected:

```powershell
curl http://localhost:8000/healthz | ConvertFrom-Json | Select-Object -ExpandProperty conversation_manager
```

Expected output:
```json
{
  "status": "healthy",
  "redis_connected": true,
  "total_conversations": 0,
  "ttl_hours": 24
}
```

## Test 2: Single-Turn (Backward Compatibility)

Verify single-turn queries still work:

```powershell
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body '{"query":"What is CO2 compressor?","language":"en","max_context":5}'

# Check response has conversation_id
$response.conversation_id
$response.is_new_conversation  # Should be True
```

## Test 3: Multi-Turn Conversation

### Turn 1: Start conversation

```powershell
$turn1 = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body '{"query":"What is K06101?","language":"en","max_context":5}'

# Save conversation ID
$convId = $turn1.conversation_id
Write-Host "Conversation ID: $convId"
Write-Host "Turn count: $($turn1.conversation_turn_count)"
```

### Turn 2: Continue conversation

```powershell
$turn2 = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body "{`"query`":`"What is its operating pressure?`",`"conversation_id`":`"$convId`",`"language`":`"en`",`"max_context`":5}"

Write-Host "`nAnswer: $($turn2.answer)"
Write-Host "Same conversation: $($turn2.conversation_id -eq $convId)"
Write-Host "Is new: $($turn2.is_new_conversation)"  # Should be False
Write-Host "Turn count: $($turn2.conversation_turn_count)"  # Should be 4
```

### Turn 3: Test context inference

```powershell
$turn3 = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body "{`"query`":`"What about temperature?`",`"conversation_id`":`"$convId`",`"language`":`"en`",`"max_context`":5}"

Write-Host "`nAnswer: $($turn3.answer)"
# Should infer "temperature of K06101" from context
```

## Test 4: Verify Persistence

### Check Redis data:

```powershell
# List all conversations
docker exec pvcfc_redis redis-cli KEYS "conv:meta:*"

# Get conversation metadata
docker exec pvcfc_redis redis-cli GET "conv:meta:$convId"

# Get conversation history
docker exec pvcfc_redis redis-cli LRANGE "conv:history:$convId" 0 -1
```

## Test 5: PII Redaction

Test that sensitive info is redacted:

```powershell
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body '{"query":"My email is test@example.com and phone is 0901234567","language":"en"}'

$convId = $response.conversation_id

# Check Redis data - should have [EMAIL_REDACTED] and [PHONE_REDACTED]
docker exec pvcfc_redis redis-cli LRANGE "conv:history:$convId" 0 -1
```

## Test 6: Streamlit UI

1. Start Streamlit:
   ```powershell
   cd streamlit_app
   streamlit run app.py
   ```

2. Navigate to "RAG Query" page

3. Enter a query: "What is K06101?"

4. Check that conversation indicator shows:
   - "Active: ...{last 8 chars of conv_id}"
   - Turn count

5. Enter follow-up: "What is its pressure?"

6. Verify answer infers context from previous turn

7. Click "New Conversation" button

8. Verify new conversation starts (different ID)

## Test 7: Summarization (Long Conversation)

```powershell
# Create a conversation and add 10+ turns to trigger summarization
$convId = $null

1..12 | ForEach-Object {
    $query = "Question number $_"
    $body = if ($convId) {
        "{`"query`":`"$query`",`"conversation_id`":`"$convId`",`"language`":`"en`"}"
    } else {
        "{`"query`":`"$query`",`"language`":`"en`"}"
    }

    $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
      -ContentType "application/json" `
      -Body $body

    if (-not $convId) { $convId = $response.conversation_id }
    Write-Host "Turn $_ : $($response.conversation_turn_count) total turns"
}

# After 8 turns, summarization should have occurred (check logs)
```

Check API logs for:
```
[INFO] Summarized conversation
```

## Test 8: Graceful Degradation

### Stop Redis:

```powershell
docker stop pvcfc_redis
```

### Send query:

```powershell
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ask" `
  -ContentType "application/json" `
  -Body '{"query":"Test query","language":"en"}'

# Should still work (falls back to single-turn)
$response.conversation_id  # Should be null
```

### Restart Redis:

```powershell
docker start pvcfc_redis
```

## Expected Results

All tests should pass with:
- ✅ Conversations persist in Redis
- ✅ Context is maintained across turns
- ✅ Backward compatibility preserved
- ✅ PII is redacted
- ✅ Summarization triggers after N turns
- ✅ Graceful degradation when Redis unavailable
- ✅ UI shows conversation state correctly

## Troubleshooting

### Redis connection failed
```
Error: Failed to connect to Redis
```
**Solution**: Start Redis with `docker-compose up -d redis`

### Conversation not found
```
Conversation not found or expired
```
**Solution**: Conversation TTL expired (24h). Start a new conversation.

### No conversation_id in response
```
Response missing conversation_id field
```
**Solution**: Conversation manager failed to initialize. Check Redis connection.

## Performance Benchmarks

Expected latencies:
- First turn (create): +10-15ms
- Subsequent turns: +5-10ms
- Summarization: +1000ms (every 8 turns)
- Single-turn: 0ms added

## Next Steps

After validation:
1. Update production .env with Redis configuration
2. Monitor Redis memory usage
3. Adjust TTL/limits based on usage patterns
4. Consider Redis persistence configuration (AOF/RDB)
