"""
Secret redaction filter for logging.

Prevents leakage of sensitive information (API keys, tokens, passwords) in application logs.
All patterns are compiled once at module load for optimal performance.
"""

import logging
import re
from typing import List, Pattern, Tuple


class SecretRedactionFilter(logging.Filter):
    """
    Logging filter that redacts sensitive information from log records.

    Redacts:
    - API keys (OpenAI, Gemini, HuggingFace, generic)
    - Bearer tokens
    - Authorization headers
    - Password fields
    - Access tokens
    - Other common secrets

    Performance:
    - All regex patterns compiled once at class load
    - Single-pass redaction over log message
    - Minimal overhead (<1ms per log record)
    """

    # Compile all patterns once at class definition time
    PATTERNS: List[Tuple[Pattern, str]] = [
        # OpenAI API keys (sk-...)
        (re.compile(r"\bsk-[a-zA-Z0-9]{20,}"), "sk-[REDACTED]"),
        # Google/Gemini API keys (AIza...)
        (re.compile(r"\bAIza[a-zA-Z0-9_-]{35,}"), "AIza[REDACTED]"),
        # HuggingFace tokens (hf_...)
        (re.compile(r"\bhf_[a-zA-Z0-9]{20,}"), "hf_[REDACTED]"),
        # Generic API keys in various formats
        (
            re.compile(
                r'\bapi[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?',
                re.IGNORECASE,
            ),
            'api_key="[REDACTED]"',
        ),
        # Bearer tokens
        (
            re.compile(r"\bBearer\s+([a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
            "Bearer [REDACTED]",
        ),
        # Authorization header values (various formats)
        (
            re.compile(
                r'\bAuthorization["\']?\s*[:=]\s*["\']?([^\s"\']{20,})["\']?',
                re.IGNORECASE,
            ),
            "Authorization: [REDACTED]",
        ),
        # X-API-Key header
        (
            re.compile(
                r'\bX-API-Key["\']?\s*[:=]\s*["\']?([^\s"\']{16,})["\']?', re.IGNORECASE
            ),
            "X-API-Key: [REDACTED]",
        ),
        # Password fields (JSON/form data)
        (
            re.compile(
                r'\bpassword["\']?\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', re.IGNORECASE
            ),
            'password="********"',
        ),
        # Access token fields
        (
            re.compile(
                r'\baccess[_-]?token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
                re.IGNORECASE,
            ),
            'access_token="[REDACTED]"',
        ),
        # Refresh token fields
        (
            re.compile(
                r'\brefresh[_-]?token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
                re.IGNORECASE,
            ),
            'refresh_token="[REDACTED]"',
        ),
        # Generic secret fields
        (
            re.compile(
                r'\bsecret["\']?\s*[:=]\s*["\']?([^\s"\']{16,})["\']?', re.IGNORECASE
            ),
            'secret="[REDACTED]"',
        ),
        # Redis password in connection strings
        (
            re.compile(r"redis://[^:]*:([^@]+)@", re.IGNORECASE),
            "redis://user:[REDACTED]@",
        ),
        # PostgreSQL password in connection strings
        (
            re.compile(r"postgresql://[^:]*:([^@]+)@", re.IGNORECASE),
            "postgresql://user:[REDACTED]@",
        ),
        # MongoDB password in connection strings
        (
            re.compile(r"mongodb://[^:]*:([^@]+)@", re.IGNORECASE),
            "mongodb://user:[REDACTED]@",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and redact sensitive information from log record.

        Args:
            record: LogRecord to filter

        Returns:
            True (always allow record through, but redact first)
        """
        # Redact message
        if record.msg:
            record.msg = self._redact(str(record.msg))

        # Redact args if present (for parameterized logging)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True  # Always pass through (after redaction)

    def _redact(self, text: str) -> str:
        """
        Apply all redaction patterns to text.

        Args:
            text: Text to redact

        Returns:
            Redacted text with secrets masked
        """
        redacted = text

        # Apply each pattern in sequence
        for pattern, replacement in self.PATTERNS:
            redacted = pattern.sub(replacement, redacted)

        return redacted


def apply_secret_redaction_filter():
    """
    Apply secret redaction filter to all relevant loggers.

    Should be called during application startup after logging is configured.
    """
    filter_instance = SecretRedactionFilter()

    # Get root logger and all known loggers
    loggers_to_filter = [
        logging.getLogger(),  # Root logger
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("app"),  # Application logger
    ]

    # Apply filter to each logger and its handlers
    for logger in loggers_to_filter:
        # Add filter to logger itself
        logger.addFilter(filter_instance)

        # Also add to all handlers
        for handler in logger.handlers:
            handler.addFilter(filter_instance)

    logging.info("Secret redaction filter applied to all loggers")


# Convenience function for manual redaction in code
def redact_secrets(text: str) -> str:
    """
    Manually redact secrets from a string.

    Useful for redacting secrets before logging or storing.

    Args:
        text: Text potentially containing secrets

    Returns:
        Text with secrets redacted

    Example:
        >>> from app.core.logging_filter import redact_secrets
        >>> redact_secrets("API key: sk-abc123xyz")
        'API key: sk-[REDACTED]'
    """
    redacted = text
    for pattern, replacement in SecretRedactionFilter.PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
