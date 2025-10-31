"""
Audit Logger for Document Access Tracking

Provides comprehensive audit trails for:
- Document access attempts
- Denied access attempts
- Sensitive document access
- Compliance reporting
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.core.config import settings


@dataclass
class AuditEvent:
    """Audit event record"""

    timestamp: str
    event_type: str  # "access", "denied", "audit"
    user_id: str
    user_role: str
    document_id: str
    document_tags: List[str]
    decision: str  # "allow", "deny", "audit"
    reason: str
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Optional[Dict] = None


class AuditLogger:
    """
    Audit logger for document access tracking

    Features:
    - JSON-formatted audit logs
    - Separate log file for compliance
    - Queryable audit trail
    - Event statistics
    """

    def __init__(self, audit_log_path: Optional[str] = None):
        """
        Initialize audit logger

        Args:
            audit_log_path: Path to audit log file
        """
        self.audit_log_path = audit_log_path or getattr(
            settings, "audit_log_path", "logs/audit.jsonl"
        )

        # Ensure log directory exists
        Path(self.audit_log_path).parent.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.stats = {
            "total_events": 0,
            "access_allowed": 0,
            "access_denied": 0,
            "audit_events": 0,
        }

        logger.info(f"AuditLogger initialized: {self.audit_log_path}")

    def log_event(
        self,
        event_type: str,
        user_id: str,
        user_role: str,
        document_id: str,
        document_tags: List[str],
        decision: str,
        reason: str,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Log audit event

        Args:
            event_type: Type of event (access, denied, audit)
            user_id: User identifier
            user_role: User role
            document_id: Document identifier
            document_tags: Document tags
            decision: Access decision (allow, deny, audit)
            reason: Reason for decision
            ip_address: Client IP address
            request_id: Request identifier for tracing
            metadata: Additional metadata
        """
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type,
            user_id=user_id,
            user_role=user_role,
            document_id=document_id,
            document_tags=document_tags,
            decision=decision,
            reason=reason,
            ip_address=ip_address,
            request_id=request_id,
            metadata=metadata,
        )

        # Write to audit log file (JSONL format)
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        # Log to standard logger as well
        log_msg = (
            f"AUDIT: {event_type.upper()} - "
            f"user={user_id} role={user_role} "
            f"doc={document_id} decision={decision}"
        )

        if event_type == "denied":
            logger.warning(log_msg, extra=asdict(event))
        else:
            logger.info(log_msg, extra=asdict(event))

        # Update statistics
        self.stats["total_events"] += 1
        if decision == "allow":
            self.stats["access_allowed"] += 1
        elif decision == "deny":
            self.stats["access_denied"] += 1
        elif decision == "audit":
            self.stats["audit_events"] += 1

    def log_access_allowed(
        self,
        user_id: str,
        user_role: str,
        document_id: str,
        document_tags: List[str],
        reason: str = "Access allowed",
        **kwargs,
    ):
        """Log successful document access"""
        self.log_event(
            event_type="access",
            user_id=user_id,
            user_role=user_role,
            document_id=document_id,
            document_tags=document_tags,
            decision="allow",
            reason=reason,
            **kwargs,
        )

    def log_access_denied(
        self,
        user_id: str,
        user_role: str,
        document_id: str,
        document_tags: List[str],
        reason: str,
        **kwargs,
    ):
        """Log denied document access attempt"""
        self.log_event(
            event_type="denied",
            user_id=user_id,
            user_role=user_role,
            document_id=document_id,
            document_tags=document_tags,
            decision="deny",
            reason=reason,
            **kwargs,
        )

    def log_audit_access(
        self,
        user_id: str,
        user_role: str,
        document_id: str,
        document_tags: List[str],
        reason: str,
        **kwargs,
    ):
        """Log access to sensitive documents (requires audit)"""
        self.log_event(
            event_type="audit",
            user_id=user_id,
            user_role=user_role,
            document_id=document_id,
            document_tags=document_tags,
            decision="audit",
            reason=reason,
            **kwargs,
        )

    def query_events(
        self,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Query audit events

        Args:
            user_id: Filter by user
            document_id: Filter by document
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of events to return

        Returns:
            List of matching audit events
        """
        events = []

        try:
            if not Path(self.audit_log_path).exists():
                return events

            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    event_dict = json.loads(line)
                    event = AuditEvent(**event_dict)

                    # Apply filters
                    if user_id and event.user_id != user_id:
                        continue

                    if document_id and event.document_id != document_id:
                        continue

                    if event_type and event.event_type != event_type:
                        continue

                    if start_time:
                        event_time = datetime.fromisoformat(
                            event.timestamp.replace("Z", "+00:00")
                        )
                        if event_time < start_time:
                            continue

                    if end_time:
                        event_time = datetime.fromisoformat(
                            event.timestamp.replace("Z", "+00:00")
                        )
                        if event_time > end_time:
                            continue

                    events.append(event)

                    if len(events) >= limit:
                        break

        except Exception as e:
            logger.error(f"Failed to query audit events: {e}")

        return events

    def get_statistics(self) -> Dict:
        """Get audit statistics"""
        return {
            **self.stats,
            "audit_log_path": self.audit_log_path,
            "log_exists": Path(self.audit_log_path).exists(),
        }

    def get_user_activity(self, user_id: str, limit: int = 50) -> List[AuditEvent]:
        """Get recent activity for a user"""
        return self.query_events(user_id=user_id, limit=limit)

    def get_document_access_history(
        self, document_id: str, limit: int = 50
    ) -> List[AuditEvent]:
        """Get access history for a document"""
        return self.query_events(document_id=document_id, limit=limit)

    def get_denied_attempts(self, limit: int = 100) -> List[AuditEvent]:
        """Get recent denied access attempts"""
        return self.query_events(event_type="denied", limit=limit)

    def generate_compliance_report(
        self, start_time: datetime, end_time: datetime
    ) -> Dict:
        """
        Generate compliance report for time period

        Args:
            start_time: Report start time
            end_time: Report end time

        Returns:
            Compliance report with statistics
        """
        events = self.query_events(
            start_time=start_time, end_time=end_time, limit=10000
        )

        # Aggregate statistics
        report = {
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "total_events": len(events),
            "access_allowed": sum(1 for e in events if e.decision == "allow"),
            "access_denied": sum(1 for e in events if e.decision == "deny"),
            "audit_events": sum(1 for e in events if e.decision == "audit"),
            "unique_users": len(set(e.user_id for e in events)),
            "unique_documents": len(set(e.document_id for e in events)),
            "top_users": self._get_top_users(events, limit=10),
            "top_documents": self._get_top_documents(events, limit=10),
            "denied_attempts": [
                {
                    "timestamp": e.timestamp,
                    "user_id": e.user_id,
                    "document_id": e.document_id,
                    "reason": e.reason,
                }
                for e in events
                if e.decision == "deny"
            ],
        }

        return report

    def _get_top_users(self, events: List[AuditEvent], limit: int) -> List[Dict]:
        """Get top users by event count"""
        user_counts = {}
        for event in events:
            user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1

        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"user_id": uid, "count": count} for uid, count in sorted_users[:limit]]

    def _get_top_documents(self, events: List[AuditEvent], limit: int) -> List[Dict]:
        """Get top documents by access count"""
        doc_counts = {}
        for event in events:
            doc_counts[event.document_id] = doc_counts.get(event.document_id, 0) + 1

        sorted_docs = sorted(doc_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"document_id": did, "count": count} for did, count in sorted_docs[:limit]
        ]


# Singleton instance
_default_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create default audit logger"""
    global _default_audit_logger

    if _default_audit_logger is None:
        _default_audit_logger = AuditLogger()

    return _default_audit_logger


def reset_audit_logger():
    """Reset default audit logger (for testing)"""
    global _default_audit_logger
    _default_audit_logger = None
