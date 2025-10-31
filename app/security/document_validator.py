"""
Document Validator for Access Control and Security

Provides:
- Document ID whitelist/blacklist validation
- Tag-based access control
- User permission checking
- Audit logging for sensitive document access
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

from loguru import logger

from app.core.config import settings


class AccessDecision(Enum):
    """Access control decision"""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but log for audit


@dataclass
class ValidationResult:
    """Result of document validation"""

    allowed: bool
    decision: AccessDecision
    reason: str
    should_audit: bool = False
    metadata: Optional[Dict] = None


class DocumentValidator:
    """
    Document-level access control and validation

    Features:
    - Whitelist/blacklist document IDs
    - Tag-based permissions (e.g., "confidential", "public")
    - User role checking
    - Audit logging for sensitive documents
    """

    def __init__(
        self,
        whitelist: Optional[Set[str]] = None,
        blacklist: Optional[Set[str]] = None,
        sensitive_tags: Optional[Set[str]] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize document validator

        Args:
            whitelist: Set of explicitly allowed document IDs
            blacklist: Set of explicitly denied document IDs
            sensitive_tags: Tags that require audit logging
            config_path: Path to validation config file (JSON)
        """
        self.whitelist = whitelist or set()
        self.blacklist = blacklist or set()
        self.sensitive_tags = sensitive_tags or {"confidential", "internal", "pii"}

        # Tag-based access rules
        # Format: {tag: {role: decision}}
        self.tag_rules: Dict[str, Dict[str, AccessDecision]] = {
            "public": {"guest": AccessDecision.ALLOW, "user": AccessDecision.ALLOW},
            "internal": {"guest": AccessDecision.DENY, "user": AccessDecision.ALLOW},
            "confidential": {
                "guest": AccessDecision.DENY,
                "user": AccessDecision.AUDIT,
                "admin": AccessDecision.ALLOW,
            },
            "pii": {
                "guest": AccessDecision.DENY,
                "user": AccessDecision.DENY,
                "admin": AccessDecision.AUDIT,
            },
        }

        # Load config if provided
        if config_path:
            self._load_config(config_path)

        logger.info(
            f"DocumentValidator initialized: "
            f"whitelist={len(self.whitelist)}, "
            f"blacklist={len(self.blacklist)}, "
            f"sensitive_tags={len(self.sensitive_tags)}"
        )

    def _load_config(self, config_path: str):
        """Load validation rules from config file"""
        try:
            path = Path(config_path)
            if not path.exists():
                logger.warning(f"Config file not found: {config_path}")
                return

            with open(path, "r") as f:
                config = json.load(f)

            # Load whitelist
            if "whitelist" in config:
                self.whitelist.update(config["whitelist"])

            # Load blacklist
            if "blacklist" in config:
                self.blacklist.update(config["blacklist"])

            # Load sensitive tags
            if "sensitive_tags" in config:
                self.sensitive_tags.update(config["sensitive_tags"])

            # Load tag rules
            if "tag_rules" in config:
                for tag, rules in config["tag_rules"].items():
                    self.tag_rules[tag] = {
                        role: AccessDecision(decision)
                        for role, decision in rules.items()
                    }

            logger.info(f"Loaded validation config from {config_path}")

        except Exception as e:
            logger.error(f"Failed to load validation config: {e}")

    def validate_document_access(
        self,
        document_id: str,
        user_id: Optional[str] = None,
        user_role: str = "guest",
        document_tags: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Validate if user can access document

        Args:
            document_id: Document identifier
            user_id: User identifier (for audit logging)
            user_role: User role (guest, user, admin)
            document_tags: Tags associated with document

        Returns:
            ValidationResult with access decision
        """
        document_tags = document_tags or []

        # Step 1: Check blacklist (highest priority)
        if document_id in self.blacklist:
            logger.warning(
                f"Access DENIED: Document {document_id} is blacklisted",
                extra={"user_id": user_id, "document_id": document_id},
            )
            return ValidationResult(
                allowed=False,
                decision=AccessDecision.DENY,
                reason="Document is blacklisted",
                should_audit=True,
                metadata={"document_id": document_id, "user_id": user_id},
            )

        # Step 2: Check whitelist (second priority)
        if self.whitelist and document_id in self.whitelist:
            logger.debug(f"Access ALLOWED: Document {document_id} is whitelisted")
            return ValidationResult(
                allowed=True,
                decision=AccessDecision.ALLOW,
                reason="Document is whitelisted",
                should_audit=False,
            )

        # Step 3: Check tag-based rules
        if document_tags:
            # Find most restrictive decision
            decisions = []
            for tag in document_tags:
                if tag in self.tag_rules:
                    role_rules = self.tag_rules[tag]
                    decision = role_rules.get(
                        user_role, AccessDecision.DENY
                    )  # Default deny
                    decisions.append((tag, decision))

            if decisions:
                # Most restrictive: DENY > AUDIT > ALLOW
                has_deny = any(d[1] == AccessDecision.DENY for d in decisions)
                has_audit = any(d[1] == AccessDecision.AUDIT for d in decisions)

                if has_deny:
                    denied_tags = [d[0] for d in decisions if d[1] == AccessDecision.DENY]
                    logger.warning(
                        f"Access DENIED: User {user_role} cannot access tags {denied_tags}",
                        extra={
                            "user_id": user_id,
                            "document_id": document_id,
                            "tags": denied_tags,
                        },
                    )
                    return ValidationResult(
                        allowed=False,
                        decision=AccessDecision.DENY,
                        reason=f"User role '{user_role}' denied for tags: {', '.join(denied_tags)}",
                        should_audit=True,
                        metadata={
                            "document_id": document_id,
                            "user_id": user_id,
                            "denied_tags": denied_tags,
                        },
                    )

                if has_audit:
                    audit_tags = [d[0] for d in decisions if d[1] == AccessDecision.AUDIT]
                    logger.info(
                        f"Access ALLOWED (AUDIT): Sensitive tags {audit_tags}",
                        extra={
                            "user_id": user_id,
                            "document_id": document_id,
                            "tags": audit_tags,
                        },
                    )
                    return ValidationResult(
                        allowed=True,
                        decision=AccessDecision.AUDIT,
                        reason=f"Access granted but audited for tags: {', '.join(audit_tags)}",
                        should_audit=True,
                        metadata={
                            "document_id": document_id,
                            "user_id": user_id,
                            "audit_tags": audit_tags,
                        },
                    )

        # Step 4: Default allow (if no restrictions matched)
        return ValidationResult(
            allowed=True,
            decision=AccessDecision.ALLOW,
            reason="No restrictions apply",
            should_audit=False,
        )

    def filter_results(
        self,
        results: List[Dict],
        user_id: Optional[str] = None,
        user_role: str = "guest",
    ) -> List[Dict]:
        """
        Filter retrieval results based on user permissions

        Args:
            results: List of retrieval results with metadata
            user_id: User identifier
            user_role: User role

        Returns:
            Filtered list of allowed results
        """
        filtered = []
        denied_count = 0
        audit_count = 0

        for result in results:
            # Extract document info
            doc_id = result.get("doc_id") or result.get("metadata", {}).get("doc_id")
            tags = result.get("tags") or result.get("metadata", {}).get("tags", [])

            if not doc_id:
                # No document ID, allow by default
                filtered.append(result)
                continue

            # Validate access
            validation = self.validate_document_access(
                document_id=doc_id,
                user_id=user_id,
                user_role=user_role,
                document_tags=tags,
            )

            if validation.allowed:
                filtered.append(result)
                if validation.should_audit:
                    audit_count += 1
            else:
                denied_count += 1

        if denied_count > 0:
            logger.info(
                f"Filtered {denied_count} documents due to access restrictions",
                extra={"user_id": user_id, "user_role": user_role},
            )

        if audit_count > 0:
            logger.info(
                f"Accessed {audit_count} sensitive documents (audit logged)",
                extra={"user_id": user_id, "user_role": user_role},
            )

        return filtered

    def add_to_blacklist(self, document_ids: List[str]) -> None:
        """Add document IDs to blacklist"""
        self.blacklist.update(document_ids)
        logger.info(f"Added {len(document_ids)} documents to blacklist")

    def remove_from_blacklist(self, document_ids: List[str]) -> None:
        """Remove document IDs from blacklist"""
        self.blacklist.difference_update(document_ids)
        logger.info(f"Removed {len(document_ids)} documents from blacklist")

    def add_to_whitelist(self, document_ids: List[str]) -> None:
        """Add document IDs to whitelist"""
        self.whitelist.update(document_ids)
        logger.info(f"Added {len(document_ids)} documents to whitelist")

    def remove_from_whitelist(self, document_ids: List[str]) -> None:
        """Remove document IDs from whitelist"""
        self.whitelist.difference_update(document_ids)
        logger.info(f"Removed {len(document_ids)} documents from whitelist")

    def get_statistics(self) -> Dict:
        """Get validator statistics"""
        return {
            "whitelist_count": len(self.whitelist),
            "blacklist_count": len(self.blacklist),
            "sensitive_tags": list(self.sensitive_tags),
            "tag_rules": {
                tag: {role: dec.value for role, dec in rules.items()}
                for tag, rules in self.tag_rules.items()
            },
        }


# Singleton instance for global access
_default_validator: Optional[DocumentValidator] = None


def get_document_validator() -> DocumentValidator:
    """Get or create default document validator"""
    global _default_validator

    if _default_validator is None:
        # Try to load from config
        config_path = getattr(settings, "document_validator_config", None)
        _default_validator = DocumentValidator(config_path=config_path)

    return _default_validator


def reset_document_validator():
    """Reset default validator (for testing)"""
    global _default_validator
    _default_validator = None
