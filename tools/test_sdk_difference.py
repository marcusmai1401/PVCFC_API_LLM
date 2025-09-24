#!/usr/bin/env python
"""
Test the difference between google.generativeai and google.genai SDKs
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def test_old_sdk():
    """Test with google.generativeai (old SDK)"""
    print("=" * 80)
    print("TESTING OLD SDK: google.generativeai")
    print("=" * 80)

    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=api_key)

        # Test different model names
        models_to_test = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "models/gemini-2.5-flash",  # With prefix
        ]

        for model_name in models_to_test:
            print(f"\nTesting: {model_name}")
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Say 'OK' only")
                if response and response.text:
                    print(f"  ✅ SUCCESS: {response.text.strip()}")
                else:
                    print(f"  ❌ Empty response")
            except Exception as e:
                error_msg = str(e)[:100]
                print(f"  ❌ FAILED: {error_msg}")

    except ImportError:
        print("❌ google.generativeai not installed")


def test_new_sdk():
    """Test with google.genai (new SDK)"""
    print("\n" + "=" * 80)
    print("TESTING NEW SDK: google.genai")
    print("=" * 80)

    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)

        # Test different model name formats
        models_to_test = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "models/gemini-2.5-flash",  # With prefix
            "gemini-2.0-flash-exp",
        ]

        for model_name in models_to_test:
            print(f"\nTesting: {model_name}")
            try:
                contents = [
                    types.Content(
                        role="user", parts=[types.Part.from_text(text="Say 'OK' only")]
                    )
                ]

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(temperature=0),
                )

                if response and response.text:
                    print(f"  ✅ SUCCESS: {response.text.strip()}")
                else:
                    print(f"  ❌ Empty response")

            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg:
                    print(f"  ❌ MODEL NOT FOUND")
                elif "not found" in error_msg.lower():
                    print(f"  ❌ Model doesn't exist with this name")
                else:
                    print(f"  ❌ FAILED: {error_msg[:100]}")

    except ImportError as e:
        print(f"❌ google.genai not installed or import error: {e}")


def list_available_models():
    """List models available in new SDK"""
    print("\n" + "=" * 80)
    print("LISTING AVAILABLE MODELS (NEW SDK)")
    print("=" * 80)

    try:
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)

        # Try to list models
        print("\nAttempting to list models...")

        # Check if there's a list method
        if hasattr(client.models, "list"):
            models = client.models.list()
            for model in models:
                print(f"  - {model}")
        else:
            print("  No list method available")

        # Check client attributes
        print("\nClient.models attributes:")
        for attr in dir(client.models):
            if not attr.startswith("_"):
                print(f"  - {attr}")

    except Exception as e:
        print(f"Error: {e}")


def main():
    print("🔍 SDK COMPARISON TEST")
    print("=" * 80)

    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ No GEMINI_API_KEY found")
        return
    print(f"✅ API Key found: {api_key[:20]}...")

    # Test old SDK
    test_old_sdk()

    # Test new SDK
    test_new_sdk()

    # List available models
    list_available_models()

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print(
        """
    If gemini-2.5 works with old SDK but not new SDK:
    - The new SDK might need different model names
    - The new SDK might not support 2.5 yet
    - We should use old SDK for now
    """
    )


if __name__ == "__main__":
    main()
