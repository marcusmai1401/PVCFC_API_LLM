# Week 2 Quick Start Guide

## 🚀 What's New in Week 2?

Week 2 adds **resilience, observability, and security** to PVCFC RAG API:

1. **Circuit Breakers** - Prevent cascading failures
2. **Health Checks** - Kubernetes-ready monitoring
3. **Document Security** - Access control and audit logging

## ⚡ Quick Setup

### 1. Install Dependencies

```bash
pip install pybreaker==1.0.1
```

### 2. Create Configuration (Optional)

```bash
# Create directories
mkdir -p config logs

# Create document validator config (optional)
cat > config/document_validator.json << 'EOF'
{
  "whitelist": [],
  "blacklist": [],
  "sensitive_tags": ["confidential", "pii"],
  "tag_rules": {
    "public": {"guest": "allow", "user": "allow", "admin": "allow"},
    "internal": {"guest": "deny", "user": "allow", "admin": "allow"},
    "confidential": {"guest": "deny", "user": "audit", "admin": "allow"},
    "pii": {"guest": "deny", "user": "deny", "admin": "audit"}
  }
}
EOF
```

### 3. Update Environment (Optional)

Add to `.env`:
```bash
DOCUMENT_VALIDATOR_CONFIG=config/document_validator.json
AUDIT_LOG_PATH=logs/audit.jsonl
```

## 🏥 Health Checks

### Check System Health

```bash
# Basic health check
curl http://localhost:8000/healthz | jq

# Kubernetes liveness probe
curl http://localhost:8000/livez | jq

# Kubernetes readiness probe (detailed)
curl http://localhost:8000/readyz | jq
```

### Example Response

```json
{
  "status": "healthy",
  "type": "readiness",
  "check_duration_ms": 145.32,
  "components": [
    {
      "name": "weaviate",
      "status": "healthy",
      "message": "Connected and ready",
      "latency_ms": 12.5
    },
    {
      "name": "opensearch",
      "status": "healthy",
      "message": "Connected and ready",
      "latency_ms": 23.8
    },
    {
      "name": "redis",
      "status": "healthy",
      "message": "Connected and ready",
      "latency_ms": 5.2
    },
    {
      "name": "filesystem",
      "status": "healthy",
      "message": "All critical paths exist",
      "latency_ms": 1.1
    }
  ]
}
```

## 🔒 Document Security

### Basic Usage

```python
from app.security import get_document_validator
from app.security.audit_logger import get_audit_logger

# Get validator
validator = get_document_validator()

# Validate document access
result = validator.validate_document_access(
    document_id="doc_123",
    user_id="user_456",
    user_role="user",
    document_tags=["confidential"]
)

if result.allowed:
    print("✅ Access granted")
    if result.should_audit:
        print("⚠️ Access logged for audit")
else:
    print(f"❌ Access denied: {result.reason}")
```

### Filter Search Results

```python
# After retrieval, filter based on permissions
results = retriever.search(query)
filtered = validator.filter_results(
    results=results,
    user_id="user_456",
    user_role="user"
)
```

### Audit Logging

```python
# Get audit logger
audit_logger = get_audit_logger()

# Log access
audit_logger.log_access_allowed(
    user_id="user_456",
    user_role="user",
    document_id="doc_123",
    document_tags=["confidential"],
    ip_address="192.168.1.1"
)

# Query user activity
activity = audit_logger.get_user_activity("user_456", limit=50)

# Generate compliance report
from datetime import datetime, timedelta

end = datetime.utcnow()
start = end - timedelta(days=30)
report = audit_logger.generate_compliance_report(start, end)

print(f"Total events: {report['total_events']}")
print(f"Denied attempts: {report['access_denied']}")
```

## 🔧 Circuit Breakers

Circuit breakers are **automatic** - no manual configuration needed!

They protect:
- Weaviate searches
- OpenSearch queries
- Redis operations
- Gemini LLM calls

### How They Work

```
CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED (recovered)
```

When a service fails:
1. Circuit opens after threshold (e.g., 5 failures)
2. Requests fail fast (no waiting)
3. Circuit tests recovery after timeout
4. Auto-closes when service is healthy

### Example Behavior

```python
# Normal operation
results = weaviate_retriever.search(query)  # Works normally

# Service down
results = weaviate_retriever.search(query)  # Returns [] immediately
# ⚠️ Circuit OPEN - skipping Weaviate

# Service recovered
results = weaviate_retriever.search(query)  # Works again
# ✅ Circuit CLOSED - Weaviate healthy
```

## 📊 Access Control Rules

| Document Tag | Guest | User | Admin |
|--------------|-------|------|-------|
| public       | ✓ Allow | ✓ Allow | ✓ Allow |
| internal     | ✗ Deny | ✓ Allow | ✓ Allow |
| confidential | ✗ Deny | 🔍 Audit | ✓ Allow |
| pii          | ✗ Deny | ✗ Deny | 🔍 Audit |

**Legend:**
- ✓ = Access granted
- ✗ = Access denied
- 🔍 = Access granted but logged for compliance

## 🎯 Common Tasks

### Manage Blacklist

```python
validator = get_document_validator()

# Block sensitive documents
validator.add_to_blacklist(["doc_secret_1", "doc_secret_2"])

# Unblock documents
validator.remove_from_blacklist(["doc_secret_1"])
```

### Manage Whitelist

```python
# Always allow specific documents
validator.add_to_whitelist(["doc_public_1", "doc_public_2"])

# Remove from whitelist
validator.remove_from_whitelist(["doc_public_1"])
```

### Check Statistics

```python
# Validator stats
stats = validator.get_statistics()
print(f"Blacklisted: {stats['blacklist_count']}")
print(f"Whitelisted: {stats['whitelist_count']}")

# Audit stats
audit_stats = audit_logger.get_statistics()
print(f"Total events: {audit_stats['total_events']}")
print(f"Access denied: {audit_stats['access_denied']}")
```

### Query Audit Logs

```python
# Get denied access attempts
denied = audit_logger.get_denied_attempts(limit=100)

for event in denied:
    print(f"{event.timestamp}: User {event.user_id} denied access to {event.document_id}")

# Get document access history
history = audit_logger.get_document_access_history("doc_sensitive", limit=50)
```

## 🐛 Troubleshooting

### Health Check Shows Component Unhealthy

```bash
# Check detailed status
curl http://localhost:8000/readyz | jq '.components[] | select(.status != "healthy")'
```

**Common Issues:**
- **Weaviate unhealthy**: Check if Weaviate is running (`docker ps`)
- **OpenSearch unhealthy**: Verify OpenSearch connection in config
- **Redis unhealthy**: Check Redis connection string
- **Filesystem degraded**: Ensure index directories exist

### Circuit Breaker Stuck Open

Circuit breakers auto-recover, but if stuck:

1. Check service health directly
2. Wait for reset timeout (30-60s)
3. Restart affected service

### Audit Log Not Writing

```bash
# Check log path exists
ls -lh logs/audit.jsonl

# Check permissions
chmod 644 logs/audit.jsonl

# Verify directory writable
touch logs/test.log && rm logs/test.log
```

## 📚 More Information

- **Full Documentation**: See `docs/week2_complete_summary.md`
- **Health Checks**: See `docs/health_checks.md`
- **Deployment**: See `docs/WEEK2_REVIEW_CHECKLIST.md`
- **Handoff**: See `docs/WEEK2_HANDOFF.md`

## ✅ Verification

Quick verification that Week 2 is working:

```bash
# 1. Health check responds
curl http://localhost:8000/readyz

# 2. Circuit breakers loaded
python -c "from app.core.circuit_breaker import weaviate_breaker; print('✅ Circuit breakers OK')"

# 3. Document validator works
python -c "from app.security import get_document_validator; v = get_document_validator(); print('✅ Document validator OK')"

# 4. Audit logger works
python -c "from app.security.audit_logger import get_audit_logger; a = get_audit_logger(); print('✅ Audit logger OK')"
```

All commands should succeed ✅

---

**Questions?** Check the full documentation or open an issue.
