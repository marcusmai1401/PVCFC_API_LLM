"""
Verification Helper - Sanity check ground truth data
Verifies all 5 test tags exist in pvcfc_pid_tags index before running accuracy tests
"""
import sys

sys.path.insert(0, ".")

from opensearchpy import OpenSearch

# Ground truth test cases
GROUND_TRUTH = [
    {"query_id": 1, "tag": "04 PSV 3926", "expected_page": 41, "required": True},
    {"query_id": 2, "tag": "04 TI 5058", "expected_page": 58, "required": True},
    {"query_id": 3, "tag": "04 TXI 2077", "expected_page": 17, "required": True},
    {"query_id": 4, "tag": "04 ZI 4502", "expected_page": 100, "required": True},
    {"query_id": 5, "tag": "06 FIC 1134", "expected_page": 103, "required": False},
]

DOC_PATTERN = "Ammonia"
INDEX_NAME = "pvcfc_pid_tags"


def verify_all_tags():
    """Verify all ground truth tags exist in OpenSearch"""

    print("=" * 80)
    print("VERIFICATION: Ground Truth Tags in OpenSearch")
    print("=" * 80)

    # Connect to OpenSearch
    try:
        client = OpenSearch(
            hosts=[{"host": "localhost", "port": 9200}], http_compress=True, timeout=10
        )

        # Check index exists
        if not client.indices.exists(index=INDEX_NAME):
            print(f"ERROR: Index '{INDEX_NAME}' does not exist!")
            return False

        print(f"Index '{INDEX_NAME}' exists")

        # Get total count
        count_response = client.count(index=INDEX_NAME)
        total_tags = count_response["count"]
        print(f"Total tags in index: {total_tags}")
        print()

    except Exception as e:
        print(f"ERROR: Cannot connect to OpenSearch - {e}")
        return False

    # Verify each tag
    all_valid = True
    results = []

    for test_case in GROUND_TRUTH:
        query_id = test_case["query_id"]
        tag_text = test_case["tag"]
        expected_page = test_case["expected_page"]
        required = test_case["required"]

        print(f"Query {query_id}: Checking tag '{tag_text}' (page {expected_page})")
        print("-" * 80)

        # Parse tag components
        parts = tag_text.split()
        if len(parts) >= 3:
            unit = parts[0]
            prefix = parts[1]
            suffix = parts[2].rstrip("A-Z")  # Remove variant letter if exists
            variant = parts[2][-1] if parts[2][-1].isalpha() else None
        else:
            print(f"  WARNING: Cannot parse tag '{tag_text}'")
            all_valid = False
            continue

        # Search for tag using nested paths (after fix)
        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"parts.unit.keyword": unit}},
                        {"term": {"parts.prefix.keyword": prefix}},
                        {"term": {"parts.suffix.keyword": suffix}},
                    ]
                }
            },
            "size": 10,
        }

        try:
            response = client.search(index=INDEX_NAME, body=query_body)
            hits = response["hits"]["hits"]

            if not hits:
                status = "NOT FOUND"
                if required:
                    print(f"  Status: {status} - CRITICAL")
                    all_valid = False
                else:
                    print(f"  Status: {status} - Optional (Query 5)")
                results.append(
                    {
                        "query_id": query_id,
                        "tag": tag_text,
                        "found": False,
                        "required": required,
                    }
                )
                continue

            # Check if tag exists on expected page
            found_on_expected_page = False
            found_pages = []

            for hit in hits:
                source = hit["_source"]
                page = source.get("page")
                found_pages.append(page)

                if page == expected_page:
                    found_on_expected_page = True
                    bbox = source.get("bbox")
                    confidence = source.get("confidence")
                    doc_id = source.get("doc_id", "")

                    print(f"  Status: FOUND")
                    print(f"  Page: {page} (matches expected)")
                    print(f"  Doc ID: {doc_id[:60]}...")
                    print(f"  Has Ammonia: {'YES' if DOC_PATTERN in doc_id else 'NO'}")
                    print(f"  Bbox: {bbox[:4] if bbox else 'None'}...")
                    print(f"  Confidence: {confidence:.2f}")
                    break

            if not found_on_expected_page:
                print(f"  Status: FOUND but WRONG PAGE")
                print(f"  Found on pages: {found_pages[:5]}")
                print(f"  Expected page: {expected_page}")
                if required:
                    print(f"  WARNING: Required query has page mismatch")
                    all_valid = False

            results.append(
                {
                    "query_id": query_id,
                    "tag": tag_text,
                    "found": len(hits) > 0,
                    "correct_page": found_on_expected_page,
                    "found_pages": found_pages,
                    "required": required,
                }
            )

        except Exception as e:
            print(f"  ERROR: Search failed - {e}")
            all_valid = False
            results.append(
                {
                    "query_id": query_id,
                    "tag": tag_text,
                    "found": False,
                    "error": str(e),
                    "required": required,
                }
            )

        print()

    # Summary
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    found_count = sum(1 for r in results if r.get("found"))
    correct_page_count = sum(1 for r in results if r.get("correct_page"))
    required_results = [r for r in results if r["required"]]
    required_correct = sum(1 for r in required_results if r.get("correct_page"))

    print(f"Tags found: {found_count}/5")
    print(f"Correct page: {correct_page_count}/5")
    print(f"Required queries correct: {required_correct}/4")
    print()

    if all_valid and required_correct == 4:
        print("Status: READY TO TEST")
        print("All required tags exist on expected pages.")
        return True
    else:
        print("Status: GROUND TRUTH ISSUES DETECTED")
        print("Please verify:")
        print("  1. Tags were extracted correctly")
        print("  2. Page numbers in test_pid.md are accurate")
        print("  3. Index was populated with correct data")
        return False


if __name__ == "__main__":
    success = verify_all_tags()
    sys.exit(0 if success else 1)
