"""
Tests for audit logger

Validates:
- Event logging
- Event querying
- Statistics tracking
- Compliance reporting
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.security.audit_logger import AuditEvent, AuditLogger


@pytest.fixture
def temp_audit_log():
    """Create temporary audit log file"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def audit_logger(temp_audit_log):
    """Create audit logger with temp file"""
    return AuditLogger(audit_log_path=temp_audit_log)


def test_log_access_allowed(audit_logger):
    """Test logging allowed access"""
    audit_logger.log_access_allowed(
        user_id="user_1",
        user_role="user",
        document_id="doc_1",
        document_tags=["public"],
    )

    assert audit_logger.stats["total_events"] == 1
    assert audit_logger.stats["access_allowed"] == 1


def test_log_access_denied(audit_logger):
    """Test logging denied access"""
    audit_logger.log_access_denied(
        user_id="user_1",
        user_role="guest",
        document_id="doc_secure",
        document_tags=["confidential"],
        reason="Insufficient permissions",
    )

    assert audit_logger.stats["total_events"] == 1
    assert audit_logger.stats["access_denied"] == 1


def test_log_audit_access(audit_logger):
    """Test logging audited access"""
    audit_logger.log_audit_access(
        user_id="user_1",
        user_role="admin",
        document_id="doc_pii",
        document_tags=["pii"],
        reason="Admin accessed PII document",
    )

    assert audit_logger.stats["total_events"] == 1
    assert audit_logger.stats["audit_events"] == 1


def test_log_event_writes_to_file(audit_logger, temp_audit_log):
    """Test that events are written to file"""
    audit_logger.log_access_allowed(
        user_id="user_1",
        user_role="user",
        document_id="doc_1",
        document_tags=["public"],
    )

    # Read file and verify
    with open(temp_audit_log, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1

    event_dict = json.loads(lines[0])
    assert event_dict["user_id"] == "user_1"
    assert event_dict["document_id"] == "doc_1"
    assert event_dict["decision"] == "allow"


def test_log_event_with_metadata(audit_logger):
    """Test logging with additional metadata"""
    audit_logger.log_event(
        event_type="access",
        user_id="user_1",
        user_role="user",
        document_id="doc_1",
        document_tags=["public"],
        decision="allow",
        reason="Normal access",
        ip_address="192.168.1.1",
        request_id="req_123",
        metadata={"query": "test query", "method": "GET"},
    )

    events = audit_logger.query_events()
    assert len(events) == 1
    assert events[0].ip_address == "192.168.1.1"
    assert events[0].request_id == "req_123"
    assert events[0].metadata["query"] == "test query"


def test_query_events_by_user(audit_logger):
    """Test querying events by user"""
    # Log events for different users
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_1", document_tags=[]
    )
    audit_logger.log_access_allowed(
        user_id="user_2", user_role="user", document_id="doc_2", document_tags=[]
    )
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_3", document_tags=[]
    )

    # Query for user_1
    events = audit_logger.query_events(user_id="user_1")

    assert len(events) == 2
    assert all(e.user_id == "user_1" for e in events)


def test_query_events_by_document(audit_logger):
    """Test querying events by document"""
    # Log accesses to different documents
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_A", document_tags=[]
    )
    audit_logger.log_access_allowed(
        user_id="user_2", user_role="user", document_id="doc_B", document_tags=[]
    )
    audit_logger.log_access_denied(
        user_id="user_3",
        user_role="guest",
        document_id="doc_A",
        document_tags=["confidential"],
        reason="Guest denied",
    )

    # Query for doc_A
    events = audit_logger.query_events(document_id="doc_A")

    assert len(events) == 2
    assert all(e.document_id == "doc_A" for e in events)


def test_query_events_by_type(audit_logger):
    """Test querying events by event type"""
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_1", document_tags=[]
    )
    audit_logger.log_access_denied(
        user_id="user_2",
        user_role="guest",
        document_id="doc_2",
        document_tags=[],
        reason="Denied",
    )
    audit_logger.log_audit_access(
        user_id="user_3",
        user_role="admin",
        document_id="doc_3",
        document_tags=["pii"],
        reason="Audit",
    )

    # Query denied events
    denied_events = audit_logger.query_events(event_type="denied")
    assert len(denied_events) == 1
    assert denied_events[0].event_type == "denied"


def test_query_events_with_limit(audit_logger):
    """Test query limit"""
    # Log many events
    for i in range(10):
        audit_logger.log_access_allowed(
            user_id=f"user_{i}",
            user_role="user",
            document_id=f"doc_{i}",
            document_tags=[],
        )

    # Query with limit
    events = audit_logger.query_events(limit=5)

    assert len(events) == 5


def test_get_user_activity(audit_logger):
    """Test getting user activity"""
    # Log activity for user
    for i in range(3):
        audit_logger.log_access_allowed(
            user_id="user_1",
            user_role="user",
            document_id=f"doc_{i}",
            document_tags=[],
        )

    activity = audit_logger.get_user_activity("user_1")

    assert len(activity) == 3
    assert all(e.user_id == "user_1" for e in activity)


def test_get_document_access_history(audit_logger):
    """Test getting document access history"""
    # Log accesses to document
    for i in range(3):
        audit_logger.log_access_allowed(
            user_id=f"user_{i}",
            user_role="user",
            document_id="doc_important",
            document_tags=["internal"],
        )

    history = audit_logger.get_document_access_history("doc_important")

    assert len(history) == 3
    assert all(e.document_id == "doc_important" for e in history)


def test_get_denied_attempts(audit_logger):
    """Test getting denied access attempts"""
    # Log various events
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_1", document_tags=[]
    )
    audit_logger.log_access_denied(
        user_id="user_2",
        user_role="guest",
        document_id="doc_secure",
        document_tags=["confidential"],
        reason="Guest denied",
    )
    audit_logger.log_access_denied(
        user_id="user_3",
        user_role="user",
        document_id="doc_pii",
        document_tags=["pii"],
        reason="User denied PII",
    )

    denied = audit_logger.get_denied_attempts()

    assert len(denied) == 2
    assert all(e.event_type == "denied" for e in denied)


def test_get_statistics(audit_logger):
    """Test getting audit statistics"""
    # Log various events
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_1", document_tags=[]
    )
    audit_logger.log_access_denied(
        user_id="user_2",
        user_role="guest",
        document_id="doc_2",
        document_tags=[],
        reason="Denied",
    )

    stats = audit_logger.get_statistics()

    assert stats["total_events"] == 2
    assert stats["access_allowed"] == 1
    assert stats["access_denied"] == 1
    assert "audit_log_path" in stats


def test_generate_compliance_report(audit_logger):
    """Test compliance report generation"""
    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(hours=1)

    # Log various events
    audit_logger.log_access_allowed(
        user_id="user_1", user_role="user", document_id="doc_1", document_tags=[]
    )
    audit_logger.log_access_allowed(
        user_id="user_2", user_role="user", document_id="doc_1", document_tags=[]
    )
    audit_logger.log_access_denied(
        user_id="user_3",
        user_role="guest",
        document_id="doc_secure",
        document_tags=[],
        reason="Denied",
    )
    audit_logger.log_audit_access(
        user_id="user_1",
        user_role="admin",
        document_id="doc_pii",
        document_tags=["pii"],
        reason="Admin access",
    )

    report = audit_logger.generate_compliance_report(start_time, end_time)

    assert report["total_events"] == 4
    assert report["access_allowed"] == 2
    assert report["access_denied"] == 1
    assert report["audit_events"] == 1
    assert report["unique_users"] == 3
    assert report["unique_documents"] == 3
    assert len(report["top_users"]) > 0
    assert len(report["top_documents"]) > 0
    assert len(report["denied_attempts"]) == 1


def test_compliance_report_top_users(audit_logger):
    """Test top users in compliance report"""
    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(hours=1)

    # user_1 accesses 3 docs, user_2 accesses 1 doc
    for i in range(3):
        audit_logger.log_access_allowed(
            user_id="user_1",
            user_role="user",
            document_id=f"doc_{i}",
            document_tags=[],
        )

    audit_logger.log_access_allowed(
        user_id="user_2", user_role="user", document_id="doc_x", document_tags=[]
    )

    report = audit_logger.generate_compliance_report(start_time, end_time)

    # user_1 should be top user
    assert report["top_users"][0]["user_id"] == "user_1"
    assert report["top_users"][0]["count"] == 3


def test_compliance_report_top_documents(audit_logger):
    """Test top documents in compliance report"""
    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(hours=1)

    # doc_popular accessed 3 times, doc_rare accessed 1 time
    for i in range(3):
        audit_logger.log_access_allowed(
            user_id=f"user_{i}",
            user_role="user",
            document_id="doc_popular",
            document_tags=[],
        )

    audit_logger.log_access_allowed(
        user_id="user_x", user_role="user", document_id="doc_rare", document_tags=[]
    )

    report = audit_logger.generate_compliance_report(start_time, end_time)

    # doc_popular should be top document
    assert report["top_documents"][0]["document_id"] == "doc_popular"
    assert report["top_documents"][0]["count"] == 3


def test_query_events_empty_log():
    """Test querying when log file doesn't exist"""
    with tempfile.NamedTemporaryFile(delete=True) as f:
        # File doesn't exist yet
        nonexistent_path = f.name

    logger = AuditLogger(audit_log_path=nonexistent_path)
    events = logger.query_events()

    assert len(events) == 0


def test_audit_event_dataclass():
    """Test AuditEvent dataclass"""
    event = AuditEvent(
        timestamp="2024-01-01T00:00:00Z",
        event_type="access",
        user_id="user_1",
        user_role="user",
        document_id="doc_1",
        document_tags=["public"],
        decision="allow",
        reason="Normal access",
    )

    assert event.timestamp == "2024-01-01T00:00:00Z"
    assert event.user_id == "user_1"
    assert event.document_id == "doc_1"


def test_multiple_events_same_user_document(audit_logger):
    """Test multiple accesses to same document by same user"""
    # Log multiple accesses
    for i in range(3):
        audit_logger.log_access_allowed(
            user_id="user_1",
            user_role="user",
            document_id="doc_1",
            document_tags=["public"],
        )

    # Should have 3 events
    events = audit_logger.query_events(user_id="user_1", document_id="doc_1")
    assert len(events) == 3


def test_statistics_accuracy(audit_logger):
    """Test that statistics are accurately maintained"""
    # Log 5 allowed, 3 denied, 2 audit
    for _ in range(5):
        audit_logger.log_access_allowed(
            user_id="user", user_role="user", document_id="doc", document_tags=[]
        )

    for _ in range(3):
        audit_logger.log_access_denied(
            user_id="user",
            user_role="guest",
            document_id="doc",
            document_tags=[],
            reason="Denied",
        )

    for _ in range(2):
        audit_logger.log_audit_access(
            user_id="user",
            user_role="admin",
            document_id="doc",
            document_tags=["pii"],
            reason="Audit",
        )

    stats = audit_logger.get_statistics()

    assert stats["total_events"] == 10
    assert stats["access_allowed"] == 5
    assert stats["access_denied"] == 3
    assert stats["audit_events"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
