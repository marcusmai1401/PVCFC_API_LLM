#!/usr/bin/env python
"""
List all available Gemini models from Google AI
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from loguru import logger
from tabulate import tabulate


def list_all_models():
    """List all available Gemini models"""

    # Configure API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment")
        return None

    genai.configure(api_key=api_key)

    # Get all models
    models = genai.list_models()

    return models


def display_models_table(models):
    """Display models in a nice table format"""

    table_data = []

    for model in models:
        # Extract key information
        name = model.name
        display_name = getattr(model, "display_name", "N/A")
        description = (
            getattr(model, "description", "N/A")[:50] + "..."
            if getattr(model, "description", None)
            else "N/A"
        )

        # Check supported methods
        supported_methods = []
        if hasattr(model, "supported_generation_methods"):
            supported_methods = model.supported_generation_methods

        # Get model capabilities
        capabilities = []
        if "generateContent" in supported_methods:
            capabilities.append("Text")
        if "generateAnswer" in supported_methods:
            capabilities.append("Q&A")
        if "embedContent" in supported_methods:
            capabilities.append("Embed")
        if "countTokens" in supported_methods:
            capabilities.append("Token")

        table_data.append(
            [
                name.replace("models/", ""),
                display_name,
                ", ".join(capabilities),
                description,
            ]
        )

    # Sort by name
    table_data.sort(key=lambda x: x[0])

    # Print table
    headers = ["Model Name", "Display Name", "Capabilities", "Description"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))


def display_detailed_info(models):
    """Display detailed information about each model"""

    print("\n" + "=" * 80)
    print("DETAILED MODEL INFORMATION")
    print("=" * 80)

    for model in models:
        print(f"\n### {model.name}")
        print("-" * 40)

        # Basic info
        print(f"Display Name: {getattr(model, 'display_name', 'N/A')}")
        print(f"Description: {getattr(model, 'description', 'N/A')}")

        # Supported methods
        if hasattr(model, "supported_generation_methods"):
            print(f"Supported Methods: {', '.join(model.supported_generation_methods)}")

        # Input/Output tokens
        if hasattr(model, "input_token_limit"):
            print(f"Input Token Limit: {model.input_token_limit:,}")
        if hasattr(model, "output_token_limit"):
            print(f"Output Token Limit: {model.output_token_limit:,}")

        # Temperature range
        if hasattr(model, "temperature"):
            print(f"Temperature Range: {model.temperature}")
        if hasattr(model, "top_p"):
            print(f"Top-P Range: {model.top_p}")
        if hasattr(model, "top_k"):
            print(f"Top-K Range: {model.top_k}")


def filter_text_generation_models(models):
    """Filter models that support text generation"""

    text_models = []

    for model in models:
        if hasattr(model, "supported_generation_methods"):
            if "generateContent" in model.supported_generation_methods:
                text_models.append(model)

    return text_models


def filter_embedding_models(models):
    """Filter models that support embeddings"""

    embedding_models = []

    for model in models:
        if hasattr(model, "supported_generation_methods"):
            if "embedContent" in model.supported_generation_methods:
                embedding_models.append(model)

    return embedding_models


def save_models_to_json(models, filename="gemini_models.json"):
    """Save model information to JSON file"""

    models_data = []

    for model in models:
        model_info = {
            "name": model.name,
            "display_name": getattr(model, "display_name", None),
            "description": getattr(model, "description", None),
            "supported_methods": getattr(model, "supported_generation_methods", []),
            "input_token_limit": getattr(model, "input_token_limit", None),
            "output_token_limit": getattr(model, "output_token_limit", None),
        }
        models_data.append(model_info)

    # Save to file
    output_path = Path("artifacts") / filename
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(models_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved model information to {output_path}")


def recommend_models_for_rag():
    """Recommend best models for RAG pipeline"""

    print("\n" + "=" * 80)
    print("RECOMMENDED MODELS FOR RAG PIPELINE")
    print("=" * 80)

    recommendations = {
        "Light Tier (Fast & Cheap)": [
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-2.0-flash-exp",
        ],
        "Standard Tier (Balanced)": ["gemini-1.5-pro", "gemini-1.5-pro-002"],
        "Heavy Tier (High Quality)": ["gemini-1.5-pro-latest", "gemini-exp-1206"],
        "Embeddings": ["text-embedding-004", "embedding-001"],
    }

    for category, model_list in recommendations.items():
        print(f"\n### {category}")
        for model in model_list:
            print(f"  - {model}")

    print("\n" + "=" * 80)
    print("UPDATE YOUR .env FILE:")
    print("=" * 80)
    print(
        """
# Recommended settings for production:
LLM_MODEL_LIGHT=gemini-1.5-flash
LLM_MODEL_HEAVY=gemini-1.5-pro
EMBEDDING_MODEL=text-embedding-004

# For experimental features:
# LLM_MODEL_LIGHT=gemini-2.0-flash-exp
# LLM_MODEL_HEAVY=gemini-exp-1206
"""
    )


def test_model_availability(model_name: str):
    """Test if a specific model is available and working"""

    logger.info(f"Testing model: {model_name}")

    try:
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel(model_name)

        # Test with simple prompt
        response = model.generate_content("Say 'Hello'")

        if response and response.text:
            logger.success(f"✅ {model_name} is working! Response: {response.text[:50]}")
            return True
        else:
            logger.warning(f"⚠️ {model_name} returned empty response")
            return False

    except Exception as e:
        logger.error(f"❌ {model_name} failed: {e}")
        return False


def main():
    """Main function"""

    logger.info("Gemini Models Explorer")
    logger.info("=" * 80)

    # List all models
    logger.info("Fetching available models...")
    models = list_all_models()

    if not models:
        logger.error("Failed to fetch models")
        return

    logger.success(f"Found {len(list(models))} models")

    # Convert to list for multiple iterations
    models_list = list(models)

    # Display in table format
    print("\n📊 AVAILABLE GEMINI MODELS:")
    display_models_table(models_list)

    # Filter by type
    text_models = filter_text_generation_models(models_list)
    embedding_models = filter_embedding_models(models_list)

    print(f"\n📝 Text Generation Models: {len(text_models)}")
    for model in text_models[:5]:  # Show first 5
        print(f"  - {model.name.replace('models/', '')}")

    print(f"\n🔤 Embedding Models: {len(embedding_models)}")
    for model in embedding_models:
        print(f"  - {model.name.replace('models/', '')}")

    # Show detailed info for some models
    print("\n📋 Detailed info for recommended models:")
    important_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]

    for model in models_list:
        model_name = model.name.replace("models/", "")
        if any(imp in model_name for imp in important_models):
            print(f"\n### {model_name}")
            print(f"  Input limit: {getattr(model, 'input_token_limit', 'N/A'):,}")
            print(f"  Output limit: {getattr(model, 'output_token_limit', 'N/A'):,}")

    # Save to JSON
    save_models_to_json(models_list)

    # Show recommendations
    recommend_models_for_rag()

    # Test recommended models
    print("\n🧪 Testing recommended models...")
    test_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]

    for model_name in test_models:
        test_model_availability(model_name)

    print("\n" + "=" * 80)
    print("✅ Model exploration complete!")


if __name__ == "__main__":
    main()
