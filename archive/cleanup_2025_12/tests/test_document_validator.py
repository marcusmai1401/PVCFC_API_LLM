"""
Tests for document validator and access control

Validates:
- Whitelist/blacklist enforcement
- Tag-based access control
- Role-based permissions
- Result filtering
"""

import pytest

from app.security.document_validator import (
    AccessDecision,
    DocumentValidator,
    ValidationResult,
)


@pytest.fixture
def validator():
    """Create validator with test data"""
    return DocumentValidator(
        whitelist={"doc_safe_1", "doc_safe_2"},
        blacklist={"doc_blocked_1", "doc_blocked_2"},
        sensitive_tags={"confidential", "pii"},
    )


def test_blacklist_denies_access(validator):
    """Blacklisted documents should be denied"""
    result = validator.validate_document_access(
        document_id="doc_blocked_1", user_id="user_1", user_role="admin"
    )

    assert result.allowed is False
    assert result.decision == AccessDecision.DENY
    assert "blacklisted" in result.reason.lower()
    assert result.should_audit is True


def test_whitelist_allows_access(validator):
    """Whitelisted documents should be allowed"""
    result = validator.validate_document_access(
        document_id="doc_safe_1", user_id="user_1", user_role="guest"
    )

    assert result.allowed is True
    assert result.decision == AccessDecision.ALLOW
    assert "whitelisted" in result.reason.lower()


def test_public_tag_allows_all(validator):
    """Public documents should be accessible to all roles"""
    for role in ["guest", "user", "admin"]:
        result = validator.validate_document_access(
            document_id="doc_public",
            user_id="user_1",
            user_role=role,
            document_tags=["public"],
        )

        assert result.allowed is True
        assert result.decision == AccessDecision.ALLOW


def test_internal_tag_denies_guest(validator):
    """Internal documents should deny guest access"""
    result = validator.validate_document_access(
        document_id="doc_internal",
        user_id="user_1",
        user_role="guest",
        document_tags=["internal"],
    )

    assert result.allowed is False
    assert result.decision == AccessDecision.DENY
    assert "internal" in result.reason.lower()


def test_internal_tag_allows_user(validator):
    """Internal documents should allow user access"""
    result = validator.validate_document_access(
        document_id="doc_internal",
        user_id="user_1",
        user_role="user",
        document_tags=["internal"],
    )

    assert result.allowed is True


def test_confidential_tag_denies_guest(validator):
    """Confidential documents should deny guest access"""
    result = validator.validate_document_access(
        document_id="doc_conf",
        user_id="user_1",
        user_role="guest",
        document_tags=["confidential"],
    )

    assert result.allowed is False
    assert result.decision == AccessDecision.DENY


def test_confidential_tag_audits_user(validator):
    """Confidential documents should audit user access"""
    result = validator.validate_document_access(
        document_id="doc_conf",
        user_id="user_1",
        user_role="user",
        document_tags=["confidential"],
    )

    assert result.allowed is True
    assert result.decision == AccessDecision.AUDIT
    assert result.should_audit is True


def test_confidential_tag_allows_admin(validator):
    """Confidential documents should allow admin access"""
    result = validator.validate_document_access(
        document_id="doc_conf",
        user_id="user_1",
        user_role="admin",
        document_tags=["confidential"],
    )

    assert result.allowed is True
    assert result.decision == AccessDecision.ALLOW


def test_pii_tag_denies_guest_and_user(validator):
    """PII documents should deny guest and user access"""
    for role in ["guest", "user"]:
        result = validator.validate_document_access(
            document_id="doc_pii",
            user_id="user_1",
            user_role=role,
            document_tags=["pii"],
        )

        assert result.allowed is False
        assert result.decision == AccessDecision.DENY


def test_pii_tag_audits_admin(validator):
    """PII documents should audit admin access"""
    result = validator.validate_document_access(
        document_id="doc_pii",
        user_id="admin_1",
        user_role="admin",
        document_tags=["pii"],
    )

    assert result.allowed is True
    assert result.decision == AccessDecision.AUDIT
    assert result.should_audit is True


def test_multiple_tags_most_restrictive(validator):
    """Multiple tags should use most restrictive decision"""
    # Public + Confidential = AUDIT for user
    result = validator.validate_document_access(
        document_id="doc_mixed",
        user_id="user_1",
        user_role="user",
        document_tags=["public", "confidential"],
    )

    assert result.allowed is True
    assert result.decision == AccessDecision.AUDIT

    # Public + PII = DENY for user
    result = validator.validate_document_access(
        document_id="doc_mixed2",
        user_id="user_1",
        user_role="user",
        document_tags=["public", "pii"],
    )

    assert result.allowed is False
    assert result.decision == AccessDecision.DENY


def test_blacklist_overrides_whitelist(validator):
    """Blacklist should take precedence over whitelist"""
    # Add document to both lists
    validator.add_to_whitelist(["doc_conflict"])
    validator.add_to_blacklist(["doc_conflict"])

    result = validator.validate_document_access(
        document_id="doc_conflict", user_id="user_1", user_role="admin"
    )

    assert result.allowed is False
    assert result.decision == AccessDecision.DENY


def test_no_restrictions_default_allow(validator):
    """Documents with no restrictions should be allowed"""
    result = validator.validate_document_access(
        document_id="doc_unknown", user_id="user_1", user_role="guest"
    )

    assert result.allowed is True
    assert result.decision == AccessDecision.ALLOW


def test_filter_results(validator):
    """Filter results should remove denied documents"""
    results = [
        {"doc_id": "doc_safe_1", "content": "Safe doc", "tags": ["public"]},
        {"doc_id": "doc_blocked_1", "content": "Blocked doc", "tags": []},
        {
            "doc_id": "doc_internal",
            "content": "Internal doc",
            "tags": ["internal"],
        },
        {"doc_id": "doc_pii", "content": "PII doc", "tags": ["pii"]},
    ]

    # Filter as guest
    filtered = validator.filter_results(results, user_id="guest_1", user_role="guest")

    # Should only have safe and public docs
    assert len(filtered) == 1  # Only doc_safe_1
    assert filtered[0]["doc_id"] == "doc_safe_1"

    # Filter as user
    filtered = validator.filter_results(results, user_id="user_1", user_role="user")

    # Should have safe, internal, but not pii or blocked
    assert len(filtered) == 2
    doc_ids = {r["doc_id"] for r in filtered}
    assert "doc_safe_1" in doc_ids
    assert "doc_internal" in doc_ids
    assert "doc_blocked_1" not in doc_ids
    assert "doc_pii" not in doc_ids


def test_filter_results_with_metadata(validator):
    """Filter should work with metadata field"""
    results = [
        {
            "content": "Doc 1",
            "metadata": {"doc_id": "doc_safe_1", "tags": ["public"]},
        },
        {
            "content": "Doc 2",
            "metadata": {"doc_id": "doc_blocked_1", "tags": []},
        },
    ]

    filtered = validator.filter_results(results, user_id="user_1", user_role="guest")

    assert len(filtered) == 1
    assert filtered[0]["metadata"]["doc_id"] == "doc_safe_1"


def test_add_to_blacklist(validator):
    """Adding to blacklist should work"""
    initial_count = len(validator.blacklist)

    validator.add_to_blacklist(["doc_new_1", "doc_new_2"])

    assert len(validator.blacklist) == initial_count + 2
    assert "doc_new_1" in validator.blacklist


def test_remove_from_blacklist(validator):
    """Removing from blacklist should work"""
    validator.remove_from_blacklist(["doc_blocked_1"])

    assert "doc_blocked_1" not in validator.blacklist

    # Should now be allowed
    result = validator.validate_document_access(
        document_id="doc_blocked_1", user_id="user_1", user_role="guest"
    )

    assert result.allowed is True


def test_add_to_whitelist(validator):
    """Adding to whitelist should work"""
    initial_count = len(validator.whitelist)

    validator.add_to_whitelist(["doc_new_3", "doc_new_4"])

    assert len(validator.whitelist) == initial_count + 2
    assert "doc_new_3" in validator.whitelist


def test_remove_from_whitelist(validator):
    """Removing from whitelist should work"""
    validator.remove_from_whitelist(["doc_safe_1"])

    assert "doc_safe_1" not in validator.whitelist


def test_get_statistics(validator):
    """Statistics should reflect current state"""
    stats = validator.get_statistics()

    assert stats["whitelist_count"] == 2
    assert stats["blacklist_count"] == 2
    assert "confidential" in stats["sensitive_tags"]
    assert "tag_rules" in stats


def test_empty_validator_allows_all():
    """Empty validator should allow all access"""
    validator = DocumentValidator()

    result = validator.validate_document_access(
        document_id="any_doc", user_id="user_1", user_role="guest"
    )

    assert result.allowed is True


def test_config_loading_missing_file():
    """Missing config file should not crash"""
    validator = DocumentValidator(config_path="/nonexistent/path.json")

    # Should still work with defaults
    assert validator.whitelist == set()
    assert validator.blacklist == set()


def test_validation_result_metadata(validator):
    """Validation result should include metadata"""
    result = validator.validate_document_access(
        document_id="doc_blocked_1", user_id="user_1", user_role="admin"
    )

    assert result.metadata is not None
    assert result.metadata["document_id"] == "doc_blocked_1"
    assert result.metadata["user_id"] == "user_1"


def test_no_document_id_in_results(validator):
    """Results without doc_id should be allowed"""
    results = [
        {"content": "Doc without ID", "score": 0.9},
        {"doc_id": "doc_blocked_1", "content": "Blocked doc"},
    ]

    filtered = validator.filter_results(results, user_id="user_1", user_role="guest")

    # Should allow doc without ID, deny blocked doc
    assert len(filtered) == 1
    assert "doc_id" not in filtered[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
