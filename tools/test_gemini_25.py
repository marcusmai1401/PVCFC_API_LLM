#!/usr/bin/env python
"""
Test Gemini 2.5 models thoroughly
"""
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from loguru import logger


def test_model_direct(
    model_name: str, test_prompt: str = "What is 2+2? Answer in one word."
):
    """Test model directly using google.generativeai"""

    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print("=" * 60)

    try:
        # Configure API
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("❌ No API key found")
            return False

        genai.configure(api_key=api_key)

        # Create model instance
        print(f"1. Creating model instance...")
        model = genai.GenerativeModel(model_name)
        print(f"   ✅ Model instance created")

        # Test generation
        print(f"2. Testing generation...")
        print(f"   Prompt: {test_prompt}")

        start_time = time.time()
        response = model.generate_content(test_prompt)
        elapsed = (time.time() - start_time) * 1000

        if response and response.text:
            print(f"   ✅ Response: {response.text.strip()}")
            print(f"   ⏱️ Time: {elapsed:.0f}ms")

            # Test token counting if available
            try:
                tokens = model.count_tokens(test_prompt)
                print(f"   📊 Input tokens: {tokens.total_tokens}")
            except:
                pass

            return True
        else:
            print(f"   ❌ Empty response")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")

        # Try to understand the error
        error_str = str(e)
        if "404" in error_str:
            print("   💡 Model not found - check exact model name")
        elif "429" in error_str:
            print("   💡 Rate limit - wait and retry")
        elif "403" in error_str:
            print("   💡 Permission denied - check API key permissions")
        elif "model" in error_str.lower():
            print("   💡 Model name issue - verify exact name from list")

        return False


def test_with_llm_client(model_name: str):
    """Test model through our LLM client wrapper"""

    print(f"\n{'='*60}")
    print(f"Testing via LLM Client: {model_name}")
    print("=" * 60)

    try:
        # Temporarily set the model in environment
        original_light = os.environ.get("LLM_MODEL_LIGHT", "")
        os.environ["LLM_MODEL_LIGHT"] = model_name

        # Import and test
        from app.services.llm_client import get_llm_client

        print("1. Creating LLM client...")
        client = get_llm_client(tier="light")
        print("   ✅ Client created")

        print("2. Testing generation...")
        response = client.generate(
            prompt="What is the capital of France? Answer in one word.",
            temperature=0.0,
            max_tokens=10,
        )

        if response and response.content:
            print(f"   ✅ Response: {response.content.strip()}")
            return True
        else:
            print(f"   ❌ Empty response")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        # Restore original
        if "original_light" in locals():
            os.environ["LLM_MODEL_LIGHT"] = original_light


def test_long_output(model_name: str):
    """Test long output capability of Gemini 2.5"""

    print(f"\n{'='*60}")
    print(f"Testing Long Output: {model_name}")
    print("=" * 60)

    try:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel(model_name)

        # Request a long output
        prompt = """Write a detailed technical explanation of how a steam turbine works.
        Include at least 10 paragraphs covering:
        1. Basic principles
        2. Components
        3. Thermodynamics
        4. Efficiency factors
        5. Applications

        Make it at least 1000 words."""

        print("Requesting long output...")
        response = model.generate_content(prompt)

        if response and response.text:
            word_count = len(response.text.split())
            char_count = len(response.text)

            print(f"   ✅ Response generated")
            print(f"   📊 Words: {word_count:,}")
            print(f"   📊 Characters: {char_count:,}")
            print(f"   📝 First 100 chars: {response.text[:100]}...")

            if word_count > 500:
                print(f"   🎉 Long output capability confirmed!")

            return True
        else:
            print(f"   ❌ Empty response")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def compare_models():
    """Compare different Gemini models"""

    print("\n" + "=" * 80)
    print("GEMINI MODEL COMPARISON")
    print("=" * 80)

    models_to_test = [
        ("gemini-1.5-flash", "Current Light (1.5)"),
        ("gemini-2.5-flash", "New Light (2.5)"),
        ("gemini-1.5-pro", "Current Heavy (1.5)"),
        ("gemini-2.5-pro", "New Heavy (2.5)"),
        ("gemini-2.0-flash-exp", "Experimental 2.0"),
    ]

    results = []
    prompt = "Explain quantum computing in 50 words"

    for model_name, description in models_to_test:
        print(f"\n📋 {description}: {model_name}")
        print("-" * 40)

        try:
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
            model = genai.GenerativeModel(model_name)

            # Measure performance
            start = time.time()
            response = model.generate_content(prompt)
            elapsed = (time.time() - start) * 1000

            if response and response.text:
                word_count = len(response.text.split())
                results.append(
                    {
                        "model": model_name,
                        "status": "✅",
                        "time_ms": elapsed,
                        "words": word_count,
                    }
                )
                print(f"✅ Success - {elapsed:.0f}ms, {word_count} words")
                print(f"   Response: {response.text[:100]}...")
            else:
                results.append(
                    {"model": model_name, "status": "❌", "time_ms": 0, "words": 0}
                )
                print(f"❌ Failed - Empty response")

        except Exception as e:
            results.append(
                {"model": model_name, "status": "❌", "time_ms": 0, "words": 0}
            )
            print(f"❌ Error: {str(e)[:100]}")

    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Model':<25} {'Status':<10} {'Time (ms)':<12} {'Words':<10}")
    print("-" * 60)
    for r in results:
        print(
            f"{r['model']:<25} {r['status']:<10} {r['time_ms']:<12.0f} {r['words']:<10}"
        )


def main():
    """Main test function"""

    print("🚀 GEMINI 2.5 MODEL TESTING")
    print("=" * 80)

    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return

    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")

    # Test specific models
    print("\n" + "=" * 80)
    print("1. TESTING GEMINI 2.5 FLASH")
    print("=" * 80)

    success_25_flash = test_model_direct("gemini-2.5-flash")

    print("\n" + "=" * 80)
    print("2. TESTING GEMINI 2.5 PRO")
    print("=" * 80)

    success_25_pro = test_model_direct("gemini-2.5-pro")

    # If 2.5 models work, test long output
    if success_25_flash:
        print("\n" + "=" * 80)
        print("3. TESTING LONG OUTPUT CAPABILITY")
        print("=" * 80)
        test_long_output("gemini-2.5-flash")

    # Compare all models
    print("\n" + "=" * 80)
    print("4. COMPARING ALL MODELS")
    print("=" * 80)
    compare_models()

    # Final recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    if success_25_flash and success_25_pro:
        print("✅ Gemini 2.5 models are working!")
        print("\nUpdate your .env file with:")
        print("```")
        print("LLM_MODEL_LIGHT=gemini-2.5-flash")
        print("LLM_MODEL_HEAVY=gemini-2.5-pro")
        print("```")
    elif success_25_flash:
        print("⚠️ Only Gemini 2.5 Flash is working")
        print("\nSuggested .env:")
        print("```")
        print("LLM_MODEL_LIGHT=gemini-2.5-flash")
        print("LLM_MODEL_HEAVY=gemini-1.5-pro  # Keep 1.5 for heavy")
        print("```")
    else:
        print("❌ Gemini 2.5 models not working yet")
        print("\nKeep current .env:")
        print("```")
        print("LLM_MODEL_LIGHT=gemini-1.5-flash")
        print("LLM_MODEL_HEAVY=gemini-1.5-pro")
        print("```")
        print("\nPossible reasons:")
        print("1. Models might be region-restricted")
        print("2. API key might not have access to new models")
        print("3. Models might be gradually rolling out")


if __name__ == "__main__":
    main()
