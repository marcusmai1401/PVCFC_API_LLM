"""
Validate ingestion output before indexing to OpenSearch
"""
# Fix Windows console encoding
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file"""
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON decode error at line {line_num}: {e}")
    return records


def validate_ingestion_output(jsonl_path: str) -> Dict[str, Any]:
    """Comprehensive validation of ingestion output"""

    file_path = Path(jsonl_path)
    if not file_path.exists():
        return {"error": f"File not found: {jsonl_path}"}

    print(f"📂 Loading: {file_path}")
    records = load_jsonl(file_path)

    if not records:
        return {"error": "No records found in file"}

    # Initialize validation results
    results = {
        "total_records": len(records),
        "validation_passed": True,
        "issues": [],
        "warnings": [],
        "statistics": {},
    }

    # Required fields for OpenSearch indexing
    required_fields = [
        "doc_id",
        "page",
        "tag",
        "unit",
        "prefix",
        "suffix",
        "bbox",
        "confidence",
        "has_variant",
        "has_annotation",
    ]

    # Track statistics
    doc_ids = set()
    pages = set()
    tags = []
    unique_tags = set()
    confidences = []
    missing_fields = defaultdict(int)
    null_values = defaultdict(int)

    # Validate each record
    for idx, record in enumerate(records, 1):
        # Check required fields
        for field in required_fields:
            if field not in record:
                missing_fields[field] += 1
                results["issues"].append(f"Record {idx}: Missing field '{field}'")
                results["validation_passed"] = False
            elif record[field] is None and field in ["doc_id", "page", "tag", "bbox"]:
                null_values[field] += 1
                results["issues"].append(
                    f"Record {idx}: Null value in critical field '{field}'"
                )
                results["validation_passed"] = False

        # Collect statistics
        if "doc_id" in record and record["doc_id"]:
            doc_ids.add(record["doc_id"])

        if "page" in record and record["page"] is not None:
            pages.add(record["page"])

        if "tag" in record and record["tag"]:
            tag = record["tag"]
            tags.append(tag)
            unique_tags.add(tag)

        if "confidence" in record and record["confidence"] is not None:
            confidences.append(record["confidence"])

        # Validate bbox format
        if "bbox" in record and record["bbox"]:
            bbox = record["bbox"]
            if not isinstance(bbox, list) or len(bbox) != 4:
                results["issues"].append(
                    f"Record {idx}: Invalid bbox format (expected 4-element list)"
                )
                results["validation_passed"] = False

    # Calculate statistics
    if confidences:
        avg_confidence = sum(confidences) / len(confidences)
        min_confidence = min(confidences)
        max_confidence = max(confidences)
        low_confidence_count = sum(1 for c in confidences if c < 0.5)
    else:
        avg_confidence = min_confidence = max_confidence = 0
        low_confidence_count = 0

    # Count duplicates
    tag_counts = Counter(tags)
    duplicates = {tag: count for tag, count in tag_counts.items() if count > 1}

    # Page distribution
    page_distribution = Counter()
    for record in records:
        if "page" in record and record["page"] is not None:
            page_distribution[record["page"]] += 1

    # Populate statistics
    results["statistics"] = {
        "documents": {
            "unique_doc_ids": len(doc_ids),
            "doc_ids_list": sorted(list(doc_ids)),
        },
        "pages": {
            "total_pages": len(pages),
            "page_range": f"{min(pages)} - {max(pages)}" if pages else "N/A",
            "pages_with_most_tags": sorted(
                page_distribution.items(), key=lambda x: x[1], reverse=True
            )[:10],
        },
        "tags": {
            "total_tags": len(tags),
            "unique_tags": len(unique_tags),
            "duplicate_tags": len(duplicates),
            "duplication_rate": f"{len(duplicates) / len(unique_tags) * 100:.2f}%"
            if unique_tags
            else "0%",
        },
        "confidence": {
            "average": f"{avg_confidence:.4f}",
            "min": f"{min_confidence:.4f}",
            "max": f"{max_confidence:.4f}",
            "low_confidence_count": low_confidence_count,
            "low_confidence_percentage": f"{low_confidence_count / len(records) * 100:.2f}%"
            if records
            else "0%",
        },
        "data_quality": {
            "missing_fields": dict(missing_fields),
            "null_values": dict(null_values),
        },
    }

    # Add warnings
    if low_confidence_count > len(records) * 0.1:
        results["warnings"].append(
            f"⚠️  {low_confidence_count} tags ({results['statistics']['confidence']['low_confidence_percentage']}) "
            f"have confidence < 0.5"
        )

    if len(duplicates) > len(unique_tags) * 0.05:
        results["warnings"].append(
            f"⚠️  {len(duplicates)} duplicate tags found (duplication rate: {results['statistics']['tags']['duplication_rate']})"
        )

    if not doc_ids:
        results["issues"].append("❌ No doc_id found in any record")
        results["validation_passed"] = False

    if not pages:
        results["issues"].append("❌ No page information found in any record")
        results["validation_passed"] = False

    return results


def print_validation_report(results: Dict[str, Any]):
    """Print formatted validation report"""

    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return

    print("\n" + "=" * 80)
    print("📊 INGESTION OUTPUT VALIDATION REPORT")
    print("=" * 80)

    # Overall status
    if results["validation_passed"]:
        print("\n✅ VALIDATION PASSED - Ready for indexing!")
    else:
        print("\n❌ VALIDATION FAILED - Issues found that need fixing")

    # Statistics
    stats = results["statistics"]
    print(f"\n📈 STATISTICS:")
    print(f"  Total records: {results['total_records']}")

    if "documents" in stats:
        print(f"\n  Documents:")
        print(f"    Unique doc_ids: {stats['documents']['unique_doc_ids']}")
        print(f"    Doc IDs: {', '.join(stats['documents']['doc_ids_list'])}")

    if "pages" in stats:
        print(f"\n  Pages:")
        print(f"    Total pages: {stats['pages']['total_pages']}")
        print(f"    Page range: {stats['pages']['page_range']}")
        print(f"    Top 5 pages by tag count:")
        for page, count in stats["pages"]["pages_with_most_tags"][:5]:
            print(f"      Page {page}: {count} tags")

    if "tags" in stats:
        print(f"\n  Tags:")
        print(f"    Total tags: {stats['tags']['total_tags']}")
        print(f"    Unique tags: {stats['tags']['unique_tags']}")
        print(f"    Duplicate tags: {stats['tags']['duplicate_tags']}")
        print(f"    Duplication rate: {stats['tags']['duplication_rate']}")

    if "confidence" in stats:
        print(f"\n  Confidence Scores:")
        print(f"    Average: {stats['confidence']['average']}")
        print(f"    Min: {stats['confidence']['min']}")
        print(f"    Max: {stats['confidence']['max']}")
        print(
            f"    Low confidence (<0.5): {stats['confidence']['low_confidence_count']} ({stats['confidence']['low_confidence_percentage']})"
        )

    # Warnings
    if results["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            print(f"  {warning}")

    # Issues
    if results["issues"]:
        print(f"\n❌ CRITICAL ISSUES ({len(results['issues'])}):")
        for issue in results["issues"][:20]:  # Show first 20
            print(f"  {issue}")
        if len(results["issues"]) > 20:
            print(f"  ... and {len(results['issues']) - 20} more issues")

    # Data quality
    if "data_quality" in stats:
        if stats["data_quality"]["missing_fields"]:
            print(f"\n  Missing fields:")
            for field, count in stats["data_quality"]["missing_fields"].items():
                print(f"    {field}: {count} records")

        if stats["data_quality"]["null_values"]:
            print(f"\n  Null values in critical fields:")
            for field, count in stats["data_quality"]["null_values"].items():
                print(f"    {field}: {count} records")

    # Recommendation
    print("\n" + "=" * 80)
    if results["validation_passed"]:
        print("✅ RECOMMENDATION: Proceed with indexing to OpenSearch")
        print("\n📝 Next steps:")
        print("  1. Run: python scripts\\opensearch\\create_tags_index.py")
        print("  2. Run: python scripts\\opensearch\\bulk_upsert_tags.py")
    else:
        print("❌ RECOMMENDATION: Fix issues before indexing")
        print("\n🔧 Suggested fixes:")
        print("  1. Re-run ingestion with correct configuration")
        print("  2. Check PDF processor and tag extraction logic")
        print("  3. Validate input data quality")

    print("=" * 80 + "\n")

    # Return exit code
    return 0 if results["validation_passed"] else 1


if __name__ == "__main__":
    jsonl_path = "output/pid_ingestion/tags.jsonl"

    if len(sys.argv) > 1:
        jsonl_path = sys.argv[1]

    results = validate_ingestion_output(jsonl_path)
    exit_code = print_validation_report(results)
    sys.exit(exit_code)
