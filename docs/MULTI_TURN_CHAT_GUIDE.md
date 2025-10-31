# Multi-Turn Conversation Guide

## Overview

The PVCFC RAG API now supports multi-turn conversations, allowing users to have contextual dialogues where the system remembers previous questions and answers.

## Features

- **Persistent Conversations**: Conversations are stored in Redis with 24-hour TTL
- **Automatic Context**: System infers references like "it", "that", "the equipment" from conversation history
- **Conversation Summarization**: Long conversations are automatically summarized to manage token budget
- **PII Redaction**: Sensitive information is redacted before storage (configurable)
- **Backward Compatible**: Single-turn queries work exactly as before

## Quick Start

### Starting a New Conversation

Simply send a query without `conversation_id`:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is K06101?",
    "language": "en"
  }'
```

Response will include a `conversation_id`:

```json
{
  "answer": "K06101 is a CO2 compressor...",
  "conversation_id": "a1b2c3d4-e5f6-...",
  "is_new_conversation": true,
  "conversation_turn_count": 2,
  ...
}
```

### Continuing a Conversation

Include the `conversation_id` in subsequent requests:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is its operating pressure?",
    "conversation_id": "a1b2c3d4-e5f6-...",
    "language": "en"
  }'
```

The system will understand "its" refers to K06101 from the previous turn.

## Configuration

Environment variables in `.env`:

```ini
# Redis connection
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=  # Optional

# Conversation limits
CONVERSATION_TTL_HOURS=24
MAX_TURNS_PER_CONVERSATION=50
MAX_CONVERSATION_CONTEXT_TOKENS=8000

# Summarization
SUMMARIZE_EVERY_N_TURNS=8

# Optional features
ENABLE_PROVIDER_SESSION=false  # Use Gemini ChatSession
ENABLE_PII_REDACTION=true
```

## Architecture

### Short-term Memory (Redis)

- Conversations stored in Redis with TTL
- Automatic cleanup after expiration
- Scales horizontally (shared state across API instances)

### History Management

- Recent turns kept in full
- Older turns summarized periodically
- Token budget enforcement

### Summarization

Every N turns (default: 8), the system:
1. Summarizes oldest turns using light-tier LLM
2. Keeps summary + recent turns for context
3. Stays within token budget

## Streamlit UI

The UI automatically manages conversations:

1. **New Conversation Button**: Start fresh conversation
2. **Active Conversation Indicator**: Shows conversation ID and turn count
3. **Automatic Continuation**: Next query uses same conversation

## API Reference

### Request Schema

```json
{
  "query": "string (required)",
  "conversation_id": "string | null (optional)",
  "user_id": "string | null (optional)",
  "language": "vi | en",
  "max_context": 8,
  ...
}
```

### Response Schema

```json
{
  "answer": "string",
  "citations": [...],
  "confidence": 0.95,
  "conversation_id": "string",
  "is_new_conversation": true,
  "conversation_turn_count": 2,
  ...
}
```

## Examples

### Example 1: Equipment Query

**Turn 1:**
```
User: "What is pump P04201A?"
Assistant: "P04201A is a centrifugal pump used for... [citations]"
```

**Turn 2:**
```
User: "What is its flow rate?"
# System infers "its" = P04201A from Turn 1
Assistant: "P04201A has a flow rate of 150 m³/h... [citations]"
```

### Example 2: Clarification

**Turn 1:**
```
User: "máy nén"  (compressor - ambiguous)
Assistant: "We have several compressors. Could you specify..."
```

**Turn 2:**
```
User: "K06101"
Assistant: "K06101 is a CO2 compressor with..."
```

**Turn 3:**
```
User: "áp suất của nó?"  (its pressure?)
# System knows "nó" = K06101
Assistant: "K06101 operates at 15 bar..."
```

## Troubleshooting

### Conversation Not Found

If you get a "conversation not found" error:
- Conversation may have expired (24h TTL)
- Redis may be unavailable
- Start a new conversation

### Redis Connection Failed

If Redis is unavailable:
- System falls back to single-turn mode
- No error thrown, just no conversation persistence
- Check `GET /healthz` for Redis status

### Token Budget Exceeded

If conversations are very long:
- Automatic summarization kicks in every 8 turns
- Oldest turns are summarized and condensed
- Recent turns kept in full

## Testing

Run tests:

```bash
# Unit tests
pytest tests/test_conversation_manager.py -v

# Integration tests (requires Redis)
pytest tests/test_conversation_integration.py -v
```

## Monitoring

Check Redis health:

```bash
curl http://localhost:8000/healthz | jq '.conversation_manager'
```

Expected output:

```json
{
  "status": "healthy",
  "redis_connected": true,
  "total_conversations": 42,
  "ttl_hours": 24
}
```

## Best Practices

1. **Use conversation_id**: Always include it for multi-turn
2. **Start fresh**: Use "New Conversation" button for unrelated topics
3. **Be specific**: First turn should establish context clearly
4. **Check turn count**: Monitor to avoid very long conversations

## Limitations

- Maximum 50 turns per conversation (configurable)
- 24-hour conversation lifetime (configurable)
- Token budget: 8000 tokens (configurable)
- No cross-user conversation sharing (privacy)

## Future Enhancements

- Long-term memory (vector DB for persistent facts)
- Conversation export/import
- User-specific conversation history
- Conversation analytics and insights
