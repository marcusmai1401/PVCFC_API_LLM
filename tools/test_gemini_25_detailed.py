#!/usr/bin/env python
"""
Test Gemini 2.5 with detailed error checking
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def test_with_new_sdk_detailed():
    """Test new SDK with detailed debugging"""
    print("=" * 80)
    print("TESTING GEMINI 2.5 WITH NEW SDK (DETAILED)")
    print("=" * 80)

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    model_name = "gemini-2.5-flash"

    print(f"\n1. Testing: {model_name}")
    print("-" * 40)

    try:
        # Create content
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="What is 2+2? Answer briefly.")],
            )
        ]

        # Generate
        print("   Generating content...")
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0),
        )

        print(f"   Response type: {type(response)}")
        print(f"   Response attributes: {dir(response)}")

        # Check different ways to get text
        if hasattr(response, "text"):
            print(f"   response.text: {response.text}")

        if hasattr(response, "parts"):
            print(f"   response.parts: {response.parts}")

        if hasattr(response, "candidates"):
            print(f"   response.candidates: {response.candidates}")
            if response.candidates:
                candidate = response.candidates[0]
                print(f"   First candidate: {candidate}")
                if hasattr(candidate, "content"):
                    print(f"   Candidate content: {candidate.content}")
                    if hasattr(candidate.content, "parts"):
                        print(f"   Content parts: {candidate.content.parts}")
                        if candidate.content.parts:
                            print(
                                f"   First part text: {candidate.content.parts[0].text}"
                            )

        # Check usage metadata
        if hasattr(response, "usage_metadata"):
            print(f"   Usage metadata: {response.usage_metadata}")

    except Exception as e:
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()


def test_llm_client():
    """Test our LLMClient wrapper"""
    print("\n" + "=" * 80)
    print("TESTING OUR LLMCLIENT")
    print("=" * 80)

    # Update .env first
    print("\n1. Updating .env to use Gemini 2.5...")
    os.environ["LLM_MODEL_LIGHT"] = "gemini-2.5-flash"
    os.environ["LLM_MODEL_HEAVY"] = "gemini-2.5-pro"

    from app.services.llm_client import GeminiClient

    api_key = os.environ.get("GEMINI_API_KEY")

    # Test 2.5 flash
    print("\n2. Testing Gemini 2.5 Flash via our client...")
    print("-" * 40)

    try:
        client = GeminiClient(api_key=api_key, model="gemini-2.5-flash")
        response = client.generate(
            prompt="What is 2+2? Answer in one word.", temperature=0
        )

        print(f"   Response type: {type(response)}")
        print(f"   Response content: {response.content}")
        print(f"   Response model: {response.model}")

    except Exception as e:
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()

    # Test 2.5 pro
    print("\n3. Testing Gemini 2.5 Pro via our client...")
    print("-" * 40)

    try:
        client = GeminiClient(api_key=api_key, model="gemini-2.5-pro")
        response = client.generate(
            prompt="What is the capital of France? One word.", temperature=0
        )

        print(f"   Response content: {response.content}")

    except Exception as e:
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()


def main():
    print("🔍 GEMINI 2.5 DETAILED TEST")
    print("=" * 80)

    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ No GEMINI_API_KEY found")
        return
    print(f"✅ API Key found: {api_key[:20]}...")

    # Test new SDK in detail
    test_with_new_sdk_detailed()

    # Test our client
    test_llm_client()

    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print(
        """
    Check the output above to see:
    1. How the new SDK returns responses
    2. Whether response.text exists
    3. How to properly extract text from response
    """
    )


if __name__ == "__main__":
    main()
