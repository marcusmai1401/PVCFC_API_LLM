"""
Enhanced Embedding Service supporting multiple providers
Supports local models (sentence-transformers) and Gemini embeddings
"""
from __future__ import annotations

import os
from typing import List, Optional, Union

import numpy as np
from loguru import logger

from app.core.config import settings


class UniversalEmbeddingService:
    """Universal embedding service supporting multiple providers."""

    def __init__(
        self, provider: Optional[str] = None, model_name: Optional[str] = None
    ):
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider (gemini, local, openai)
            model_name: Model name to use
        """
        self.provider = provider or settings.embedding_provider or "local"
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._gemini_model = None

        logger.info(
            f"Initializing embedding service: provider={self.provider}, model={self.model_name}"
        )

    def _ensure_model(self):
        """Ensure the appropriate model is loaded."""

        if self.provider == "gemini":
            self._ensure_gemini_model()
        elif self.provider == "local":
            self._ensure_local_model()
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def _ensure_gemini_model(self):
        """Initialize Gemini embedding model."""
        if self._gemini_model is None:
            try:
                import google.generativeai as genai

                from app.core.config import settings

                # Configure API key from settings (which reads from .env)
                api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "GEMINI_API_KEY not found in settings or environment"
                    )

                genai.configure(api_key=api_key)

                # Set model name - text-embedding-004 is the latest
                if self.model_name == "text-embedding-004":
                    self._gemini_model = "models/text-embedding-004"
                elif self.model_name == "embedding-001":
                    self._gemini_model = "models/embedding-001"
                else:
                    # Default to text-embedding-004
                    self._gemini_model = "models/text-embedding-004"

                logger.info(f"Initialized Gemini embedding model: {self._gemini_model}")

            except Exception as e:
                logger.error(f"Failed to initialize Gemini embeddings: {e}")
                raise

    def _ensure_local_model(self):
        """Initialize local sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as exc:
                raise RuntimeError(
                    "sentence-transformers is required for local embeddings.\n"
                    "Install with: pip install sentence-transformers"
                ) from exc

            logger.info(f"Loading sentence-transformers model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        """
        Embed a list of texts and return a 2D numpy array.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            2D numpy array of embeddings (num_texts, dim)
        """
        self._ensure_model()

        if self.provider == "gemini":
            return self._embed_texts_gemini(texts)
        elif self.provider == "local":
            return self._embed_texts_local(texts, batch_size)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _embed_texts_gemini(self, texts: List[str]) -> np.ndarray:
        """Embed texts using Gemini API."""
        try:
            import google.generativeai as genai

            embeddings = []

            # Process texts individually due to size limits
            # Truncate very long texts if needed
            MAX_TEXT_LENGTH = 10000  # Gemini limit is about 20k chars

            for i, text in enumerate(texts):
                # Truncate if too long
                if len(text) > MAX_TEXT_LENGTH:
                    logger.warning(
                        f"Text {i} truncated from {len(text)} to {MAX_TEXT_LENGTH} chars"
                    )
                    text = text[:MAX_TEXT_LENGTH]

                try:
                    # Generate embedding
                    result = genai.embed_content(
                        model=self._gemini_model,
                        content=text,
                        task_type="retrieval_document",  # or "retrieval_query" for queries
                        title=None,  # Optional title for better context
                    )

                    # Extract embedding vector
                    embedding = result["embedding"]
                    embeddings.append(embedding)

                except Exception as e:
                    logger.error(f"Failed to embed text {i}: {e}")
                    # Use zero vector as fallback
                    dim = 768 if "004" in self._gemini_model else 768
                    embeddings.append([0.0] * dim)

            # Convert to numpy array
            embeddings_array = np.array(embeddings, dtype=np.float32)

            # Normalize embeddings
            norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
            embeddings_array = embeddings_array / (norms + 1e-8)

            return embeddings_array

        except Exception as e:
            logger.error(f"Gemini embedding failed: {e}")
            raise

    def _embed_texts_local(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Embed texts using local sentence-transformers model."""
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32, copy=False)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Embed a single text.

        Args:
            text: Text to embed

        Returns:
            1D numpy array of embedding
        """
        return self.embed_texts([text])[0]

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a query text (optimized for search).

        Args:
            query: Query text

        Returns:
            1D numpy array of embedding
        """
        self._ensure_model()

        # Skip embedding for empty or non-informative queries (e.g., only punctuation)
        if (
            not isinstance(query, str)
            or not query.strip()
            or not any(ch.isalnum() for ch in query)
        ):
            logger.warning("Embedding skipped for empty/non-informative query")
            return np.zeros((self.get_embedding_dimension(),), dtype=np.float32)

        if self.provider == "gemini":
            try:
                import google.generativeai as genai

                # Use retrieval_query task type for queries
                result = genai.embed_content(
                    model=self._gemini_model,
                    content=query,
                    task_type="retrieval_query",  # Optimized for search queries
                )

                embedding = np.array(result["embedding"], dtype=np.float32)

                # Normalize
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                return embedding

            except Exception as e:
                logger.error(f"Gemini query embedding failed: {e}")
                raise
        else:
            # For local models, same as regular embedding
            return self.embed_text(query)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        self._ensure_model()

        if self.provider == "gemini":
            # Gemini text-embedding-004 has 768 dimensions
            if "004" in self.model_name:
                return 768
            else:
                return 768  # Default for Gemini embeddings
        elif self.provider == "local":
            # Get dimension from model
            if hasattr(self._model, "get_sentence_embedding_dimension"):
                return self._model.get_sentence_embedding_dimension()
            else:
                # Generate a test embedding to get dimension
                test_embedding = self.embed_text("test")
                return len(test_embedding)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")


# Compatibility wrapper
class EmbeddingService(UniversalEmbeddingService):
    """Backward compatible embedding service."""

    pass


# Factory function
def get_embedding_service(provider: Optional[str] = None) -> UniversalEmbeddingService:
    """
    Get embedding service instance.

    Args:
        provider: Override provider (gemini, local, openai)

    Returns:
        Configured embedding service
    """
    from app.core.config import settings

    # Use settings which properly reads from .env
    provider = provider or settings.embedding_provider_effective()
    model = settings.embedding_model or "BAAI/bge-small-en-v1.5"

    return UniversalEmbeddingService(provider=provider, model_name=model)
