"""
Embedding Service - Re-exports enhanced embedding service with multi-provider support

This module provides backward compatibility while enabling Gemini and other providers.
"""

# Re-export enhanced embedding service that supports multiple providers
from app.services.embedding_enhanced import (
    EmbeddingService,
    UniversalEmbeddingService,
    get_embedding_service,
)

__all__ = ["EmbeddingService", "UniversalEmbeddingService", "get_embedding_service"]
