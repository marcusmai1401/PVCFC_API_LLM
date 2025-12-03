"""
Tests for LLM configuration and helper functions
"""
import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.llm import (
    get_api_key_for,
    get_embedding_model,
    get_embedding_provider,
    get_model_for,
    get_provider_for,
)


class TestLLMConfiguration:
    """Test LLM configuration and validation"""

    def test_default_configuration(self):
        """Test default configuration values"""
        settings = Settings()
        assert settings.llm_provider == "none"
        assert settings.llm_tier == "light"
        assert settings.llm_light_provider is None
        assert settings.embedding_provider == "none"

    def test_provider_for_tier_fallback(self):
        """Test provider selection with fallback"""
        settings = Settings(llm_provider="gemini", llm_light_provider=None)

        # Light tier should fallback to main provider
        assert settings.provider_for_tier("light") == "gemini"
        assert settings.provider_for_tier("heavy") == "gemini"

    def test_provider_for_tier_explicit(self):
        """Test provider selection with explicit light provider"""
        settings = Settings(llm_provider="gemini", llm_light_provider="openai")

        assert settings.provider_for_tier("light") == "openai"
        assert settings.provider_for_tier("heavy") == "gemini"

    def test_embedding_provider_effective(self):
        """Test embedding provider with alias"""
        # Without alias
        settings1 = Settings(embedding_provider="openai", embedding_llm=None)
        assert settings1.embedding_provider_effective() == "openai"

        # With alias
        settings2 = Settings(embedding_provider="openai", embedding_llm="local")
        assert settings2.embedding_provider_effective() == "local"

    def test_model_provider_validation_openai(self):
        """Test model validation for OpenAI provider"""
        # Valid OpenAI models
        settings = Settings(
            llm_provider="openai",
            llm_model_heavy="gpt-4o",
            llm_model_light="gpt-4o-mini",
        )
        assert settings.llm_model_heavy == "gpt-4o"

        # Invalid OpenAI model
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                llm_provider="openai",
                llm_model_heavy="gemini-1.5-pro",  # Wrong provider model
            )
        assert "may not be compatible with OpenAI provider" in str(exc_info.value)

    def test_model_provider_validation_gemini(self):
        """Test model validation for Gemini provider"""
        # Valid Gemini models
        settings = Settings(
            llm_provider="gemini",
            llm_model_heavy="gemini-1.5-pro",
            llm_model_light="gemini-1.5-flash",
        )
        assert settings.llm_model_heavy == "gemini-1.5-pro"

        # Invalid Gemini model
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                llm_provider="gemini", llm_model_heavy="gpt-4o"  # Wrong provider model
            )
        assert "may not be compatible with Gemini provider" in str(exc_info.value)

    def test_embedding_model_validation(self):
        """Test embedding model validation"""
        # Valid OpenAI embedding model
        settings = Settings(
            embedding_provider="openai", embedding_model="text-embedding-3-small"
        )
        assert settings.embedding_model == "text-embedding-3-small"

        # Invalid OpenAI embedding model
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                embedding_provider="openai",
                embedding_model="gpt-4o",  # Not an embedding model
            )
        assert "may not be a valid OpenAI embedding model" in str(exc_info.value)

    def test_llm_provider_ready(self):
        """Test LLM provider readiness check"""
        # Provider none
        settings1 = Settings(llm_provider="none")
        assert not settings1.llm_provider_ready

        # OpenAI without key
        settings2 = Settings(llm_provider="openai", openai_api_key=None)
        assert not settings2.llm_provider_ready

        # OpenAI with key
        settings3 = Settings(llm_provider="openai", openai_api_key="test-key")
        assert settings3.llm_provider_ready

        # Gemini without key
        settings4 = Settings(llm_provider="gemini", gemini_api_key=None)
        assert not settings4.llm_provider_ready

        # Gemini with key
        settings5 = Settings(llm_provider="gemini", gemini_api_key="test-key")
        assert settings5.llm_provider_ready


class TestLLMServiceFunctions:
    """Test LLM service helper functions"""

    @patch("app.services.llm.settings")
    def test_get_provider_for(self, mock_settings):
        """Test get_provider_for function"""
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_light_provider = "openai"

        assert get_provider_for("light") == "openai"
        assert get_provider_for("heavy") == "gemini"

    @patch("app.services.llm.settings")
    def test_get_provider_for_error(self, mock_settings):
        """Test get_provider_for with no provider configured"""
        mock_settings.llm_provider = "none"
        mock_settings.llm_light_provider = None

        with pytest.raises(ValueError) as exc_info:
            get_provider_for("light")
        assert "No LLM provider configured" in str(exc_info.value)

    @patch("app.services.llm.settings")
    def test_get_provider_for_fallback(self, mock_settings):
        """Test get_provider_for with fallback"""
        mock_settings.llm_provider = "gemini"
        mock_settings.llm_light_provider = None

        assert get_provider_for("light") == "gemini"
        assert get_provider_for("heavy") == "gemini"

    @patch("app.services.llm.settings")
    def test_get_model_for(self, mock_settings):
        """Test get_model_for function"""
        mock_settings.llm_model_light = "gpt-4o-mini"
        mock_settings.llm_model_heavy = "gpt-4o"
        mock_settings.llm_provider = "openai"
        mock_settings.llm_light_provider = None

        assert get_model_for("light") == "gpt-4o-mini"
        assert get_model_for("heavy") == "gpt-4o"

    @patch("app.services.llm.settings")
    def test_get_model_for_error(self, mock_settings):
        """Test get_model_for with no model configured"""
        mock_settings.llm_model_light = None
        mock_settings.llm_model_heavy = None
        mock_settings.llm_provider = "openai"
        mock_settings.llm_light_provider = None

        with pytest.raises(ValueError) as exc_info:
            get_model_for("light")
        assert "No model configured for tier 'light'" in str(exc_info.value)

    @patch("app.services.llm.settings")
    def test_get_api_key_for(self, mock_settings):
        """Test get_api_key_for function"""
        mock_settings.openai_api_key = "openai-key"
        mock_settings.gemini_api_key = "gemini-key"

        assert get_api_key_for("openai") == "openai-key"
        assert get_api_key_for("gemini") == "gemini-key"

        # Test unknown provider raises error
        with pytest.raises(ValueError) as exc_info:
            get_api_key_for("unknown")
        assert "Unknown provider 'unknown'" in str(exc_info.value)

    @patch("app.services.llm.settings")
    def test_get_api_key_for_missing(self, mock_settings):
        """Test get_api_key_for with missing API key"""
        mock_settings.openai_api_key = None
        mock_settings.gemini_api_key = None

        with pytest.raises(ValueError) as exc_info:
            get_api_key_for("openai")
        assert "API key not configured for provider 'openai'" in str(exc_info.value)
        mock_settings.embedding_llm = None
        mock_settings.embedding_provider = "openai"

        assert get_embedding_provider() == "openai"

        mock_settings.embedding_llm = "local"
        assert get_embedding_provider() == "local"

    @patch("app.services.llm.settings")
    def test_get_embedding_model(self, mock_settings):
        """Test get_embedding_model function"""
        mock_settings.embedding_model = "text-embedding-3-small"
        mock_settings.embedding_llm = "openai"
        mock_settings.embedding_provider = "openai"

        assert get_embedding_model() == "text-embedding-3-small"

        # Test no model configured raises error
        mock_settings.embedding_model = None
        with pytest.raises(ValueError) as exc_info:
            get_embedding_model()
        assert "No embedding model configured" in str(exc_info.value)


class TestMixedProviderScenarios:
    """Test scenarios with mixed providers"""

    def test_heavy_gemini_light_openai(self):
        """Test configuration with Gemini for heavy, OpenAI for light"""
        settings = Settings(
            llm_provider="gemini",
            llm_light_provider="openai",
            llm_model_heavy="gemini-1.5-pro",
            llm_model_light="gpt-4o-mini",
            gemini_api_key="gemini-key",
            openai_api_key="openai-key",
        )

        assert settings.provider_for_tier("heavy") == "gemini"
        assert settings.provider_for_tier("light") == "openai"
        assert settings.llm_provider_ready  # Gemini is ready

    def test_all_openai_with_embedding(self):
        """Test configuration with all OpenAI services"""
        settings = Settings(
            llm_provider="openai",
            llm_model_heavy="gpt-4o",
            llm_model_light="gpt-4o-mini",
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            openai_api_key="test-key",
        )

        assert settings.provider_for_tier("heavy") == "openai"
        assert settings.provider_for_tier("light") == "openai"
        assert settings.embedding_provider_effective() == "openai"
        assert settings.llm_provider_ready

    def test_local_embedding_with_cloud_llm(self):
        """Test local embedding with cloud LLM"""
        settings = Settings(
            llm_provider="gemini",
            llm_model_heavy="gemini-1.5-pro",
            embedding_provider="local",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            gemini_api_key="test-key",
        )

        assert settings.llm_provider == "gemini"
        assert settings.embedding_provider_effective() == "local"
        assert settings.llm_provider_ready
