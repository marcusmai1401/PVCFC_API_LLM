#!/usr/bin/env python
"""
Simple script to list all available Gemini models
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai


def main():
    # Configure API
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found")
        return

    genai.configure(api_key=api_key)

    print("=" * 80)
    print("AVAILABLE GEMINI MODELS")
    print("=" * 80)

    # List all models
    models = genai.list_models()

    # Group models by type
    text_models = []
    embedding_models = []
    other_models = []

    for model in models:
        model_name = model.name

        # Get supported methods - handle different attribute names
        supported = []
        if hasattr(model, "supported_generation_methods"):
            supported = model.supported_generation_methods

        # Categorize
        if "generateContent" in supported:
            text_models.append(model)
        elif "embedContent" in supported:
            embedding_models.append(model)
        else:
            other_models.append(model)

    # Display text generation models
    print("\n📝 TEXT GENERATION MODELS:")
    print("-" * 40)
    for model in text_models:
        name = model.name.replace("models/", "")
        print(f"\n✅ {name}")

        # Show details if available
        if hasattr(model, "input_token_limit"):
            print(f"   Input Tokens: {model.input_token_limit:,}")
        if hasattr(model, "output_token_limit"):
            print(f"   Output Tokens: {model.output_token_limit:,}")
        if hasattr(model, "description"):
            desc = model.description[:100] if model.description else "N/A"
            print(f"   Description: {desc}")

    # Display embedding models
    print("\n\n🔤 EMBEDDING MODELS:")
    print("-" * 40)
    for model in embedding_models:
        name = model.name.replace("models/", "")
        print(f"\n✅ {name}")

        if hasattr(model, "description"):
            desc = model.description[:100] if model.description else "N/A"
            print(f"   Description: {desc}")

    # Display other models
    if other_models:
        print("\n\n🔧 OTHER MODELS:")
        print("-" * 40)
        for model in other_models:
            name = model.name.replace("models/", "")
            methods = getattr(model, "supported_generation_methods", [])
            print(f"\n✅ {name}")
            print(f"   Methods: {', '.join(methods)}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Models: {len(list(genai.list_models()))}")
    print(f"Text Generation: {len(text_models)}")
    print(f"Embedding: {len(embedding_models)}")
    print(f"Other: {len(other_models)}")

    # Recommendations for RAG
    print("\n" + "=" * 80)
    print("RECOMMENDED FOR YOUR RAG PIPELINE")
    print("=" * 80)

    print("\n🚀 FAST (Light Tier):")
    recommended_light = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash-exp",
    ]
    for model_name in recommended_light:
        if any(model_name in m.name for m in text_models):
            print(f"  ✅ {model_name} - Available")
        else:
            print(f"  ❌ {model_name} - Not found")

    print("\n💎 QUALITY (Heavy Tier):")
    recommended_heavy = ["gemini-1.5-pro", "gemini-1.5-pro-latest", "gemini-exp-1206"]
    for model_name in recommended_heavy:
        if any(model_name in m.name for m in text_models):
            print(f"  ✅ {model_name} - Available")
        else:
            print(f"  ❌ {model_name} - Not found")

    print("\n🔤 EMBEDDINGS:")
    recommended_embed = [
        "text-embedding-004",
        "embedding-001",
        "text-embedding-preview-0409",
    ]
    for model_name in recommended_embed:
        if any(model_name in m.name for m in embedding_models):
            print(f"  ✅ {model_name} - Available")
        else:
            print(f"  ❌ {model_name} - Not found")

    # Test the models we're currently using
    print("\n" + "=" * 80)
    print("TESTING CURRENT CONFIGURATION")
    print("=" * 80)

    current_light = os.environ.get("LLM_MODEL_LIGHT", "gemini-1.5-flash")
    current_heavy = os.environ.get("LLM_MODEL_HEAVY", "gemini-1.5-pro")

    print(f"\nCurrent Light Model: {current_light}")
    try:
        model = genai.GenerativeModel(current_light)
        response = model.generate_content("Say OK")
        if response.text:
            print(f"  ✅ Working - Response: {response.text.strip()}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    print(f"\nCurrent Heavy Model: {current_heavy}")
    try:
        model = genai.GenerativeModel(current_heavy)
        response = model.generate_content("Say OK")
        if response.text:
            print(f"  ✅ Working - Response: {response.text.strip()}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
