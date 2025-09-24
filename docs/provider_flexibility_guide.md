# LLM Provider Flexibility Guide

## Overview

The PVCFC RAG API system is designed with **maximum flexibility** for switching between different LLM providers and models. You can easily change providers without modifying any application code - just update configuration and restart.

## Current Architecture

### 1. Multi-Tier Support
The system supports two tiers of LLM models:
- **Light Tier**: Fast and cost-effective (for simple queries)
- **Heavy Tier**: High quality (for complex analysis)

### 2. Supported Providers

#### Currently Implemented
- **Gemini** (Google)
  - Models: gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-pro, etc.
- **OpenAI**
  - Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, etc.

#### Embeddings
- **Local** (sentence-transformers)
  - Models: BAAI/bge-small-en-v1.5, all-MiniLM-L6-v2, etc.
- **OpenAI** (ready to implement)
  - Models: text-embedding-3-small, text-embedding-3-large

### 3. Configuration Methods

#### A. Environment Variables (.env file)
```env
# Main LLM Provider
LLM_PROVIDER=gemini              # or openai
LLM_MODEL_LIGHT=gemini-2.5-flash
LLM_MODEL_HEAVY=gemini-2.5-pro

# Optional: Different provider for light tier
LLM_LIGHT_PROVIDER=gemini        # Can differ from main provider

# Embedding Provider
EMBEDDING_PROVIDER=local         # or openai
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# API Keys
GEMINI_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here     # If using OpenAI
```

#### B. Programmatic Override
```python
from app.services.llm_client import LLMClientFactory

# Use configuration from .env
client = LLMClientFactory.create_client(tier="light")

# Override with specific provider
client = LLMClientFactory.create_client(
    provider="openai",
    model="gpt-4o",
    api_key="sk-..."
)
```

## Switching Scenarios

### Scenario 1: Switch from Gemini to OpenAI

**Step 1**: Update `.env`
```env
LLM_PROVIDER=openai
LLM_MODEL_LIGHT=gpt-4o-mini
LLM_MODEL_HEAVY=gpt-4o
OPENAI_API_KEY=sk-your-key-here
```

**Step 2**: Restart application
```bash
# Restart the server
make run
```

That's it! The application now uses OpenAI.

### Scenario 2: Use Different Providers for Different Tiers

Want to use Gemini for fast responses but OpenAI for high-quality?

```env
# Heavy tier uses OpenAI
LLM_PROVIDER=openai
LLM_MODEL_HEAVY=gpt-4o

# Light tier uses Gemini (override)
LLM_LIGHT_PROVIDER=gemini
LLM_MODEL_LIGHT=gemini-2.5-flash

# Need both API keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
```

### Scenario 3: Switch Embedding Provider

Change from local embeddings to OpenAI:

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-...
```

### Scenario 4: Test New Models

Try experimental or new models without code changes:

```env
# Try Gemini 2.0 Flash Experimental
LLM_MODEL_LIGHT=gemini-2.0-flash-exp

# Or try GPT-4 Turbo
LLM_MODEL_HEAVY=gpt-4-turbo-preview
```

## Production Deployment

### 1. Using Docker

```bash
docker run \
  -e LLM_PROVIDER=openai \
  -e LLM_MODEL_LIGHT=gpt-4o-mini \
  -e LLM_MODEL_HEAVY=gpt-4o \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  pvcfc-rag-api
```

### 2. Using Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-config
data:
  LLM_PROVIDER: "openai"
  LLM_MODEL_LIGHT: "gpt-4o-mini"
  LLM_MODEL_HEAVY: "gpt-4o"
---
apiVersion: v1
kind: Secret
metadata:
  name: llm-secrets
data:
  OPENAI_API_KEY: <base64-encoded-key>
```

### 3. Using Cloud Services

**AWS Parameter Store**:
```bash
aws ssm put-parameter --name /pvcfc/llm_provider --value openai
aws ssm put-parameter --name /pvcfc/openai_api_key --value sk-... --type SecureString
```

**Azure Key Vault**:
```bash
az keyvault secret set --vault-name pvcfc --name LLM-PROVIDER --value openai
az keyvault secret set --vault-name pvcfc --name OPENAI-API-KEY --value sk-...
```

## Cost Optimization Strategies

### 1. Use Tiered Approach
```python
# In your API endpoint
if request.requires_high_quality:
    client = get_llm_client(tier="heavy")  # Expensive but accurate
else:
    client = get_llm_client(tier="light")  # Cheap and fast
```

### 2. Implement Fallback
```python
try:
    # Try expensive model first
    client = get_llm_client(tier="heavy")
    response = client.generate(prompt, timeout=5)
except (TimeoutError, RateLimitError):
    # Fallback to cheaper model
    client = get_llm_client(tier="light")
    response = client.generate(prompt)
```

### 3. Cache Responses
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_response(prompt_hash):
    client = get_llm_client(tier="light")
    return client.generate(prompt)
```

## Adding New Providers

To add a new LLM provider:

1. **Create Client Class**:
```python
# app/services/llm_client.py
class AnthropicClient(BaseLLMClient):
    def generate(self, prompt, **kwargs):
        # Implementation
        pass
```

2. **Register Provider**:
```python
LLMClientFactory.register_provider("anthropic", AnthropicClient)
```

3. **Update Config**:
```env
LLM_PROVIDER=anthropic
LLM_MODEL_HEAVY=claude-3-opus
ANTHROPIC_API_KEY=...
```

## Testing Provider Changes

### 1. Test Current Configuration
```bash
python tools/test_provider_flexibility.py
```

### 2. Test Specific Provider
```bash
python tools/test_gemini_2_5.py  # Test Gemini models
```

### 3. Test Hybrid Search
```bash
python tools/test_hybrid_search.py  # Uses configured embedding provider
```

## Monitoring and Debugging

### Check Current Configuration
```python
from app.core.config import settings

print(f"Provider: {settings.llm_provider}")
print(f"Light Model: {settings.llm_model_light}")
print(f"Heavy Model: {settings.llm_model_heavy}")
print(f"Embedding: {settings.embedding_provider}")
```

### Track Usage
```python
# Response includes usage information
response = client.generate(prompt)
print(f"Tokens used: {response.usage}")
print(f"Provider: {response.provider}")
print(f"Model: {response.model}")
```

## Best Practices

1. **Never hardcode providers or models** - Always use configuration
2. **Test provider changes in staging** before production
3. **Monitor costs** when switching providers
4. **Keep API keys secure** - Use secrets management
5. **Document model behavior differences** for your use cases
6. **Set up alerts** for API errors or rate limits
7. **Have fallback strategies** for high availability

## Summary

The system provides:
- ✅ **Zero-code provider switching** via configuration
- ✅ **Multi-provider support** (different providers for different tasks)
- ✅ **Tier-based selection** (light vs heavy)
- ✅ **Programmatic override** when needed
- ✅ **Production-ready** configuration management
- ✅ **Cost optimization** through smart tier selection
- ✅ **Easy extensibility** for new providers

This flexibility ensures you can:
- Optimize costs by choosing appropriate models
- Switch providers based on availability or pricing
- Test new models without code changes
- Maintain high availability with fallback options
- Scale efficiently with tier-based selection
