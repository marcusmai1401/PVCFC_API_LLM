from typing import Literal, Optional

from app.core.config import settings
from app.core.llm_constants import is_valid_model

Tier = Literal["light", "heavy"]


def get_provider_for(tier: Tier) -> str:
    """Get the LLM provider for a specific tier

    Args:
        tier: The tier to get provider for (light or heavy)

    Returns:
        str: The provider name

    Raises:
        ValueError: If provider is not configured
    """
    if tier == "light":
        provider = settings.llm_light_provider or settings.llm_provider
    else:
        provider = settings.llm_provider

    if provider == "none" or provider is None:
        raise ValueError(
            f"No LLM provider configured for tier '{tier}'. "
            f"Please set LLM_PROVIDER in your .env file. "
            f"Options: openai, gemini"
        )

    return provider


def get_model_for(tier: Tier) -> Optional[str]:
    """Get the model name for a specific tier

    Args:
        tier: The tier to get model for (light or heavy)

    Returns:
        str: The model name

    Raises:
        ValueError: If model is not configured for the tier
    """
    model = settings.llm_model_light if tier == "light" else settings.llm_model_heavy

    if not model:
        model_var = "LLM_MODEL_LIGHT" if tier == "light" else "LLM_MODEL_HEAVY"
        raise ValueError(
            f"No model configured for tier '{tier}'. "
            f"Please set {model_var} in your .env file. "
            f"Example models: gpt-4o-mini, gemini-1.5-flash (light), "
            f"gpt-4o, gemini-1.5-pro (heavy)"
        )

    # Validate model is appropriate for provider
    try:
        provider = get_provider_for(tier)
        if not is_valid_model(provider, model, "chat"):
            # Don't fail hard, just warn since model lists might be outdated
            import logging

            logging.warning(
                f"Model '{model}' may not be valid for provider '{provider}'. "
                f"Please verify the model name is correct."
            )
    except Exception:
        pass  # Provider validation will handle its own errors

    return model


def get_api_key_for(provider: str) -> Optional[str]:
    """Get the API key for a specific provider

    Args:
        provider: The provider to get API key for

    Returns:
        str: The API key

    Raises:
        ValueError: If API key is not configured for the provider
    """
    api_key = None
    key_var = None

    if provider == "openai":
        api_key = settings.openai_api_key
        key_var = "OPENAI_API_KEY"
    elif provider == "gemini":
        api_key = settings.gemini_api_key
        key_var = "GEMINI_API_KEY"
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. " f"Supported providers: openai, gemini"
        )

    if not api_key:
        raise ValueError(
            f"API key not configured for provider '{provider}'. "
            f"Please set {key_var} in your .env file. "
            f"Get your key from: "
            f"{'https://platform.openai.com/api-keys' if provider == 'openai' else 'https://makersuite.google.com/app/apikey'}"
        )

    return api_key


def get_embedding_provider() -> str:
    """Get the embedding provider

    Returns:
        str: The embedding provider name

    Raises:
        ValueError: If embedding provider is not configured
    """
    provider = settings.embedding_llm or settings.embedding_provider

    if provider == "none" or provider is None:
        raise ValueError(
            "No embedding provider configured. "
            "Please set EMBEDDING_PROVIDER in your .env file. "
            "Options: openai, local"
        )

    return provider


def get_embedding_model() -> Optional[str]:
    """Get the embedding model name

    Returns:
        str: The embedding model name

    Raises:
        ValueError: If embedding model is not configured
    """
    model = settings.embedding_model

    if not model:
        provider = get_embedding_provider()
        examples = {
            "openai": "text-embedding-3-small, text-embedding-3-large",
            "local": "sentence-transformers/all-MiniLM-L6-v2, BAAI/bge-base-en-v1.5",
        }
        raise ValueError(
            f"No embedding model configured. "
            f"Please set EMBEDDING_MODEL in your .env file. "
            f"Example models for {provider}: {examples.get(provider, 'check documentation')}"
        )

    # Validate model is appropriate for provider
    try:
        provider = get_embedding_provider()
        if not is_valid_model(provider, model, "embedding"):
            # Don't fail hard, just warn since model lists might be outdated
            import logging

            logging.warning(
                f"Model '{model}' may not be valid for embedding provider '{provider}'. "
                f"Please verify the model name is correct."
            )
    except Exception:
        pass  # Provider validation will handle its own errors

    return model
