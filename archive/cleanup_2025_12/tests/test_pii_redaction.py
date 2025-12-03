"""
Tests for PII redaction.
"""

import pytest

from app.utils.redaction import PIIRedactor


def test_email_redaction():
    """Test email address redaction"""
    redactor = PIIRedactor(enabled=True)

    text = "Contact me at john.doe@example.com for details"
    redacted = redactor.redact(text)

    assert "john.doe@example.com" not in redacted
    assert "[EMAIL_REDACTED]" in redacted
    assert "Contact me at" in redacted  # Rest preserved


def test_phone_redaction():
    """Test phone number redaction"""
    redactor = PIIRedactor(enabled=True)

    # Vietnamese phone formats
    text1 = "Call me at 0901234567"
    redacted1 = redactor.redact(text1)
    assert "0901234567" not in redacted1
    assert "[PHONE_REDACTED]" in redacted1

    text2 = "Phone: +84901234567"
    redacted2 = redactor.redact(text2)
    assert "+84901234567" not in redacted2
    assert "[PHONE_REDACTED]" in redacted2


def test_vietnamese_id_redaction():
    """Test Vietnamese ID (CCCD) redaction"""
    redactor = PIIRedactor(enabled=True)

    text = "ID number is 123456789012"
    redacted = redactor.redact(text)

    assert "123456789012" not in redacted
    assert "[ID_REDACTED]" in redacted


def test_technical_numbers_preserved():
    """Test that technical numbers are NOT redacted"""
    redactor = PIIRedactor(enabled=True)

    # Equipment tags, pressures, temperatures should be preserved
    text = "K06101 operates at 15 bar and 80 degrees"
    redacted = redactor.redact(text)

    assert "K06101" in redacted  # Equipment tag preserved
    assert "15" in redacted  # Pressure preserved
    assert "80" in redacted  # Temperature preserved


def test_multiple_pii_types():
    """Test redacting multiple PII types in one text"""
    redactor = PIIRedactor(enabled=True)

    text = "Email test@example.com, phone 0901234567, ID 123456789012"
    redacted = redactor.redact(text)

    assert "test@example.com" not in redacted
    assert "0901234567" not in redacted
    assert "123456789012" not in redacted
    assert redacted.count("[EMAIL_REDACTED]") == 1
    assert redacted.count("[PHONE_REDACTED]") == 1
    assert redacted.count("[ID_REDACTED]") == 1


def test_redaction_disabled():
    """Test that redaction can be disabled"""
    redactor = PIIRedactor(enabled=False)

    text = "Email test@example.com, phone 0901234567"
    redacted = redactor.redact(text)

    # Should return original text
    assert redacted == text
    assert "test@example.com" in redacted


def test_empty_text():
    """Test handling of empty text"""
    redactor = PIIRedactor(enabled=True)

    assert redactor.redact("") == ""
    assert redactor.redact(None) == None


def test_redact_turn():
    """Test redacting a conversation turn"""
    redactor = PIIRedactor(enabled=True)

    turn = {
        "role": "user",
        "content": "My email is test@example.com",
        "timestamp": "2025-10-20T10:00:00",
    }

    redacted_turn = redactor.redact_turn(turn)

    assert redacted_turn["role"] == "user"
    assert redacted_turn["timestamp"] == "2025-10-20T10:00:00"
    assert "test@example.com" not in redacted_turn["content"]
    assert "[EMAIL_REDACTED]" in redacted_turn["content"]
