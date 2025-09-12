"""
Cấu hình ứng dụng sử dụng pydantic-settings
Đọc từ biến môi trường và .env file
"""
import os
from typing import Literal, Optional

from pydantic import Field
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

    # Cấu hình cache và rate limiting (cho Phase 2)
    cache_ttl_minutes: int = Field(default=10, description="Cache TTL in minutes")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="forbid"
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


# Global settings instance
settings = Settings()
