"""
Page-First RAG Agent Configuration

Configuration for the Page-First RAG Agent based on the Operation Manual.
Supports environment variable overrides with validation.

Environment Variables:
    PAGE_FIRST_TOPK_BM25: Number of BM25 results (default: 30)
    PAGE_FIRST_TOPK_VEC: Number of vector results (default: 30)
    PAGE_FIRST_MERGED_K: Results after RRF merge (default: 40)
    PAGE_FIRST_RERANK_KEEP: Pages to keep after reranking (default: 8)
    PAGE_FIRST_NLI_THRESHOLD: NLI entailment threshold (default: 0.60)
    PAGE_FIRST_FUZZY_MIN: Minimum fuzzy overlap (default: 0.55)
    PAGE_FIRST_NEIGHBOR_RADIUS: Page neighbor radius for CiteFix (default: 2)
    PAGE_FIRST_CTX_MAX_TOKENS: Maximum context tokens (default: 2200)
    PAGE_FIRST_ANSWER_MAX_TOKENS: Maximum answer tokens (default: 400)

Example:
    >>> from app.rag.page_first_config import PageFirstConfig
    >>> config = PageFirstConfig.from_env()
    >>> config.validate()
    >>> print(config.to_dict())
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Union

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    """
    Read integer from environment variable with fallback.

    Tries both prefixed (PAGE_FIRST_{name}) and unprefixed ({name}) versions.

    Args:
        name: Variable name (without prefix)
        default: Default value if not found

    Returns:
        Integer value from env or default
    """
    prefixed = f"PAGE_FIRST_{name}"
    value = os.environ.get(prefixed, os.environ.get(name))

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        logger.warning(
            f"Invalid integer for {prefixed}/{name}: '{value}', using default {default}"
        )
        return default


def _env_float(name: str, default: float) -> float:
    """
    Read float from environment variable with fallback.

    Tries both prefixed (PAGE_FIRST_{name}) and unprefixed ({name}) versions.

    Args:
        name: Variable name (without prefix)
        default: Default value if not found

    Returns:
        Float value from env or default
    """
    prefixed = f"PAGE_FIRST_{name}"
    value = os.environ.get(prefixed, os.environ.get(name))

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        logger.warning(
            f"Invalid float for {prefixed}/{name}: '{value}', using default {default}"
        )
        return default


@dataclass
class PageFirstConfig:
    """
    Configuration for Page-First RAG Agent.

    Attributes:
        TOPK_BM25: Number of BM25 results to retrieve (default: 30)
        TOPK_VEC: Number of vector results to retrieve (default: 30)
        MERGED_K: Number of results after RRF merge (default: 40)
        RERANK_KEEP: Number of pages to keep after reranking (default: 8)
        NLI_THRESHOLD: NLI entailment threshold, range [0.0, 1.0] (default: 0.60)
        FUZZY_MIN: Minimum fuzzy overlap score, range [0.0, 1.0] (default: 0.55)
        NEIGHBOR_RADIUS: Page neighbor radius for CiteFix (default: 2)
        CTX_MAX_TOKENS: Maximum context tokens (default: 2200)
        ANSWER_MAX_TOKENS: Maximum answer tokens (default: 400)

    Validation Rules:
        - All integers must be positive (NEIGHBOR_RADIUS >= 0)
        - Thresholds must be in range [0.0, 1.0]
        - RERANK_KEEP <= MERGED_K
        - MERGED_K <= (TOPK_BM25 + TOPK_VEC)
        - Token limits must be positive
    """

    # Retrieval parameters
    TOPK_BM25: int = 30
    TOPK_VEC: int = 30
    MERGED_K: int = 40
    RERANK_KEEP: int = 8

    # Validation thresholds
    NLI_THRESHOLD: float = 0.60
    FUZZY_MIN: float = 0.55
    NEIGHBOR_RADIUS: int = 2

    # Context limits
    CTX_MAX_TOKENS: int = 2200
    ANSWER_MAX_TOKENS: int = 400

    @classmethod
    def from_env(cls) -> "PageFirstConfig":
        """
        Create configuration from environment variables.

        Reads environment variables with fallback to defaults.
        Supports both prefixed (PAGE_FIRST_*) and unprefixed names.

        Returns:
            PageFirstConfig instance with env overrides

        Example:
            >>> config = PageFirstConfig.from_env()
            >>> config.TOPK_BM25
            30
        """
        return cls(
            TOPK_BM25=_env_int("TOPK_BM25", 30),
            TOPK_VEC=_env_int("TOPK_VEC", 30),
            MERGED_K=_env_int("MERGED_K", 40),
            RERANK_KEEP=_env_int("RERANK_KEEP", 8),
            NLI_THRESHOLD=_env_float("NLI_THRESHOLD", 0.60),
            FUZZY_MIN=_env_float("FUZZY_MIN", 0.55),
            NEIGHBOR_RADIUS=_env_int("NEIGHBOR_RADIUS", 2),
            CTX_MAX_TOKENS=_env_int("CTX_MAX_TOKENS", 2200),
            ANSWER_MAX_TOKENS=_env_int("ANSWER_MAX_TOKENS", 400),
        )

    def validate(self) -> None:
        """
        Validate configuration parameters.

        Raises:
            ValueError: If any parameter is invalid

        Example:
            >>> config = PageFirstConfig(TOPK_BM25=-1)
            >>> config.validate()
            Traceback (most recent call last):
                ...
            ValueError: TOPK_BM25 must be positive, got -1
        """
        # Check positive integers
        if self.TOPK_BM25 <= 0:
            raise ValueError(f"TOPK_BM25 must be positive, got {self.TOPK_BM25}")

        if self.TOPK_VEC <= 0:
            raise ValueError(f"TOPK_VEC must be positive, got {self.TOPK_VEC}")

        if self.MERGED_K <= 0:
            raise ValueError(f"MERGED_K must be positive, got {self.MERGED_K}")

        if self.RERANK_KEEP <= 0:
            raise ValueError(f"RERANK_KEEP must be positive, got {self.RERANK_KEEP}")

        if self.NEIGHBOR_RADIUS < 0:
            raise ValueError(
                f"NEIGHBOR_RADIUS must be >= 0, got {self.NEIGHBOR_RADIUS}"
            )

        if self.CTX_MAX_TOKENS <= 0:
            raise ValueError(
                f"CTX_MAX_TOKENS must be positive, got {self.CTX_MAX_TOKENS}"
            )

        if self.ANSWER_MAX_TOKENS <= 0:
            raise ValueError(
                f"ANSWER_MAX_TOKENS must be positive, got {self.ANSWER_MAX_TOKENS}"
            )

        # Check thresholds in [0, 1]
        if not (0.0 <= self.NLI_THRESHOLD <= 1.0):
            raise ValueError(
                f"NLI_THRESHOLD must be in [0.0, 1.0], got {self.NLI_THRESHOLD}"
            )

        if not (0.0 <= self.FUZZY_MIN <= 1.0):
            raise ValueError(f"FUZZY_MIN must be in [0.0, 1.0], got {self.FUZZY_MIN}")

        # Check relationships
        if self.RERANK_KEEP > self.MERGED_K:
            raise ValueError(
                f"RERANK_KEEP ({self.RERANK_KEEP}) must be <= MERGED_K ({self.MERGED_K})"
            )

        if self.MERGED_K > (self.TOPK_BM25 + self.TOPK_VEC):
            raise ValueError(
                f"MERGED_K ({self.MERGED_K}) must be <= "
                f"TOPK_BM25 + TOPK_VEC ({self.TOPK_BM25 + self.TOPK_VEC})"
            )

        logger.debug("PageFirstConfig validation passed")

    def to_dict(self) -> Dict[str, Union[int, float]]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary with all configuration parameters

        Example:
            >>> config = PageFirstConfig()
            >>> d = config.to_dict()
            >>> d['TOPK_BM25']
            30
        """
        return {
            "TOPK_BM25": self.TOPK_BM25,
            "TOPK_VEC": self.TOPK_VEC,
            "MERGED_K": self.MERGED_K,
            "RERANK_KEEP": self.RERANK_KEEP,
            "NLI_THRESHOLD": self.NLI_THRESHOLD,
            "FUZZY_MIN": self.FUZZY_MIN,
            "NEIGHBOR_RADIUS": self.NEIGHBOR_RADIUS,
            "CTX_MAX_TOKENS": self.CTX_MAX_TOKENS,
            "ANSWER_MAX_TOKENS": self.ANSWER_MAX_TOKENS,
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"PageFirstConfig("
            f"BM25={self.TOPK_BM25}, VEC={self.TOPK_VEC}, "
            f"MERGED={self.MERGED_K}, RERANK={self.RERANK_KEEP}, "
            f"NLI={self.NLI_THRESHOLD:.2f}, FUZZY={self.FUZZY_MIN:.2f}, "
            f"NEIGHBOR={self.NEIGHBOR_RADIUS})"
        )


if __name__ == "__main__":
    # Quick validation test
    import doctest

    doctest.testmod()

    # Smoke test
    config = PageFirstConfig.from_env()
    config.validate()
    print(f"✓ Config validated: {config}")
    print(f"✓ Config dict: {config.to_dict()}")
