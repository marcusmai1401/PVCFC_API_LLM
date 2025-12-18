"""
LLM Constants and Model Definitions
Contains lists of supported models for each provider
"""

# Vision model constant (Gemini 3 Pro Preview - best for multimodal)
VISION_MODEL = "models/gemini-3-pro-preview"

# OpenAI Models
OPENAI_CHAT_MODELS = [
    # GPT-4o series (latest multimodal)
    "gpt-4o",
    "gpt-4o-2024-11-20",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-05-13",
    "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18",
    # GPT-4 Turbo series
    "gpt-4-turbo",
    "gpt-4-turbo-2024-04-09",
    "gpt-4-turbo-preview",
    "gpt-4-0125-preview",
    "gpt-4-1106-preview",
    # GPT-4 original
    "gpt-4",
    "gpt-4-0613",
    "gpt-4-32k",
    "gpt-4-32k-0613",
    # GPT-3.5 series
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-16k",
    # O1 series (reasoning models)
    "o1-preview",
    "o1-preview-2024-09-12",
    "o1-mini",
    "o1-mini-2024-09-12",
]

OPENAI_EMBEDDING_MODELS = [
    # Text Embedding 3 series (latest)
    "text-embedding-3-small",
    "text-embedding-3-large",
    # Ada v2 (legacy but still popular)
    "text-embedding-ada-002",
]

# Google Gemini Models
GEMINI_CHAT_MODELS = [
    # Gemini 3 series (preview - cutting edge!)
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    # Gemini 2.5 series (stable, 65K output tokens)
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    # Gemini 2.0 Flash (with thinking/reasoning)
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-thinking-exp",
    "gemini-2.0-flash-thinking-exp-1219",
    # Gemini 1.5 Pro series (stable)
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-1.5-pro-002",
    "gemini-1.5-pro-001",
    "gemini-1.5-pro-exp-0827",
    # Gemini 1.5 Flash (fast & cheap)
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash-exp-0827",
    # Gemini 1.0 Pro (legacy)
    "gemini-1.0-pro",
    "gemini-1.0-pro-latest",
    "gemini-1.0-pro-001",
    "gemini-1.0-pro-vision-latest",
    # Gemini Pro (alias)
    "gemini-pro",
    "gemini-pro-vision",
]

GEMINI_EMBEDDING_MODELS = [
    # Text embedding models
    "text-embedding-004",
    "embedding-001",
    # Multilingual embedding
    "text-multilingual-embedding-002",
]

# Local/Open Source Embedding Models (for sentence-transformers)
LOCAL_EMBEDDING_MODELS = [
    # Small & Fast models
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-MiniLM-L12-v2",
    # Multilingual models
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    # High quality English models
    "sentence-transformers/all-mpnet-base-v2",
    "sentence-transformers/all-distilroberta-v1",
    # Specialized models
    "sentence-transformers/msmarco-distilbert-base-v4",  # For search/retrieval
    "sentence-transformers/multi-qa-mpnet-base-dot-v1",  # For Q&A
    # BGE models (popular in production)
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-base-en-v1.5",
    "BAAI/bge-large-en-v1.5",
    # E5 models (Microsoft)
    "intfloat/e5-small-v2",
    "intfloat/e5-base-v2",
    "intfloat/e5-large-v2",
]

# Model recommendations by use case
RECOMMENDED_MODELS = {
    "development": {
        "light": {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-3-flash-preview",
        },
        "heavy": {
            "openai": "gpt-4o",
            "gemini": "gemini-3-pro-preview",
        },
        "embedding": {
            "openai": "text-embedding-3-small",
            "local": "sentence-transformers/all-MiniLM-L6-v2",
        },
    },
    "production": {
        "light": {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-3-flash-preview",
        },
        "heavy": {
            "openai": "gpt-4o",
            "gemini": "gemini-3-pro-preview",
        },
        "embedding": {
            "openai": "text-embedding-3-large",
            "local": "BAAI/bge-large-en-v1.5",
        },
    },
    "cost_optimized": {
        "light": {
            "openai": "gpt-3.5-turbo",
            "gemini": "gemini-3-flash-preview",
        },
        "heavy": {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-3-pro-preview",
        },
        "embedding": {
            "openai": "text-embedding-3-small",
            "local": "sentence-transformers/all-MiniLM-L6-v2",
        },
    },
    "quality_optimized": {
        "light": {
            "openai": "gpt-4o",
            "gemini": "gemini-3-flash-preview",
        },
        "heavy": {
            "openai": "o1-preview",
            "gemini": "gemini-3-pro-preview",
        },
        "embedding": {
            "openai": "text-embedding-3-large",
            "local": "BAAI/bge-large-en-v1.5",
        },
    },
}


def is_valid_model(provider: str, model: str, model_type: str = "chat") -> bool:
    """
    Check if a model name is valid for a given provider

    Args:
        provider: The LLM provider (openai, gemini, local)
        model: The model name to check
        model_type: Type of model - "chat" or "embedding"

    Returns:
        bool: True if model is valid for the provider
    """
    if provider == "openai":
        if model_type == "chat":
            return model in OPENAI_CHAT_MODELS
        elif model_type == "embedding":
            return model in OPENAI_EMBEDDING_MODELS
    elif provider == "gemini":
        if model_type == "chat":
            return model in GEMINI_CHAT_MODELS
        elif model_type == "embedding":
            return model in GEMINI_EMBEDDING_MODELS
    elif provider == "local" and model_type == "embedding":
        return model in LOCAL_EMBEDDING_MODELS

    return False


def get_recommended_model(
    use_case: str = "development", tier: str = "light", provider: str = "openai"
) -> str:
    """
    Get recommended model for a specific use case

    Args:
        use_case: One of development, production, cost_optimized, quality_optimized
        tier: One of light, heavy, embedding
        provider: The LLM provider

    Returns:
        str: Recommended model name or None if not found
    """
    try:
        return RECOMMENDED_MODELS[use_case][tier][provider]
    except KeyError:
        return None
