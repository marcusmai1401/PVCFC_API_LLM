#!/usr/bin/env python
"""
Test LLM Provider Flexibility
Demonstrates how easy it is to switch between different LLM providers and models
"""
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.llm_client import LLMClientFactory, get_llm_client


def test_configuration_based():
    """Test using configuration from .env file"""
    logger.info("=== Testing Configuration-Based LLM Selection ===")

    # Current configuration
    logger.info(f"Current .env configuration:")
    logger.info(f"  LLM_PROVIDER: {settings.llm_provider}")
    logger.info(f"  LLM_MODEL_LIGHT: {settings.llm_model_light}")
    logger.info(f"  LLM_MODEL_HEAVY: {settings.llm_model_heavy}")
    logger.info(f"  EMBEDDING_PROVIDER: {settings.embedding_provider}")
    logger.info(f"  EMBEDDING_MODEL: {settings.embedding_model}")

    try:
        # Test light tier (default)
        logger.info("\n1. Light Tier (fast & cheap):")
        client_light = get_llm_client(tier="light")
        logger.info(f"   Provider: {client_light.provider}")
        logger.info(f"   Model: {client_light.model}")

        # Test heavy tier
        logger.info("\n2. Heavy Tier (high quality):")
        client_heavy = get_llm_client(tier="heavy")
        logger.info(f"   Provider: {client_heavy.provider}")
        logger.info(f"   Model: {client_heavy.model}")

        # Test actual generation
        logger.info("\n3. Testing actual generation with light tier:")
        response = client_light.generate(
            prompt="What is RAG in one sentence?", temperature=0.5, max_tokens=50
        )
        logger.info(f"   Response: {response.content}")
        logger.info(f"   Tokens used: {response.usage}")

    except Exception as e:
        logger.error(f"Error: {e}")


def demonstrate_switching():
    """Demonstrate how to switch providers programmatically"""
    logger.info("\n=== Demonstrating Provider Switching ===")

    scenarios = [
        {
            "name": "Scenario 1: Switch to OpenAI GPT-4o",
            "env_changes": {
                "LLM_PROVIDER": "openai",
                "LLM_MODEL_HEAVY": "gpt-4o",
                "OPENAI_API_KEY": "sk-your-key-here",
            },
        },
        {
            "name": "Scenario 2: Use Gemini for light, OpenAI for heavy",
            "env_changes": {
                "LLM_PROVIDER": "openai",  # Heavy tier
                "LLM_LIGHT_PROVIDER": "gemini",  # Light tier override
                "LLM_MODEL_LIGHT": "gemini-2.5-flash",
                "LLM_MODEL_HEAVY": "gpt-4o",
            },
        },
        {
            "name": "Scenario 3: Switch embedding to OpenAI",
            "env_changes": {
                "EMBEDDING_PROVIDER": "openai",
                "EMBEDDING_MODEL": "text-embedding-3-small",
                "OPENAI_API_KEY": "sk-your-key-here",
            },
        },
        {
            "name": "Scenario 4: Use different Gemini models",
            "env_changes": {
                "LLM_MODEL_LIGHT": "gemini-2.0-flash-exp",  # Experimental
                "LLM_MODEL_HEAVY": "gemini-1.5-pro-002",  # Stable
            },
        },
    ]

    for scenario in scenarios:
        logger.info(f"\n{scenario['name']}:")
        logger.info("  Required .env changes:")
        for key, value in scenario["env_changes"].items():
            logger.info(f"    {key}={value}")
        logger.info("  Then restart the application to apply changes.")


def test_programmatic_override():
    """Test programmatic override of configuration"""
    logger.info("\n=== Testing Programmatic Override ===")

    logger.info("You can override configuration programmatically:")
    logger.info("")
    logger.info("# Example 1: Force specific provider/model")
    logger.info("client = LLMClientFactory.create_client(")
    logger.info('    provider="openai",')
    logger.info('    model="gpt-4-turbo",')
    logger.info('    api_key="sk-..."')
    logger.info(")")
    logger.info("")
    logger.info("# Example 2: Use in API endpoint")
    logger.info("async def ask(request: AskRequest):")
    logger.info("    # Dynamically choose based on request")
    logger.info("    if request.high_quality:")
    logger.info('        client = get_llm_client(tier="heavy")')
    logger.info("    else:")
    logger.info('        client = get_llm_client(tier="light")')
    logger.info("")
    logger.info("    response = client.generate(request.query)")
    logger.info("    return response")


def show_production_recommendations():
    """Show recommendations for production deployment"""
    logger.info("\n=== Production Deployment Recommendations ===")

    recommendations = [
        "1. **Use environment variables in production** (not .env file)",
        "   - Set via Docker: docker run -e LLM_PROVIDER=openai ...",
        "   - Set via Kubernetes: ConfigMap or Secrets",
        "   - Set via cloud: AWS Parameter Store, Azure Key Vault, etc.",
        "",
        "2. **Implement fallback logic** for high availability:",
        "   ```python",
        "   try:",
        "       client = get_llm_client(tier='heavy')  # Primary",
        "   except Exception:",
        "       client = get_llm_client(tier='light')  # Fallback",
        "   ```",
        "",
        "3. **Use different tiers for different use cases**:",
        "   - Light tier: Real-time chat, simple queries",
        "   - Heavy tier: Complex analysis, report generation",
        "",
        "4. **Monitor costs and performance**:",
        "   - Track token usage per provider",
        "   - Set alerts for cost thresholds",
        "   - Use caching to reduce API calls",
        "",
        "5. **Test provider switching in staging**:",
        "   - Ensure all providers work with your prompts",
        "   - Compare quality/cost trade-offs",
        "   - Have rollback plan ready",
    ]

    for rec in recommendations:
        logger.info(rec)


def main():
    """Run all demonstrations"""
    logger.info("LLM Provider Flexibility Test")
    logger.info("=" * 50)

    # Test current configuration
    test_configuration_based()

    # Show how to switch providers
    demonstrate_switching()

    # Show programmatic override
    test_programmatic_override()

    # Production recommendations
    show_production_recommendations()

    logger.info("\n" + "=" * 50)
    logger.info("Summary: The system is designed for easy provider switching!")
    logger.info("- Change providers via .env file (restart required)")
    logger.info("- Override programmatically when needed")
    logger.info("- Support for multiple providers simultaneously")
    logger.info("- Ready for production with proper configuration management")


if __name__ == "__main__":
    main()
