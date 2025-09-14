#!/usr/bin/env python3
"""
Quick test for Gemini 2.5 models (flash and pro)
Usage:
    $env:GEMINI_API_KEY="your_key_here"
    python tools/test_gemini_2_5.py
"""

import os
import sys

from google import genai
from google.genai import types

# Add app to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def test_gemini_model(model_name: str, test_prompt: str = "Hello, how are you?"):
    """Test a specific Gemini model"""
    print(f"\n{'='*50}")
    print(f"Testing {model_name}")
    print(f"{'='*50}")

    try:
        # Get API key from settings or environment
        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("❌ No GEMINI_API_KEY found in environment or settings")
            return False

        # Create client
        client = genai.Client(api_key=api_key)

        # Prepare content
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=test_prompt)],
            ),
        ]

        print(f"📝 Prompt: {test_prompt}")
        print(f"🤖 Response from {model_name}:")
        print("-" * 30)

        # Stream response
        response_text = ""
        for chunk in client.models.generate_content_stream(
            model=model_name,
            contents=contents,
        ):
            if chunk.text:
                print(chunk.text, end="", flush=True)
                response_text += chunk.text

        print("\n" + "-" * 30)
        print(f"✅ {model_name} working! Response length: {len(response_text)} chars")
        return True

    except Exception as e:
        print(f"❌ Error with {model_name}: {str(e)}")
        return False


def main():
    """Test both Gemini 2.5 models"""
    print("🧪 Gemini 2.5 Models Test")
    print(f"Environment: {settings.app_env}")
    print(f"LLM Provider: {settings.llm_provider}")

    # Test prompt
    test_prompt = (
        "Explain what RAG (Retrieval-Augmented Generation) is in one sentence."
    )

    # Test models
    models_to_test = [
        "gemini-2.5-flash",  # Light tier
        "gemini-2.5-pro",  # Heavy tier
    ]

    results = {}
    for model in models_to_test:
        results[model] = test_gemini_model(model, test_prompt)

    # Summary
    print(f"\n{'='*50}")
    print("📊 TEST SUMMARY")
    print(f"{'='*50}")

    passed = sum(results.values())
    total = len(results)

    for model, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{model}: {status}")

    print(f"\nResults: {passed}/{total} models working")

    if passed == total:
        print("🎉 All Gemini 2.5 models are working!")
        print("\n💡 You can now use:")
        print("   LLM_MODEL_LIGHT=gemini-2.5-flash")
        print("   LLM_MODEL_HEAVY=gemini-2.5-pro")
    else:
        print("⚠️  Some models failed. Check your API key and model availability.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
