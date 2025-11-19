"""
LLM Client Factory - Support multiple LLM providers with easy switching
Allows easy switching between OpenAI, Gemini, and other providers via .env configuration
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Literal, Optional, Union

from loguru import logger

from app.services.llm import Tier, get_api_key_for, get_model_for, get_provider_for


@dataclass
class LLMResponse:
    """Unified response format from any LLM provider"""

    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLMClient(ABC):
    """Base class for all LLM clients"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.provider = self.__class__.__name__.replace("Client", "").lower()

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """Generate a streaming response from the LLM"""
        pass


class GeminiClient(BaseLLMClient):
    """Google Gemini client implementation"""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self._client = None

    def _get_client(self):
        """Lazy load the Gemini client"""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "google-genai is required for Gemini support. "
                    "Install with: pip install google-genai"
                )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Gemini"""
        from google.genai import types

        client = self._get_client()

        # Build contents - only user message, system_prompt goes to system_instruction
        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        ]

        # Generate config with system_instruction if provided
        config_params = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        # Add system_instruction if provided
        if system_prompt:
            config_params["system_instruction"] = system_prompt

        config = types.GenerateContentConfig(**config_params)

        try:
            # Ensure model name has correct format
            model_name = (
                self.model
                if self.model.startswith("models/")
                else f"models/{self.model}"
            )

            response = client.models.generate_content(
                model=model_name, contents=contents, config=config
            )

            # Log response structure for debugging
            logger.info(f"Gemini response type: {type(response)}")
            if response and not hasattr(response, "text"):
                logger.warning(
                    f"Response has no 'text' attribute. Available attrs: {[a for a in dir(response) if not a.startswith('_')]}"
                )

            # Check finish_reason first to understand why generation stopped
            finish_reason = None
            if hasattr(response, "candidates") and response.candidates:
                try:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "finish_reason"):
                        finish_reason = str(candidate.finish_reason)
                        logger.debug(f"Gemini finish_reason: {finish_reason}")

                        # Log warning for problematic finish reasons
                        if "MAX_TOKENS" in finish_reason:
                            logger.warning(
                                f"Gemini hit MAX_TOKENS limit (max_tokens={max_tokens}). "
                                f"Response may be truncated. Consider increasing max_tokens."
                            )
                        elif "SAFETY" in finish_reason:
                            logger.warning(
                                f"Gemini blocked response due to safety: {finish_reason}"
                            )
                except (IndexError, AttributeError) as e:
                    logger.debug(f"Could not check finish_reason: {e}")

            # Extract text - handle multiple ways response might structure the text
            content_text = ""

            # First try the simple response.text attribute
            if hasattr(response, "text") and response.text:
                content_text = response.text
                logger.info(
                    f"Extracted text from response.text: {len(content_text)} chars"
                )
            # If response.text is empty/None, try to extract from candidates
            elif hasattr(response, "candidates") and response.candidates:
                try:
                    for candidate in response.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            if (
                                hasattr(candidate.content, "parts")
                                and candidate.content.parts
                            ):
                                for part in candidate.content.parts:
                                    if hasattr(part, "text"):
                                        # Extract even if text is None/empty, to handle partial responses
                                        part_text = (
                                            part.text if part.text is not None else ""
                                        )
                                        content_text += part_text
                        # Alternative structure
                        elif hasattr(candidate, "text"):
                            candidate_text = (
                                candidate.text if candidate.text is not None else ""
                            )
                            content_text += candidate_text
                except (TypeError, AttributeError) as e:
                    logger.warning(f"Could not iterate through candidates: {e}")

            # If still empty but MAX_TOKENS was hit, try harder to extract ANY text
            if not content_text and finish_reason and "MAX_TOKENS" in finish_reason:
                logger.warning(
                    "MAX_TOKENS hit but no text extracted - trying harder..."
                )
                try:
                    if hasattr(response, "candidates") and response.candidates:
                        candidate = response.candidates[0]
                        # Try to get raw content
                        if hasattr(candidate, "content"):
                            logger.debug(
                                f"Candidate content type: {type(candidate.content)}"
                            )
                            logger.debug(
                                f"Candidate content: {str(candidate.content)[:500]}"
                            )
                except Exception as e:
                    logger.debug(f"Could not extract debug info: {e}")

            # Log warning if still no content
            if not content_text:
                reason_msg = (
                    f" (finish_reason: {finish_reason})" if finish_reason else ""
                )
                logger.warning(
                    f"Gemini returned empty response for model {self.model}. "
                    f"Prompt length: {len(prompt)}{reason_msg}"
                )
                content_text = "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."

            # Safely extract usage metadata
            usage = None
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                try:
                    usage = {
                        "prompt_tokens": getattr(
                            response.usage_metadata, "prompt_token_count", 0
                        ),
                        "completion_tokens": getattr(
                            response.usage_metadata, "candidates_token_count", 0
                        ),
                        "total_tokens": getattr(
                            response.usage_metadata, "total_token_count", 0
                        ),
                    }
                except Exception as e:
                    logger.debug(f"Could not extract usage metadata: {e}")
                    usage = None

            return LLMResponse(
                content=content_text, model=self.model, provider="gemini", usage=usage
            )

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            # Return a fallback response instead of raising
            return LLMResponse(
                content=f"Error generating response: {str(e)}",
                model=self.model,
                provider="gemini",
                usage=None,
            )

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream response using Gemini"""
        from google.genai import types

        client = self._get_client()

        # Build contents
        contents = []
        if system_prompt:
            contents.append(
                types.Content(
                    role="model", parts=[types.Part.from_text(text=system_prompt)]
                )
            )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        )

        # Stream generate
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Ensure model name has correct format
        model_name = (
            self.model if self.model.startswith("models/") else f"models/{self.model}"
        )

        for chunk in client.models.generate_content_stream(
            model=model_name, contents=contents, config=config
        ):
            if chunk.text:
                yield chunk.text


class OpenAIClient(BaseLLMClient):
    """OpenAI client implementation"""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self._client = None

    def _get_client(self):
        """Lazy load the OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "openai is required for OpenAI support. "
                    "Install with: pip install openai"
                )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using OpenAI"""
        client = self._get_client()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Generate
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="openai",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            if response.usage
            else None,
        )

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """Stream response using OpenAI"""
        client = self._get_client()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Stream generate
        stream = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class LLMClientFactory:
    """Factory for creating LLM clients based on configuration"""

    # Registry of supported providers
    _providers = {
        "gemini": GeminiClient,
        "openai": OpenAIClient,
    }

    @classmethod
    def register_provider(cls, name: str, client_class: type[BaseLLMClient]):
        """Register a new LLM provider"""
        cls._providers[name.lower()] = client_class

    @classmethod
    def create_client(
        cls,
        tier: Tier = "light",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMClient:
        """
        Create an LLM client based on tier or explicit configuration

        Args:
            tier: Use configuration for "light" or "heavy" tier
            provider: Override provider (if None, uses config)
            model: Override model (if None, uses config)
            api_key: Override API key (if None, uses config)

        Returns:
            LLM client instance

        Examples:
            # Use default light tier from config
            client = LLMClientFactory.create_client(tier="light")

            # Use heavy tier from config
            client = LLMClientFactory.create_client(tier="heavy")

            # Override with specific provider/model
            client = LLMClientFactory.create_client(
                provider="openai",
                model="gpt-4o",
                api_key="sk-..."
            )
        """
        # Get configuration
        if provider is None:
            provider = get_provider_for(tier)
        if model is None:
            model = get_model_for(tier)
        if api_key is None:
            api_key = get_api_key_for(provider)

        # Validate provider
        provider_lower = provider.lower()
        if provider_lower not in cls._providers:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported: {list(cls._providers.keys())}"
            )

        # Create client
        client_class = cls._providers[provider_lower]
        logger.info(f"Creating {provider} client with model {model}")

        return client_class(api_key=api_key, model=model)

    @classmethod
    def create_embedding_client(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Create an embedding client

        Supports local (sentence-transformers) and Gemini embeddings.
        Can be extended to support OpenAI embeddings.
        """
        from app.services.embedding import EmbeddingService

        if provider is None:
            from app.services.llm import get_embedding_provider

            provider = get_embedding_provider()

        if provider in ("local", "gemini"):
            # EmbeddingService now supports both local and gemini
            return EmbeddingService(provider=provider, model_name=model)
        elif provider == "openai":
            # TODO: Implement OpenAI embedding client
            raise NotImplementedError("OpenAI embeddings not yet implemented")
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")


# Convenience functions
def get_llm_client(tier: Tier = "light") -> BaseLLMClient:
    """Get an LLM client for the specified tier using configuration"""
    return LLMClientFactory.create_client(tier=tier)


def get_embedding_client():
    """Get an embedding client using configuration"""
    return LLMClientFactory.create_embedding_client()


def create_llm_client(tier: Tier = "light") -> BaseLLMClient:
    """Create an LLM client for the specified tier

    This is an alias for get_llm_client() for backward compatibility.
    """
    return get_llm_client(tier)
