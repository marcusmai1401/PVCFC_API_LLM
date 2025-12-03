"""
Unit tests for secret redaction logging filter.

Tests:
- API key redaction (OpenAI, Gemini, HuggingFace)
- Bearer token redaction
- Authorization header redaction
- Password field redaction
- Generic token redaction
- Connection string password redaction
- Performance benchmarks
"""

import time

import pytest

from app.core.logging_filter import SecretRedactionFilter, redact_secrets


class TestSecretRedactionFilter:
    """Test suite for SecretRedactionFilter"""

    def test_openai_api_key_redaction(self):
        """Test OpenAI API key (sk-...) is redacted"""
        text = "Using API key: sk-proj-abcdef123456789012345678901234567890"
        expected = "Using API key: sk-[REDACTED]"
        assert redact_secrets(text) == expected

    def test_gemini_api_key_redaction(self):
        """Test Google/Gemini API key (AIza...) is redacted"""
        text = "API_KEY=AIzaSyD1234567890abcdefghijklmnopqrstuvwxyz"
        expected = "API_KEY=AIza[REDACTED]"
        assert redact_secrets(text) == expected

    def test_huggingface_token_redaction(self):
        """Test HuggingFace token (hf_...) is redacted"""
        text = "Authorization: hf_abc123def456ghi789jkl012mno345pqr678"
        expected = "Authorization: hf_[REDACTED]"
        assert redact_secrets(text) == expected

    def test_bearer_token_redaction(self):
        """Test Bearer token is redacted"""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        expected = "Authorization: Bearer [REDACTED]"
        assert redact_secrets(text) == expected

    def test_generic_api_key_field_redaction(self):
        """Test generic api_key field is redacted"""
        cases = [
            ('api_key="abc123def456ghi789"', 'api_key="[REDACTED]"'),
            ("api-key: secret_token_12345", 'api_key="[REDACTED]"'),
            ("apikey=myverysecretkey123", 'api_key="[REDACTED]"'),
        ]
        for text, expected in cases:
            result = redact_secrets(text)
            assert "[REDACTED]" in result, f"Failed for: {text}"

    def test_authorization_header_redaction(self):
        """Test Authorization header values are redacted"""
        text = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        result = redact_secrets(text)
        assert "dXNlcjpwYXNzd29yZA==" not in result
        assert "[REDACTED]" in result

    def test_x_api_key_header_redaction(self):
        """Test X-API-Key header is redacted"""
        text = "X-API-Key: my-secret-api-key-123456"
        result = redact_secrets(text)
        assert "my-secret-api-key-123456" not in result
        assert "[REDACTED]" in result

    def test_password_field_redaction(self):
        """Test password fields are redacted"""
        cases = [
            ('password="mysecretpass123"', 'password="********"'),
            ("PASSWORD: admin123456", 'password="********"'),
            ("password=verysecurepassword", 'password="********"'),
        ]
        for text, _ in cases:
            result = redact_secrets(text)
            assert (
                "password" not in result.lower()
                or "********" in result
                or "[REDACTED]" in result
            )

    def test_access_token_redaction(self):
        """Test access_token fields are redacted"""
        text = 'access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"'
        result = redact_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_refresh_token_redaction(self):
        """Test refresh_token fields are redacted"""
        text = "refresh-token: refresh_abc123def456xyz789"
        result = redact_secrets(text)
        assert "refresh_abc123def456xyz789" not in result
        assert "[REDACTED]" in result

    def test_redis_connection_string_redaction(self):
        """Test Redis password in connection string is redacted"""
        text = "redis://user:mysecretpassword@localhost:6379/0"
        result = redact_secrets(text)
        assert "mysecretpassword" not in result
        assert "redis://user:[REDACTED]@" in result

    def test_postgresql_connection_string_redaction(self):
        """Test PostgreSQL password in connection string is redacted"""
        text = "postgresql://dbuser:dbpass123@localhost:5432/mydb"
        result = redact_secrets(text)
        assert "dbpass123" not in result
        assert "postgresql://user:[REDACTED]@" in result

    def test_mongodb_connection_string_redaction(self):
        """Test MongoDB password in connection string is redacted"""
        text = "mongodb://admin:mongopass456@cluster.example.com/database"
        result = redact_secrets(text)
        assert "mongopass456" not in result
        assert "mongodb://user:[REDACTED]@" in result

    def test_no_false_positive_redaction(self):
        """Test that innocent strings are not over-redacted"""
        innocent_texts = [
            "This is a normal sentence about API documentation",
            "The password policy requires 8 characters",
            "Bearer tokens are used for authentication",
            "sk is a common abbreviation",
            "User ID: 12345",
        ]
        for text in innocent_texts:
            result = redact_secrets(text)
            # Should not be significantly different (may have minor changes)
            # but should not have [REDACTED] or ******** for innocent strings
            if "API" not in text.upper():
                assert "[REDACTED]" not in result or text == result

    def test_structured_json_with_secrets(self):
        """Test redaction in structured JSON-like logs"""
        text = """
        {
            "user": "admin",
            "password": "secretpass123",
            "api_key": "sk-proj-abcdef1234567890",
            "config": {
                "redis_url": "redis://user:mypass@localhost:6379"
            }
        }
        """
        result = redact_secrets(text)

        # Check all secrets are redacted
        assert "secretpass123" not in result
        assert "sk-proj-abcdef1234567890" not in result
        assert "mypass" not in result

        # Check redaction markers are present
        assert "********" in result or "[REDACTED]" in result

    def test_multiple_secrets_in_single_string(self):
        """Test multiple secrets in one log line are all redacted"""
        text = (
            "Config loaded: openai_key=sk-abc123xyz, "
            "gemini_key=AIzaSyD1234567890abcdef, "
            "redis=redis://user:pass123@localhost"
        )
        result = redact_secrets(text)

        # All three secrets should be redacted
        assert "sk-abc123xyz" not in result
        assert "AIzaSyD1234567890abcdef" not in result
        assert "pass123" not in result
        assert result.count("[REDACTED]") >= 2  # At least 2 redactions

    def test_very_long_token_redaction(self):
        """Test very long tokens (JWT-style) are redacted efficiently"""
        # Simulate a long JWT token
        long_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "a" * 500 + ".signature123"
        )
        text = f"Bearer {long_token}"

        result = redact_secrets(text)
        assert long_token not in result
        assert "Bearer [REDACTED]" in result

    def test_performance_large_log_message(self):
        """Test performance on large log messages"""
        # Create a large log message (10KB)
        large_text = "Normal log line without secrets. " * 300
        large_text += "api_key=sk-secretkey123 "
        large_text += "More normal log lines. " * 300

        start = time.time()
        result = redact_secrets(large_text)
        duration_ms = (time.time() - start) * 1000

        # Should complete in under 10ms for 10KB of text
        assert duration_ms < 10, f"Redaction took {duration_ms:.2f}ms (too slow)"
        assert "sk-secretkey123" not in result

    def test_performance_many_secrets(self):
        """Test performance with many secrets in one message"""
        # Message with 20 different secrets
        secrets = [f"key{i}=sk-secret{i:03d}{'x'*20}" for i in range(20)]
        text = " | ".join(secrets)

        start = time.time()
        result = redact_secrets(text)
        duration_ms = (time.time() - start) * 1000

        # Should complete quickly even with many secrets
        assert duration_ms < 5, f"Redaction took {duration_ms:.2f}ms (too slow)"

        # All secrets should be redacted
        for i in range(20):
            assert f"secret{i:03d}" not in result

    def test_logging_filter_with_parameterized_logging(self):
        """Test filter works with parameterized logging"""
        import logging

        filter_instance = SecretRedactionFilter()

        # Create a mock log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="API key: %s",
            args=("sk-secret123456789012345678901234567890",),
            exc_info=None,
        )

        # Apply filter
        filter_instance.filter(record)

        # Check args are redacted
        assert "sk-secret123456789012345678901234567890" not in str(record.args)
        assert "[REDACTED]" in str(record.args)

    def test_edge_case_empty_string(self):
        """Test empty string doesn't cause errors"""
        result = redact_secrets("")
        assert result == ""

    def test_edge_case_none_equivalent(self):
        """Test None-like values don't cause errors"""
        # Filter should handle string conversion
        result = redact_secrets("None")
        assert result == "None"

    def test_case_insensitive_field_names(self):
        """Test field names are matched case-insensitively"""
        cases = [
            "API_KEY=sk-abc123def456",
            "Api-Key=sk-abc123def456",
            "api_key=sk-abc123def456",
            "PASSWORD=secret123",
            "Password=secret123",
            "password=secret123",
        ]
        for text in cases:
            result = redact_secrets(text)
            assert "[REDACTED]" in result or "********" in result


# Integration test with actual logging
def test_integration_with_logging():
    """Integration test: verify filter works with actual logging module"""
    import io
    import logging

    # Create logger with string stream
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)

    # Apply filter
    filter_instance = SecretRedactionFilter()
    handler.addFilter(filter_instance)

    logger.addHandler(handler)

    # Log a message with secrets
    logger.info("Connecting with api_key=sk-secret123456789012345678901234567890")

    # Get logged output
    output = stream.getvalue()

    # Verify secret is redacted in output
    assert "sk-secret123456789012345678901234567890" not in output
    assert "[REDACTED]" in output or "sk-[REDACTED]" in output

    # Cleanup
    logger.removeHandler(handler)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
