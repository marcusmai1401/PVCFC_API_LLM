"""
Test 7 Ground Truth Queries - Spatial Search Only
Based on test_pid.md ground truth
"""
import re
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.rag.spatial.spatial_searcher import SpatialTagSearcher

# Ground truth from test_pid.md
GROUND_TRUTH = [
    {"query": "04 PSV 3926", "expected_page": 41},
    {"query": "04 TI 5058", "expected_page": 58},
    {"query": "04 TXI 2077", "expected_page": 17},
    {"query": "04 ZI 4502", "expected_page": 100},
    {"query": "04 ZLH 2028A", "expected_page": 9},  # Optional
    {"query": "04 I 209", "expected_page": 14},
    {"query": "04 PSAH 2552", "expected_page": 20},
]


def parse_tag(tag_str):
    """Parse tag into unit, prefix, suffix"""
    # Match: unit (1-2 digits) + prefix (2-6 letters) + suffix (3-5 digits + optional letter)
    match = re.match(r"^(\d{1,2})\s+([A-Z]{1,6})\s+(\d{3,5}[A-Z]?)$", tag_str.upper())

    if match:
        return {
            "unit": match.group(1),
            "prefix": match.group(2),
            "suffix": match.group(3),
        }
    return None


print("=" * 80)
print("TEST: 7 Ground Truth Queries - Spatial Search")
print("=" * 80)

searcher = SpatialTagSearcher(
    max_distance_mm=25.0, alignment_tolerance_mm=5.0, min_cluster_score=0.6
)

passed = 0
failed = 0
results_detail = []

for i, test_case in enumerate(GROUND_TRUTH, 1):
    query = test_case["query"]
    expected_page = test_case["expected_page"]

    print(f"\n{'='*80}")
    print(f"Query {i}: {query}")
    print(f"Expected: Page {expected_page}")
    print("-" * 80)

    # Parse tag
    components = parse_tag(query)
    if not components:
        print(f"✗ ERROR: Failed to parse tag '{query}'")
        failed += 1
        continue

    print(
        f"  Components: unit={components['unit']}, prefix={components['prefix']}, suffix={components['suffix']}"
    )

    # Search
    try:
        results = searcher.search(
            unit=components["unit"],
            prefix=components["prefix"],
            suffix=components["suffix"],
        )

        if not results:
            print(f"✗ FAILED: No results found")
            failed += 1
            results_detail.append(
                {
                    "query": query,
                    "expected": expected_page,
                    "found": None,
                    "status": "NO_RESULTS",
                }
            )
            continue

        # Get top result
        top_result = results[0]
        found_page = top_result.page
        score = top_result.score

        print(f"  Found: Page {found_page} (score: {score:.3f})")

        # Check if correct
        if found_page == expected_page:
            print(f"✓ PASSED!")
            passed += 1
            results_detail.append(
                {
                    "query": query,
                    "expected": expected_page,
                    "found": found_page,
                    "score": score,
                    "status": "PASS",
                }
            )
        else:
            print(f"✗ FAILED: Wrong page (expected {expected_page}, got {found_page})")
            failed += 1
            results_detail.append(
                {
                    "query": query,
                    "expected": expected_page,
                    "found": found_page,
                    "score": score,
                    "status": "WRONG_PAGE",
                }
            )

        # Show top 3 results
        if len(results) > 1:
            print(f"  Top 3 results:")
            for j, r in enumerate(results[:3], 1):
                marker = "✓" if r.page == expected_page else " "
                print(f"    {marker} {j}. Page {r.page} (score: {r.score:.3f})")

    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        failed += 1
        results_detail.append(
            {
                "query": query,
                "expected": expected_page,
                "found": None,
                "status": "ERROR",
                "error": str(e),
            }
        )

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total: {len(GROUND_TRUTH)} queries")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Accuracy: {passed/len(GROUND_TRUTH)*100:.1f}%")

print("\nDetailed Results:")
for i, detail in enumerate(results_detail, 1):
    status_icon = "✓" if detail["status"] == "PASS" else "✗"
    print(f"  {status_icon} {i}. {detail['query']}: {detail['status']}")
    if detail["status"] == "PASS":
        print(
            f"      Expected {detail['expected']} → Found {detail['found']} (score: {detail.get('score', 0):.3f})"
        )
    elif detail["status"] == "WRONG_PAGE":
        print(
            f"      Expected {detail['expected']} → Found {detail['found']} (score: {detail.get('score', 0):.3f})"
        )
    elif detail["status"] == "NO_RESULTS":
        print(f"      Expected {detail['expected']} → No results")

print("\n" + "=" * 80)

# Target: 4/5 required queries (queries 1-4), optional query 5
required_passed = sum(1 for d in results_detail[:4] if d["status"] == "PASS")
print(f"Required queries (1-4): {required_passed}/4 passed")

if required_passed >= 4:
    print("✓ TARGET MET: At least 4/4 required queries passed!")
    sys.exit(0)
else:
    print(f"✗ TARGET NOT MET: Only {required_passed}/4 required queries passed")
    sys.exit(1)
