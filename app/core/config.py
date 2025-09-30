"""
Cấu hình ứng dụng sử dụng pydantic-settings
Đọc từ biến môi trường và .env file
"""
import os
from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình chính của ứng dụng"""

    # Cấu hình cơ bản
    app_env: Literal["local", "dev", "prod"] = "local"
    api_port: int = Field(default=8000, description="Port để chạy API server")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Thông tin phiên bản (sẽ được override bởi CI/CD)
    version: str = Field(default="0.1.0-dev", description="Phiên bản ứng dụng")
    commit_sha: str = Field(default="unknown", description="Git commit SHA")

    # Cấu hình LLM
    llm_provider: Literal["openai", "gemini", "none"] = "none"
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )

    # Phân tầng model sinh (light/heavy) và provider cho tier nhẹ
    llm_tier: Literal["light", "heavy"] = "light"
    llm_light_provider: Optional[Literal["openai", "gemini", ""]] = None
    llm_model_light: Optional[str] = Field(
        default=None, description="Model cho tier nhẹ"
    )
    llm_model_heavy: Optional[str] = Field(
        default=None, description="Model cho tier nặng"
    )

    # Cấu hình Embedding (provider/model). Cho phép alias qua EMBEDDING_LLM
    embedding_provider: Literal["openai", "gemini", "local", "none"] = "none"
    embedding_llm: Optional[Literal["openai", "gemini", "local", "none", ""]] = None
    embedding_model: Optional[str] = Field(default=None, description="Embedding model")

    # Cấu hình cache và rate limiting (cho Phase 2)
    cache_ttl_minutes: int = Field(default=10, description="Cache TTL in minutes")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")

    # ========================================
    # Phase 2 - Retrieval & Context
    # ========================================
    max_context: int = Field(
        default=8,
        description="Maximum number of context chunks to send to LLM for generation",
    )
    top_rerank: int = Field(
        default=20,
        description="Number of top candidates to keep after reranking (before selecting MAX_CONTEXT)",
    )

    # ========================================
    # Phase 2 - Vision & Text Range Scan
    # ========================================
    vision_page_selector_enabled: bool = Field(
        default=True,
        description="Enable Vision-based multimodal page selector (uses image understanding)",
    )
    text_range_scan_enabled: bool = Field(
        default=False,
        description="Enable text-only page range scan (fallback when Vision is off)",
    )

    # ========================================
    # Phase 2 - Degrade Mode & Resilience
    # ========================================
    retrieval_allow_bm25_only_fallback: bool = Field(
        default=True,
        description="Allow fallback to BM25-only retrieval when FAISS/embedding service fails",
    )
    bm25_k_when_degrade: int = Field(
        default=80,
        description="BM25 k value to use when in degrade mode (higher to compensate for missing FAISS)",
    )
    rerank_top_n_when_degrade: int = Field(
        default=50,
        description="Rerank top N value when in degrade mode (higher for better coverage)",
    )

    # ========================================
    # Phase 2 - Cache Configuration
    # ========================================
    retrieve_cache_ttl_min: int = Field(
        default=10,
        description="TTL for retrieval/rerank cache in minutes (LRU cache with time expiration)",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @property
    def llm_provider_ready(self) -> bool:
        """Kiểm tra xem LLM provider có sẵn sàng không"""
        if self.llm_provider == "none":
            return False
        elif self.llm_provider == "openai":
            return self.openai_api_key is not None
        elif self.llm_provider == "gemini":
            return self.gemini_api_key is not None
        return False

    # Helpers để chọn provider/model theo tier và embedding
    def provider_for_tier(self, tier: Literal["light", "heavy"]) -> str:
        if tier == "light":
            # Handle empty string as None
            light_provider = self.llm_light_provider
            if light_provider == "":
                light_provider = None
            return light_provider or self.llm_provider
        return self.llm_provider

    def embedding_provider_effective(self) -> str:
        # Handle empty string as None
        embedding_llm = self.embedding_llm
        if embedding_llm == "":
            embedding_llm = None
        return embedding_llm or self.embedding_provider

    @model_validator(mode="after")
    def validate_model_provider_compatibility(self):
        """Validate that model names are compatible with their providers"""
        # Validate heavy tier model
        if self.llm_model_heavy and self.llm_provider != "none":
            if self.llm_provider == "openai" and not (
                "gpt" in self.llm_model_heavy.lower()
                or "o1" in self.llm_model_heavy.lower()
            ):
                raise ValueError(
                    f"Model '{self.llm_model_heavy}' may not be compatible with OpenAI provider. "
                    "OpenAI models typically start with 'gpt-' or 'o1-'"
                )
            elif (
                self.llm_provider == "gemini"
                and "gemini" not in self.llm_model_heavy.lower()
            ):
                raise ValueError(
                    f"Model '{self.llm_model_heavy}' may not be compatible with Gemini provider. "
                    "Gemini models should contain 'gemini' in the name"
                )

        # Validate light tier model
        light_provider = self.llm_light_provider or self.llm_provider
        if self.llm_model_light and light_provider != "none":
            if light_provider == "openai" and not (
                "gpt" in self.llm_model_light.lower()
                or "o1" in self.llm_model_light.lower()
            ):
                raise ValueError(
                    f"Model '{self.llm_model_light}' may not be compatible with OpenAI provider. "
                    "OpenAI models typically start with 'gpt-' or 'o1-'"
                )
            elif (
                light_provider == "gemini"
                and "gemini" not in self.llm_model_light.lower()
            ):
                raise ValueError(
                    f"Model '{self.llm_model_light}' may not be compatible with Gemini provider. "
                    "Gemini models should contain 'gemini' in the name"
                )

        # Validate embedding model
        if self.embedding_model and self.embedding_provider_effective() == "openai":
            if not (
                "embedding" in self.embedding_model.lower()
                or "ada" in self.embedding_model.lower()
            ):
                raise ValueError(
                    f"Model '{self.embedding_model}' may not be a valid OpenAI embedding model. "
                    "OpenAI embedding models typically contain 'embedding' or 'ada' in the name"
                )

        return self


# Global settings instance
settings = Settings()
