"""
PII redaction utilities for conversation persistence.

Redacts sensitive information (emails, phones, IDs) before storing.
"""

import re
from typing import Optional

from loguru import logger


class PIIRedactor:
    """
    Redacts personally identifiable information.

    Patterns:
    - Email addresses
    - Phone numbers (various formats)
    - Vietnamese ID numbers
    - Credit card-like numbers
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

        # Redaction patterns
        self.patterns = [
            # Email addresses
            (
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "[EMAIL_REDACTED]",
            ),
            # Phone numbers (various formats)
            (
                r"(?:\+84|0)\d{9,10}\b",
                "[PHONE_REDACTED]",
            ),
            # Vietnamese ID/CCCD (12 digits)
            (
                r"\b\d{12}\b",
                "[ID_REDACTED]",
            ),
            # Credit card-like numbers (13-19 digits with optional spaces/dashes)
            (
                r"\b(?:\d[ -]*?){13,19}\b",
                "[CARD_REDACTED]",
            ),
        ]

    def redact(self, text: str) -> str:
        """
        Redact PII from text.

        Args:
            text: Text to redact

        Returns:
            Redacted text
        """
        if not self.enabled:
            return text

        if not text:
            return text

        redacted = text
        redaction_count = 0

        try:
            for pattern, replacement in self.patterns:
                matches = re.findall(pattern, redacted)
                if matches:
                    redaction_count += len(matches)
                    redacted = re.sub(pattern, replacement, redacted)

            if redaction_count > 0:
                logger.debug(f"Redacted {redaction_count} PII instances")

            return redacted

        except Exception as e:
            logger.error(f"Failed to redact PII: {e}")
            # Return original text if redaction fails
            return text

    def redact_turn(self, turn: dict) -> dict:
        """
        Redact PII from a conversation turn.

        Args:
            turn: Turn dictionary with 'content' field

        Returns:
            Turn with redacted content
        """
        if not self.enabled:
            return turn

        turn_copy = turn.copy()
        if "content" in turn_copy:
            turn_copy["content"] = self.redact(turn_copy["content"])

        return turn_copy
