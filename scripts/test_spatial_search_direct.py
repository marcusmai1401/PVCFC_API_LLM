"""Test spatial search with parsed tag components"""
import sys

sys.path.insert(0, "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC")

from app.rag.spatial.spatial_searcher import SpatialTagSearcher

# Initialize searcher
print("Initializing spatial searcher...")
print("Using clustering threshold: 100mm (increased from 25mm)")
searcher = SpatialTagSearcher(
    max_distance_mm=100.0, alignment_tolerance_mm=5.0, min_cluster_score=0.6
)

# Test cases with VERIFIED tags from actual P&ID document
# Ground truth from: D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf
TEST_CASES = [
    {
        "name": "Test 1: 04-TT-2097",
        "tag": "04-TT-2097",
        "unit": "04",
        "prefix": "TT",
        "suffix": "2097",
        "expected_page": 21,
        "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
    },
    {
        "name": "Test 2: 04-TT-2095",
        "tag": "04-TT-2095",
        "unit": "04",
        "prefix": "TT",
        "suffix": "2095",
        "expected_page": 20,
        "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
    },
    {
        "name": "Test 3: 04-FIC-5041",
        "tag": "04-FIC-5041",
        "unit": "04",
        "prefix": "FIC",
        "suffix": "5041",
        "expected_page": 65,
        "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
    },
    {
        "name": "Test 4: 04-HV-5501",
        "tag": "04-HV-5501",
        "unit": "04",
        "prefix": "HV",
        "suffix": "5501",
        "expected_page": 55,
        "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
    },
]

print("=" * 70)
print("TESTING SPATIAL SEARCH WITH PARSED COMPONENTS")
print("=" * 70)

results = {"total": len(TEST_CASES), "passed": 0, "failed": 0, "details": []}

for test in TEST_CASES:
    print("\n" + "=" * 70)
    print(test["name"])
    print("=" * 70)
    print(f"Tag: {test['tag']}")
    print(
        f"Components: unit={test['unit']}, prefix={test['prefix']}, suffix={test['suffix']}"
    )
    print(f"Expected page: {test['expected_page']}")

    # Search using spatial searcher
    try:
        search_results = searcher.search(
            unit=test["unit"],
            prefix=test["prefix"],
            suffix=test["suffix"],
            doc_id=test["doc_id"],
        )

        if not search_results:
            print("\n❌ FAILED: No results from spatial search")
            results["failed"] += 1
            results["details"].append(
                {
                    "test": test["name"],
                    "status": "FAILED",
                    "reason": "No results",
                    "expected_page": test["expected_page"],
                    "actual_page": None,
                }
            )
            continue

        print(f"\nFound {len(search_results)} result(s)")

        # Display top 5 results
        print("\nTop 5 results:")
        for i, result in enumerate(search_results[:5], 1):
            tag_text = result.metadata.get("tag_text", "N/A")
            print(
                f"  {i}. page={result.page}, score={result.score:.4f}, tag={tag_text}"
            )
            print(f"     bbox={result.bbox}")

        # Check top result
        top_result = search_results[0]
        actual_page = top_result.page

        if actual_page == test["expected_page"]:
            print(f"\n✅ PASSED: Page matches (page={actual_page})")
            results["passed"] += 1
            results["details"].append(
                {
                    "test": test["name"],
                    "status": "PASSED",
                    "expected_page": test["expected_page"],
                    "actual_page": actual_page,
                    "score": top_result.score,
                    "tag_text": top_result.metadata.get("tag_text"),
                }
            )
        else:
            print(
                f"\n❌ FAILED: Page mismatch (expected={test['expected_page']}, got={actual_page})"
            )
            results["failed"] += 1
            results["details"].append(
                {
                    "test": test["name"],
                    "status": "FAILED",
                    "reason": "Page mismatch",
                    "expected_page": test["expected_page"],
                    "actual_page": actual_page,
                    "score": top_result.score,
                    "tag_text": top_result.metadata.get("tag_text"),
                }
            )

    except Exception as e:
        print(f"\n❌ FAILED: Error - {e}")
        results["failed"] += 1
        results["details"].append(
            {
                "test": test["name"],
                "status": "FAILED",
                "reason": f"Error: {str(e)}",
                "expected_page": test["expected_page"],
                "actual_page": None,
            }
        )

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total tests: {results['total']}")
print(f"Passed: {results['passed']} ✅")
print(f"Failed: {results['failed']} ❌")
print(f"Success rate: {100 * results['passed'] / results['total']:.1f}%")

# Detailed results
print("\n" + "=" * 70)
print("DETAILED RESULTS")
print("=" * 70)
for detail in results["details"]:
    status_icon = "✅" if detail["status"] == "PASSED" else "❌"
    print(f"{status_icon} {detail['test']}")
    print(f"   Expected: page {detail['expected_page']}")
    print(f"   Actual: page {detail.get('actual_page', 'N/A')}")
    if detail.get("tag_text"):
        print(f"   Tag text: {detail['tag_text']}")
    if detail["status"] == "FAILED":
        print(f"   Reason: {detail.get('reason', 'Unknown')}")
    print()

# Save results
import json

output_file = "artifacts/spatial_search_test_results.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"Results saved to: {output_file}")

if results["passed"] == results["total"]:
    print("\n🎉 ALL TESTS PASSED - SPATIAL SEARCH WORKING!")
    exit(0)
else:
    print(f"\n⚠️  {results['failed']} TEST(S) FAILED!")

    # Troubleshooting hints
    print("\n" + "=" * 70)
    print("TROUBLESHOOTING")
    print("=" * 70)
    print("If all tests failed with 'No results':")
    print("  1. Check if spatial index has components for these tags")
    print("  2. Verify doc_id matches (currently using 'Ammonia')")
    print("  3. Try different unit numbers (e.g., '04', '05', etc.)")
    print("\nTo check available components:")
    print(
        "  python -c \"from app.rag.spatial.component_indexer import SpatialComponentIndexer; idx = SpatialComponentIndexer(); print(idx.search_components(component_text='FIC', component_type='prefix', size=10))\""
    )

    exit(1)
