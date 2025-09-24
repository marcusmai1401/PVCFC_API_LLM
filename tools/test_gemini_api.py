#!/usr/bin/env python
"""
Test Gemini API connectivity and functionality
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

from loguru import logger

from app.services.llm_client import get_llm_client


def test_gemini_connection():
    """Test basic Gemini API connection"""
    logger.info("Testing Gemini API connection...")

    try:
        # Test with different model names
        models_to_test = [
            "gemini-2.0-flash-exp",  # Latest experimental
            "gemini-1.5-flash",  # Stable version
            "gemini-1.5-pro",  # Pro version
        ]

        for model_name in models_to_test:
            logger.info(f"\nTesting model: {model_name}")
            try:
                # Override model in environment BEFORE importing
                os.environ["LLM_MODEL_LIGHT"] = model_name
                os.environ["GEMINI_MODEL_LIGHT"] = model_name

                # Force reload to pick up new env var
                from importlib import reload

                import app.services.llm_client as llm_module

                reload(llm_module)

                client = llm_module.get_llm_client(tier="light")

                # Simple test prompt
                response = client.generate(
                    prompt="What is 2+2? Answer in one word.",
                    temperature=0.0,
                    max_tokens=10,
                )

                if response and response.content:
                    logger.success(
                        f"✅ {model_name} works! Response: {response.content}"
                    )
                    return model_name  # Return working model
                else:
                    logger.warning(f"❌ {model_name} returned empty response")

            except Exception as e:
                logger.error(f"❌ {model_name} failed: {e}")

        logger.error("No working Gemini model found!")
        return None

    except Exception as e:
        logger.error(f"Fatal error testing Gemini: {e}")
        return None


def test_hyde_generation():
    """Test HyDE generation specifically"""
    logger.info("\n=== Testing HyDE Generation ===")

    working_model = test_gemini_connection()

    if not working_model:
        logger.error("Cannot test HyDE - no working model")
        return

    # Set the working model
    os.environ["GEMINI_MODEL_LIGHT"] = working_model

    try:
        from app.rag.query_transform import QueryTransformer

        transformer = QueryTransformer()
        query = "What is the maximum temperature of steam turbine?"

        logger.info(f"Testing HyDE for query: {query}")

        from app.rag.query_transform import QueryIntent

        hyde_results = transformer.generate_hyde(query=query, intent=QueryIntent.ASK)

        if hyde_results:
            logger.success(f"✅ HyDE generated {len(hyde_results)} hypotheses:")
            for i, hyde in enumerate(hyde_results, 1):
                logger.info(f"  {i}. {hyde[:100]}...")
        else:
            logger.warning("❌ HyDE returned empty results")

    except Exception as e:
        logger.error(f"HyDE test failed: {e}")


def check_api_key():
    """Check if API key is properly configured"""
    logger.info("\n=== Checking API Key Configuration ===")

    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        logger.error("❌ GEMINI_API_KEY not found in environment!")
        return False

    if len(api_key) < 30:
        logger.warning("⚠️ API key seems too short")
        return False

    logger.success(f"✅ API key found: {api_key[:10]}...{api_key[-4:]}")
    return True


def main():
    """Run all API tests"""
    logger.info("Gemini API Test Suite")
    logger.info("=" * 50)

    # Check API key
    if not check_api_key():
        logger.error("Please set GEMINI_API_KEY environment variable")
        return

    # Test connection
    working_model = test_gemini_connection()

    if working_model:
        logger.success(f"\n✅ Recommended model: {working_model}")

        # Update .env file suggestion
        logger.info("\nUpdate your .env file with:")
        logger.info(f"GEMINI_MODEL_LIGHT={working_model}")
        logger.info(f"GEMINI_MODEL_STANDARD={working_model}")

        # Test HyDE
        test_hyde_generation()
    else:
        logger.error("\n❌ No working Gemini models found")
        logger.info("Possible issues:")
        logger.info("1. API key might be invalid")
        logger.info("2. Rate limits exceeded")
        logger.info("3. Models might be unavailable in your region")


if __name__ == "__main__":
    main()
