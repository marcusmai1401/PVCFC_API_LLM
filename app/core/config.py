"""
Cấu hình ứng dụng sử dụng pydantic-settings
Đọc từ biến môi trường và .env file
"""
import os
from typing import List, Literal, Optional

from pydantic import Field, field_validator, model_validator
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
    llm_max_output_tokens: int = Field(
        default=8192,
        description="Maximum output tokens for LLM generation (affects both light and heavy tiers)",
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
        default=50,
        description="Maximum number of context chunks to send to LLM for generation (increased for Gemini 3.0 Pro)",
    )
    top_rerank: int = Field(
        default=60,
        description="Number of top candidates to keep after reranking (must be >= MAX_CONTEXT)",
    )

    # ========================================
    # Phase 2 - Vision & Text Range Scan
    # ========================================
    vision_page_selector_enabled: bool = Field(
        default=True,
        description="Enable Vision-based multimodal page selector (uses image understanding)",
    )
    vision_always_on: bool = Field(
        default=True,
        description="Always use vision generation when pages available (bypasses smart gating strategy)",
    )
    text_range_scan_enabled: bool = Field(
        default=False,
        description="Enable text-only page range scan (fallback when Vision is off)",
    )

    # ========================================
    # Phase 2 - Day 13: Bbox Detection
    # ========================================
    enable_bbox_detection: bool = Field(
        default=True,
        description="Enable automatic bbox detection for citations (Day 13)",
    )
    bbox_detection_fuzzy_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Fuzzy match threshold for bbox detection (0.0-1.0)",
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

    # ========================================
    # Phase 3 - BGE Reranker Configuration
    # ========================================
    enable_bge_rerank: bool = Field(
        default=True,
        description="Enable BGE CrossEncoder reranking (Phase 3)",
    )
    bge_rerank_candidate_limit: int = Field(
        default=100,
        description="Number of candidates to retrieve before BGE reranking (increased to 100 for better recall)",
    )
    bge_rerank_top_k: int = Field(
        default=50,
        description="Final number of results after BGE reranking (increased to match MAX_CONTEXT)",
    )
    bge_rerank_level: Literal["chunk", "doc", "page"] = Field(
        default="chunk",
        description="Reranking granularity: chunk (fastest), doc (aggregate by document), page (aggregate by page)",
    )
    bge_rerank_aggregation: Literal["max", "mean", "top3_mean"] = Field(
        default="max",
        description="Score aggregation method for doc/page level reranking (max=highest chunk, mean=average, top3_mean=avg of top 3)",
    )

    # ========================================
    # Phase 2 - Chain-of-Verification (CoVe)
    # ========================================
    enable_cove: bool = Field(
        default=True,
        description="Enable Chain-of-Verification (CoVe) for answer validation (reduces hallucinations but adds latency)",
    )

    # ========================================
    # Index Directory Configuration
    # ========================================
    index_dir: str = Field(
        default="artifacts/index_production",
        description="Directory containing BM25 and FAISS indices",
    )

    # ========================================
    # Phase 4 - Weaviate Configuration
    # ========================================
    weaviate_enabled: bool = Field(
        default=False,
        description="Enable Weaviate vector database for retrieval (Phase 4)",
    )
    weaviate_host: str = Field(
        default="localhost",
        description="Weaviate server host",
    )
    weaviate_port: int = Field(
        default=8080,
        description="Weaviate server port (default: 8080 for HTTP, 50051 for gRPC)",
    )
    weaviate_grpc_port: Optional[int] = Field(
        default=50051,
        description="Weaviate gRPC port (optional, for better performance)",
    )
    weaviate_use_grpc: bool = Field(
        default=True,
        description="Use gRPC for Weaviate communication (faster than HTTP)",
    )
    weaviate_collection: str = Field(
        default="PVCFCDocuments",
        description="Weaviate collection name for document chunks",
    )
    weaviate_timeout: int = Field(
        default=30,
        description="Weaviate query timeout in seconds",
    )
    weaviate_retrieval_limit: int = Field(
        default=100,
        description="Number of results to retrieve from Weaviate before reranking (increased to 100 for better recall)",
    )

    # ========================================
    # Phase 5 - OpenSearch BM25 Configuration
    # ========================================
    opensearch_enabled: bool = Field(
        default=False,
        description="Enable OpenSearch for BM25 keyword search (replaces offline rank-bm25)",
    )
    opensearch_host: str = Field(
        default="localhost",
        description="OpenSearch server host",
    )
    opensearch_port: int = Field(
        default=9200,
        description="OpenSearch server port",
    )
    opensearch_index: str = Field(
        default="rag_chunks",
        description="OpenSearch index name for RAG chunks",
    )
    opensearch_timeout: int = Field(
        default=30,
        description="OpenSearch query timeout in seconds",
    )
    opensearch_bm25_k1: float = Field(
        default=1.2,
        description="BM25 k1 parameter (term frequency saturation)",
    )
    opensearch_bm25_b: float = Field(
        default=0.75,
        description="BM25 b parameter (length normalization)",
    )
    opensearch_retrieval_limit: int = Field(
        default=200,
        description="Number of results to retrieve from OpenSearch before reranking (200 for deep code search + header/footer filtering)",
    )

    # ========================================
    # Hybrid Retriever Mode Selection
    # ========================================
    use_hybrid_modern: bool = Field(
        default=True,
        description="Use modern hybrid (Weaviate+OpenSearch) vs legacy (FAISS+BM25 offline). Set to false for legacy fallback.",
    )

    # ========================================
    # Redis Configuration (HA with Sentinel support)
    # ========================================
    redis_mode: Literal["single", "sentinel"] = Field(
        default="single",
        description="Redis connection mode: 'single' for standalone, 'sentinel' for HA cluster",
    )

    # Single mode configuration (fallback)
    redis_host: str = Field(
        default="localhost",
        description="Redis host for single mode",
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port for single mode",
    )

    # Sentinel mode configuration
    redis_sentinels: Optional[str] = Field(
        default=None,
        description="Comma-separated list of sentinel host:port pairs (e.g., 'host1:26379,host2:26379')",
    )
    redis_sentinel_service: str = Field(
        default="mymaster",
        description="Sentinel service name (master set name)",
    )

    # Common Redis settings
    redis_password: Optional[str] = Field(
        default=None, description="Redis authentication password"
    )
    redis_db: int = Field(default=0, description="Redis database number")

    # Connection and timeout settings
    redis_socket_connect_timeout_ms: int = Field(
        default=200,
        description="Socket connect timeout in milliseconds",
    )
    redis_socket_timeout_ms: int = Field(
        default=1000,
        description="Socket timeout in milliseconds",
    )
    redis_max_retries: int = Field(
        default=3,
        description="Maximum connection retry attempts",
    )
    redis_retry_backoff_ms: int = Field(
        default=100,
        description="Retry backoff time in milliseconds",
    )

    # Legacy redis_url for backward compatibility
    redis_url: Optional[str] = Field(
        default=None,
        description="Legacy Redis URL (deprecated, use redis_mode config instead)",
    )

    # ========================================
    # Distributed Cache Configuration
    # ========================================
    use_distributed_cache: bool = Field(
        default=False,
        description="Enable Redis-backed distributed cache (feature flag for gradual rollout)",
    )
    cache_namespace: str = Field(
        default="pvcfc",
        description="Cache key namespace for isolation",
    )
    cache_default_ttl: int = Field(
        default=3600,
        description="Default cache TTL in seconds",
    )
    cache_enable_compression: bool = Field(
        default=False,
        description="Enable cache value compression (may impact performance)",
    )

    # ========================================
    # Conversation Memory (Multi-turn Chat)
    # ========================================
    conversation_ttl_hours: int = Field(
        default=24, description="Conversation TTL in hours"
    )
    max_turns_per_conversation: int = Field(
        default=50, description="Maximum turns per conversation before trimming"
    )
    max_conversation_context_tokens: int = Field(
        default=8000, description="Maximum tokens for conversation context"
    )
    summarize_every_n_turns: int = Field(
        default=8, description="Summarize conversation every N turns"
    )
    enable_provider_session: bool = Field(
        default=False,
        description="Use provider's native chat session (Gemini ChatSession)",
    )
    enable_pii_redaction: bool = Field(
        default=True, description="Enable PII redaction before persistence"
    )

    # ========================================
    # P&ID Semantic Fallback Enhancement
    # ========================================
    pid_enable_semantic_fallback: bool = Field(
        default=True,
        description="Enable enhanced semantic fallback for P&ID queries when spatial search fails",
    )
    pid_opensearch_weight: float = Field(
        default=1.0,
        description="Weight for OpenSearch results in RRF fusion (higher = more BM25 influence)",
    )
    pid_weaviate_weight: float = Field(
        default=0.3,
        description="Weight for Weaviate results in RRF fusion (lower = less semantic influence)",
    )
    pid_enable_tag_rerank: bool = Field(
        default=True,
        description="Enable P&ID tag-based reranking before BGE reranking",
    )
    pid_tag_boost_meta_exact: float = Field(
        default=10.0,
        description="Boost multiplier for exact tag match in metadata",
    )
    pid_tag_boost_text_exact: float = Field(
        default=5.0,
        description="Boost multiplier for exact tag match in text content",
    )
    pid_tag_boost_proximity: float = Field(
        default=3.0,
        description="Boost multiplier for proximity match (fuzzy/partial)",
    )
    pid_enable_safety_check: bool = Field(
        default=True,
        description="Force exact tag matches to top 3 after BGE reranking",
    )
    pid_max_tag_variants: int = Field(
        default=4,
        description="Maximum number of tag variants to generate for query expansion",
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

    @field_validator("redis_sentinels", mode="after")
    @classmethod
    def parse_sentinels(cls, v: Optional[str]) -> Optional[List[tuple[str, int]]]:
        """Parse comma-separated sentinel host:port pairs into list of tuples"""
        if not v:
            return None

        sentinels = []
        for item in v.split(","):
            item = item.strip()
            if ":" not in item:
                raise ValueError(
                    f"Invalid sentinel format '{item}'. Expected 'host:port'"
                )
            host, port_str = item.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError(f"Invalid port '{port_str}' in sentinel '{item}'")
            sentinels.append((host, port))

        return sentinels if sentinels else None

    @model_validator(mode="after")
    def validate_redis_config(self):
        """Validate Redis configuration based on mode"""
        if self.redis_mode == "sentinel":
            if not self.redis_sentinels:
                raise ValueError(
                    "REDIS_SENTINELS must be provided when REDIS_MODE is 'sentinel'. "
                    "Expected format: 'host1:port1,host2:port2,host3:port3'"
                )
            if not self.redis_sentinel_service:
                raise ValueError(
                    "REDIS_SENTINEL_SERVICE must be provided when REDIS_MODE is 'sentinel'"
                )
        elif self.redis_mode == "single":
            if not self.redis_host:
                raise ValueError(
                    "REDIS_HOST must be provided when REDIS_MODE is 'single'"
                )

        return self

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
