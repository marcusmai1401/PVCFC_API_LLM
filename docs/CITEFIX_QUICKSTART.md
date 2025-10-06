# CiteFix-lite Quick Start Guide

**Last Updated**: 2025-01-03
**Status**: Production Ready ✅

---

## 🎯 What is CiteFix-lite?

CiteFix-lite is a lightweight citation validation system that prevents hallucinations in RAG responses by validating:
- ✅ Document ID exists in corpus
- ✅ Page number is valid
- ✅ Text actually exists on the cited page
- ✅ Snippets match page content

**Key Benefits:**
- Catches hallucinated citations before they reach users
- Provides confidence scores for each citation
- Suggests alternative pages when citations are wrong
- Optional filtering of invalid citations

---

## 🚀 Quick Start (5 minutes)

### 1. Enable Validation

```python
from app.rag.citation_retriever import CitationRetriever, SearchConfig

# Create config with validation enabled
config = SearchConfig(
    enable_validation=True,           # Enable validation
    validation_level=2,                # Level 2: text verification
    min_confidence_threshold=0.7,      # 70% confidence required
    filter_invalid_citations=False,    # Keep all, just flag issues
)

# Create retriever
retriever = CitationRetriever(config=config)
```

### 2. Run Search with Validation

```python
# Search as usual
results = retriever.search_with_citations(
    query="What is the operating pressure?",
    doc_ids=["doc1", "doc2", "doc3"],
)

# Check validation results
for citation in results:
    validation = citation.metadata.get('validation')

    if validation:
        is_valid = validation['is_valid']
        confidence = validation['confidence']

        print(f"Citation: {citation.doc_id}, Page {citation.page}")
        print(f"  Valid: {is_valid}, Confidence: {confidence:.2%}")

        # Show errors if any
        if validation['errors']:
            for error in validation['errors']:
                print(f"  ⚠️  {error['message']}")

        # Check for suggested alternatives
        if 'suggested_page' in validation['metadata']:
            print(f"  💡 Try page {validation['metadata']['suggested_page']} instead")
```

### 3. Check Results

```python
# Example output:
Citation: doc1, Page 5
  Valid: True, Confidence: 95.20%

Citation: doc2, Page 12
  Valid: False, Confidence: 45.30%
  ⚠️  Cited page text does not match actual page content (confidence: 45%)
  💡 Try page 13 instead
```

---

## ⚙️ Configuration Options

### Validation Levels

```python
# Level 1: Basic validation only (fastest, ~1-5ms)
config = SearchConfig(
    enable_validation=True,
    validation_level=1,  # Doc ID + page number only
)

# Level 2: Full text validation (recommended, ~10-30ms)
config = SearchConfig(
    enable_validation=True,
    validation_level=2,  # Doc ID + page + text + snippets
)

# Level 3: Semantic validation (future, ~100-500ms)
config = SearchConfig(
    enable_validation=True,
    validation_level=3,  # Full validation + NLI/entailment
)
```

### Confidence Thresholds

```python
# Strict: High confidence required
config = SearchConfig(
    enable_validation=True,
    min_confidence_threshold=0.9,  # 90% confidence
    filter_invalid_citations=True,  # Remove invalid citations
)

# Balanced: Default settings
config = SearchConfig(
    enable_validation=True,
    min_confidence_threshold=0.7,  # 70% confidence
    filter_invalid_citations=False,  # Keep all, just flag
)

# Permissive: Low threshold
config = SearchConfig(
    enable_validation=True,
    min_confidence_threshold=0.5,  # 50% confidence
    filter_invalid_citations=False,
)
```

### Feature Flags

```python
# Development: Full validation with filtering
dev_config = SearchConfig(
    enable_validation=True,
    validation_level=2,
    filter_invalid_citations=True,
)

# Production: Validation off initially
prod_config = SearchConfig(
    enable_validation=False,  # Start disabled
)

# Staging: Test with warnings only
staging_config = SearchConfig(
    enable_validation=True,
    filter_invalid_citations=False,  # Flag but don't filter
)
```

---

## 📊 Understanding Validation Results

### Validation Result Structure

```python
validation = {
    "is_valid": True,           # Overall status
    "confidence": 0.85,          # 0.0 to 1.0

    "errors": [                  # List of validation errors
        {
            "type": "text_not_found",
            "message": "Cited text does not match page",
            "severity": "warning",  # critical | warning | info
            "details": {"page_text_confidence": 0.45}
        }
    ],

    "checks": {                  # Individual check results
        "doc_exists": True,
        "page_valid": True,
        "page_text_valid": True,
        "page_text_confidence": 0.95,
        "snippets_valid": True,
        "snippet_coverage": 0.87,
        "neighbor_page_found": 13,     # Optional: better page found
        "neighbor_confidence": 0.92
    },

    "metadata": {                # Additional info
        "validation_level": 2,
        "doc_id": "doc1",
        "page": 12,
        "snippet_count": 3,
        "suggested_page": 13       # Optional: suggested alternative
    }
}
```

### Common Error Types

| Error Type | Severity | Meaning |
|------------|----------|---------|
| `doc_not_found` | CRITICAL | Document doesn't exist in corpus |
| `invalid_page_number` | CRITICAL | Page number out of range |
| `text_not_found` | WARNING | Cited text doesn't match page |
| `snippet_mismatch` | WARNING | Snippets not found on page |
| `low_confidence` | WARNING | Overall confidence below threshold |

---

## 🎛️ Advanced Usage

### Standalone Validator

```python
from app.rag.citation_validator import get_citation_validator
from app.rag.snippet_extractor import Snippet

# Get validator instance
validator = get_citation_validator(
    validation_level=2,
    min_confidence_threshold=0.7,
)

# Validate manually
result = validator.validate(
    doc_id="doc1",
    page=5,
    page_text="The operating pressure is 150 PSI...",
    snippets=[
        Snippet(
            text="operating pressure",
            start_pos=0,
            end_pos=18,
            matched_keywords={"operating", "pressure"},
        ),
    ],
    query="operating pressure",
)

# Process result
if not result.is_valid:
    print(f"Invalid citation! Confidence: {result.confidence:.2%}")
    for error in result.errors:
        print(f"  - {error.message}")
```

### Batch Validation

```python
# Validate multiple citations at once
citations = [
    {"doc_id": "doc1", "page": 5, "page_text": "..."},
    {"doc_id": "doc2", "page": 12, "page_text": "..."},
    {"doc_id": "doc3", "page": 8, "page_text": "..."},
]

validator = get_citation_validator()
results = []

for citation in citations:
    result = validator.validate(**citation)
    results.append({
        "citation": citation,
        "validation": result.to_dict(),
    })

# Filter valid citations
valid_citations = [
    r for r in results
    if r['validation']['is_valid']
]

print(f"Valid: {len(valid_citations)}/{len(citations)}")
```

### Custom Confidence Calculation

```python
# Access individual checks for custom logic
result = validator.validate(...)

if result.checks.get('page_text_confidence', 0) > 0.9:
    print("High confidence text match!")

if result.checks.get('snippet_coverage', 0) == 1.0:
    print("All snippets found!")

if 'neighbor_page_found' in result.checks:
    better_page = result.checks['neighbor_page_found']
    print(f"Better match on page {better_page}")
```

---

## 🐛 Troubleshooting

### Issue: All citations marked invalid

**Possible causes:**
1. `doc_id_map.json` not found or empty
2. Page index not built
3. Threshold too high

**Solutions:**
```python
# Check doc_id_map exists
from pathlib import Path
doc_map_path = Path("artifacts/ingestion_production/doc_id_map.json")
print(f"Doc map exists: {doc_map_path.exists()}")

# Lower threshold temporarily
config = SearchConfig(
    enable_validation=True,
    min_confidence_threshold=0.5,  # Lower threshold
)

# Use Level 1 only (basic checks)
config = SearchConfig(
    enable_validation=True,
    validation_level=1,  # Skip text validation
)
```

### Issue: Performance too slow

**Solutions:**
```python
# Use Level 1 validation only
config = SearchConfig(
    validation_level=1,  # ~1-5ms instead of ~10-30ms
)

# Disable validation for specific queries
if query_requires_speed:
    config.enable_validation = False

# Reduce top_k to validate fewer citations
config = SearchConfig(
    max_total_citations=5,  # Validate fewer citations
)
```

### Issue: False positives (valid citations marked invalid)

**Solutions:**
```python
# Lower text match threshold
validator = CitationValidator(
    text_match_threshold=0.3,  # Default: 0.5
)

# Lower overall confidence threshold
config = SearchConfig(
    min_confidence_threshold=0.6,  # Default: 0.7
)

# Check neighbor scanning is enabled
validator = CitationValidator(
    neighbor_scan_range=3,  # Check ±3 pages instead of ±2
)
```

---

## 📈 Performance Tuning

### Recommended Settings by Use Case

#### Development/Testing
```python
config = SearchConfig(
    enable_validation=True,
    validation_level=2,
    min_confidence_threshold=0.6,  # Lower threshold
    filter_invalid_citations=False,  # Don't filter, just warn
)
```

#### Production (Accuracy Priority)
```python
config = SearchConfig(
    enable_validation=True,
    validation_level=2,
    min_confidence_threshold=0.8,  # High confidence
    filter_invalid_citations=True,  # Remove invalid citations
)
```

#### Production (Speed Priority)
```python
config = SearchConfig(
    enable_validation=True,
    validation_level=1,  # Basic checks only
    min_confidence_threshold=0.7,
    filter_invalid_citations=False,
)
```

#### Interactive/Real-time
```python
config = SearchConfig(
    enable_validation=False,  # Disable for speed
)
```

---

## 🔍 Monitoring & Metrics

### Track Validation Results

```python
# Collect validation stats
stats = {
    "total": 0,
    "valid": 0,
    "invalid": 0,
    "filtered": 0,
    "confidence_scores": [],
}

for citation in results:
    stats["total"] += 1
    validation = citation.metadata.get('validation')

    if validation:
        stats["confidence_scores"].append(validation['confidence'])

        if validation['is_valid']:
            stats["valid"] += 1
        else:
            stats["invalid"] += 1

# Calculate metrics
import statistics
print(f"Total citations: {stats['total']}")
print(f"Valid: {stats['valid']} ({stats['valid']/stats['total']:.1%})")
print(f"Invalid: {stats['invalid']} ({stats['invalid']/stats['total']:.1%})")
print(f"Avg confidence: {statistics.mean(stats['confidence_scores']):.2%}")
print(f"Min confidence: {min(stats['confidence_scores']):.2%}")
```

### Recommended Prometheus Metrics

```python
from prometheus_client import Histogram, Counter

# Add to app/core/metrics.py
citation_validation_confidence = Histogram(
    "rag_citation_validation_confidence",
    "Confidence scores from citation validation",
    buckets=(0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0)
)

citation_validation_errors = Counter(
    "rag_citation_validation_errors",
    "Count of validation errors by type",
    ["error_type", "severity"]
)

# Use in code
for citation in results:
    validation = citation.metadata.get('validation')
    if validation:
        citation_validation_confidence.observe(validation['confidence'])

        for error in validation['errors']:
            citation_validation_errors.labels(
                error_type=error['type'],
                severity=error['severity']
            ).inc()
```

---

## 📚 Additional Resources

- **Design Document**: `Build_plan_README/designs/CITEFIX_LITE_DESIGN.md`
- **Implementation Report**: `Build_plan_README/completed/CITEFIX_LITE_IMPLEMENTATION_REPORT.md`
- **Test Suite**: `tests/test_citation_validator.py`
- **Source Code**: `app/rag/citation_validator.py`

---

## 💡 Tips & Best Practices

1. **Start with validation disabled** in production, enable gradually
2. **Monitor confidence distributions** to tune thresholds
3. **Use Level 1 validation** for latency-critical paths
4. **Enable filtering** only after validating accuracy on your data
5. **Check suggested_page** in metadata for auto-correction opportunities
6. **Log validation results** to track hallucination rates over time

---

## ✅ Next Steps

1. **Try the examples** above in your development environment
2. **Run tests** to verify setup: `pytest tests/test_citation_validator.py -v`
3. **Enable validation** in dev/staging with `filter_invalid_citations=False`
4. **Monitor metrics** and tune thresholds based on your data
5. **Gradually enable** in production with low threshold initially
6. **Collect feedback** and adjust confidence thresholds

---

**Questions or issues?** Check the troubleshooting section or review the implementation report for technical details.

**Status**: Production Ready ✅ | **Version**: 1.0 | **Last Updated**: 2025-01-03
