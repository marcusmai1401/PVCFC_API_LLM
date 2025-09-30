"""
Enhanced Embedding Service supporting multiple providers
Supports local models (sentence-transformers) and Gemini embeddings
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from loguru import logger

from app.core.config import settings

# Model alias mapping for Gemini
MODEL_ALIASES = {
    "gemini-embedding-001": "models/embedding-001",
    "embedding-001": "models/embedding-001",
    "text-embedding-004": "models/text-embedding-004",
    "text-multilingual-embedding-002": "models/text-multilingual-embedding-002",
}


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

        # Read embedding configuration from environment
        self.output_dim = int(os.getenv("EMBED_OUTPUT_DIM", "768"))
        self.batch_size = int(os.getenv("EMBED_BATCH_SIZE", "256"))
        self.concurrency = int(os.getenv("EMBED_CONCURRENCY", "8"))
        self.tpm_cap = int(os.getenv("EMBED_TPM_CAP", "1000000"))
        self.rpm_cap = int(os.getenv("EMBED_RPM_CAP", "3000"))
        self.max_tokens_per_req = int(os.getenv("EMBED_MAX_TOKENS_PER_REQ", "20000"))
        self.embed_task_doc = os.getenv("EMBED_TASK", "RETRIEVAL_DOCUMENT")
        self.embed_task_query = "RETRIEVAL_QUERY"

        # Metrics tracking
        self.metrics = {
            "cache_hits": 0,
            "api_calls": 0,
            "retries": 0,
            "rate_limit_events": 0,
            "quarantine_count": 0,
        }

        # Initialize cache and quarantine paths
        self.cache_dir = Path("artifacts/ingestion/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_db_path = self.cache_dir / "embeddings.sqlite"
        self.quarantine_path = Path("artifacts/ingestion/quarantine_embedding.jsonl")
        self.quarantine_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize cache database
        self._init_cache_db()

        logger.info(
            f"Initializing embedding service: provider={self.provider}, "
            f"model={self.model_name}, output_dim={self.output_dim}, "
            f"batch_size={self.batch_size}, concurrency={self.concurrency}"
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

                # Resolve model alias
                self._gemini_model = MODEL_ALIASES.get(
                    self.model_name,
                    f"models/{self.model_name}"
                    if not self.model_name.startswith("models/")
                    else self.model_name,
                )

                logger.info(
                    f"Initialized Gemini embedding model: {self._gemini_model} "
                    f"(resolved from {self.model_name}), output_dim={self.output_dim}"
                )

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

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text."""
        # Rough estimate: 1 token ≈ 4 characters for English/technical text
        return math.ceil(len(text) / 4)

    def _build_micro_batches(self, texts: List[str]) -> List[List[str]]:
        """Build micro-batches respecting batch size and token limits."""
        micro_batches = []
        current_batch = []
        current_tokens = 0

        for text in texts:
            text_tokens = self._estimate_tokens(text)

            # Check if adding this text would exceed limits
            if current_batch and (
                len(current_batch) >= self.batch_size
                or current_tokens + text_tokens > self.max_tokens_per_req
            ):
                # Save current batch and start new one
                micro_batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(text)
            current_tokens += text_tokens

        # Add remaining batch
        if current_batch:
            micro_batches.append(current_batch)

        logger.debug(
            f"Built {len(micro_batches)} micro-batches from {len(texts)} texts "
            f"(batch_size={self.batch_size}, max_tokens={self.max_tokens_per_req})"
        )

        return micro_batches

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        key_str = f"{self._gemini_model}:{self.output_dim}:{content_hash}"
        return hashlib.sha1(key_str.encode()).hexdigest()

    def _check_cache(self, text: str) -> Optional[List[float]]:
        """Check if embedding exists in cache."""
        try:
            cache_key = self._get_cache_key(text)
            conn = sqlite3.connect(str(self.cache_db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT vec FROM cache WHERE key = ?", (cache_key,))
            row = cursor.fetchone()
            conn.close()

            if row:
                # Deserialize embedding from blob
                vec_bytes = row[0]
                vec_array = np.frombuffer(vec_bytes, dtype=np.float32)
                self.metrics["cache_hits"] += 1
                logger.debug(f"Cache hit for key {cache_key[:8]}...")
                return vec_array.tolist()

            return None
        except Exception as e:
            logger.error(f"Cache check failed: {e}")
            return None

    def _save_to_cache(self, text: str, embedding: List[float]):
        """Save embedding to cache."""
        try:
            cache_key = self._get_cache_key(text)
            content_hash = hashlib.sha256(text.encode()).hexdigest()

            # Convert embedding to bytes
            vec_array = np.array(embedding, dtype=np.float32)
            vec_bytes = vec_array.tobytes()

            conn = sqlite3.connect(str(self.cache_db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO cache (key, model_id, out_dim, content_hash, vec, ts)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    cache_key,
                    self._gemini_model,
                    self.output_dim,
                    content_hash,
                    vec_bytes,
                ),
            )

            conn.commit()
            conn.close()
            logger.debug(f"Saved to cache: key {cache_key[:8]}...")
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")

    async def _embed_single_with_retry(
        self, text: str, semaphore: asyncio.Semaphore, max_retries: int = 5
    ) -> Optional[List[float]]:
        """Embed a single text with retry logic and rate limiting."""
        # Check cache first
        cached_embedding = self._check_cache(text)
        if cached_embedding is not None:
            return cached_embedding

        import google.generativeai as genai

        for attempt in range(max_retries):
            async with semaphore:
                try:
                    # Add jitter to avoid thundering herd
                    if attempt > 0:
                        backoff = (2**attempt) + random.uniform(0, 1)
                        logger.debug(f"Retry {attempt} after {backoff:.1f}s backoff")
                        await asyncio.sleep(backoff)

                    # Call API (genai is sync, so run in executor)
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda: genai.embed_content(
                            model=self._gemini_model,
                            content=text,
                            task_type=self.embed_task_doc.lower(),
                            output_dimensionality=self.output_dim,
                            title=None,
                        ),
                    )

                    embedding = result["embedding"]

                    # Verify dimension
                    if len(embedding) != self.output_dim:
                        logger.warning(
                            f"Dimension mismatch: expected {self.output_dim}, got {len(embedding)}"
                        )

                    self.metrics["api_calls"] += 1

                    # Save to cache
                    self._save_to_cache(text, embedding)

                    return embedding

                except Exception as e:
                    error_str = str(e)
                    self.metrics["retries"] += 1

                    # Check for rate limiting
                    if "429" in error_str or "rate" in error_str.lower():
                        self.metrics["rate_limit_events"] += 1

                        # Try to extract Retry-After header if present
                        retry_after = 60  # Default 60s
                        if (
                            "retry" in error_str.lower()
                            and "after" in error_str.lower()
                        ):
                            # Try to extract seconds from error message
                            import re

                            match = re.search(
                                r"(\d+)\s*second", error_str, re.IGNORECASE
                            )
                            if match:
                                retry_after = int(match.group(1))

                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Rate limited (attempt {attempt + 1}/{max_retries}), "
                                f"waiting {retry_after}s"
                            )
                            await asyncio.sleep(retry_after)
                            continue

                    # Check for server errors (5xx)
                    if (
                        "500" in error_str
                        or "502" in error_str
                        or "503" in error_str
                        or "504" in error_str
                    ):
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Server error (attempt {attempt + 1}/{max_retries}): {error_str[:100]}"
                            )
                            continue

                    # For other errors, don't retry
                    if attempt == 0:
                        logger.error(f"Failed to embed text: {error_str[:200]}")
                        break

        # All retries exhausted
        return None

    def _embed_texts_gemini(self, texts: List[str]) -> np.ndarray:
        """Embed texts using Gemini API with async concurrency and micro-batching."""
        try:
            # Build micro-batches
            micro_batches = self._build_micro_batches(texts)
            all_embeddings = []
            text_to_index_map = {}  # Map text to its original index

            MAX_TEXT_LENGTH = 10000  # Gemini limit per text

            # Prepare all texts and track indices
            all_texts_to_embed = []
            for batch_texts in micro_batches:
                for text in batch_texts:
                    # Truncate if too long
                    if len(text) > MAX_TEXT_LENGTH:
                        logger.warning(
                            f"Text truncated from {len(text)} to {MAX_TEXT_LENGTH} chars"
                        )
                        text = text[:MAX_TEXT_LENGTH]

                    # Track original index
                    text_to_index_map[text] = len(all_texts_to_embed)
                    all_texts_to_embed.append(text)

            # Run async embedding with concurrency control
            embeddings_dict = asyncio.run(self._embed_texts_async(all_texts_to_embed))

            # Collect embeddings in order, handling failures
            for text in all_texts_to_embed:
                if text in embeddings_dict and embeddings_dict[text] is not None:
                    all_embeddings.append(embeddings_dict[text])
                else:
                    # Text failed after all retries - already quarantined
                    logger.debug(f"Skipping failed text (quarantined)")

            if not all_embeddings:
                raise ValueError(
                    "No embeddings generated - all texts failed or quarantined"
                )

            # Convert to numpy array
            embeddings_array = np.array(all_embeddings, dtype=np.float32)

            # Normalize embeddings
            norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
            embeddings_array = embeddings_array / (norms + 1e-8)

            logger.info(
                f"Embedding complete: {len(all_embeddings)}/{len(texts)} successful, "
                f"API calls: {self.metrics['api_calls']}, "
                f"Retries: {self.metrics['retries']}, "
                f"Rate limits: {self.metrics['rate_limit_events']}, "
                f"Quarantined: {self.metrics['quarantine_count']}"
            )

            return embeddings_array

        except Exception as e:
            logger.error(f"Gemini embedding failed: {e}")
            raise

    async def _embed_texts_async(
        self, texts: List[str]
    ) -> Dict[str, Optional[List[float]]]:
        """Embed multiple texts asynchronously with concurrency control."""
        semaphore = asyncio.Semaphore(self.concurrency)

        tasks = []
        for text in texts:
            task = self._embed_single_with_retry(text, semaphore)
            tasks.append(task)

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        embeddings_dict = {}
        for text, result in zip(texts, results):
            if isinstance(result, Exception):
                logger.error(f"Embedding failed for text: {result}")
                # Add to quarantine
                self._add_to_quarantine(
                    content_hash=hashlib.sha256(text.encode()).hexdigest(),
                    model=self._gemini_model,
                    reason=str(result)[:200],
                    attempts=5,  # Max retries exhausted
                )
                embeddings_dict[text] = None
            elif result is None:
                # Already handled in retry logic
                self._add_to_quarantine(
                    content_hash=hashlib.sha256(text.encode()).hexdigest(),
                    model=self._gemini_model,
                    reason="Max retries exhausted",
                    attempts=5,
                )
                embeddings_dict[text] = None
            else:
                embeddings_dict[text] = result

        return embeddings_dict

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
                    task_type=self.embed_task_query.lower(),
                    output_dimensionality=self.output_dim,
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
        if self.provider == "gemini":
            # Return configured output dimension
            return self.output_dim
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

    def _init_cache_db(self):
        """Initialize SQLite cache database."""
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            cursor = conn.cursor()

            # Create cache table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    out_dim INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    vec BLOB NOT NULL,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create index on content_hash for faster lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_ch ON cache(content_hash)
            """
            )

            conn.commit()
            conn.close()
            logger.info(f"Initialized cache database at {self.cache_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def _add_to_quarantine(
        self, content_hash: str, model: str, reason: str, attempts: int = 1
    ):
        """Add failed embedding to quarantine log."""
        try:
            quarantine_entry = {
                "content_hash": content_hash,
                "model": model,
                "dim": self.output_dim,
                "reason": reason[:200],  # Limit reason length
                "attempts": attempts,
                "ts": datetime.utcnow().isoformat(),
            }

            with open(self.quarantine_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(quarantine_entry) + "\n")

            self.metrics["quarantine_count"] += 1
            logger.debug(f"Added to quarantine: {content_hash[:8]}...")
        except Exception as e:
            logger.error(f"Failed to write quarantine entry: {e}")


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
