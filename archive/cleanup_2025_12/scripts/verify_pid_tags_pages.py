"""Verify expected pages for P&ID tags in spatial index"""
import requests

# Test cases with expected pages
TEST_TAGS = [
    {"tag": "FIC-310", "expected_page": 9},
    {"tag": "PIC-560", "expected_page": 14},
    {"tag": "TIC-460", "expected_page": 10},
    {"tag": "LIC-520", "expected_page": 12},
]

print("=" * 70)
print("VERIFYING P&ID TAGS IN SPATIAL INDEX")
print("=" * 70)

for test in TEST_TAGS:
    print("\n" + "=" * 70)
    print(f"Tag: {test['tag']}")
    print("=" * 70)
    print(f"Expected page: {test['expected_page']}")

    # Search spatial index for exact tag
    query = {
        "size": 20,
        "_source": ["doc_id", "page", "tag", "bbox", "normalized_tag"],
        "query": {
            "bool": {
                "should": [
                    # Exact match on original tag
                    {"term": {"tag.keyword": test["tag"]}},
                    # Exact match on normalized
                    {"term": {"normalized_tag": test["tag"].lower()}},
                    # Partial match
                    {"match": {"tag": test["tag"]}},
                ],
                "minimum_should_match": 1,
            }
        },
    }

    response = requests.post(
        "http://localhost:9200/pvcfc_pid_spatial_components/_search",
        json=query,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        continue

    data = response.json()
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        print("❌ No matches found in spatial index")
        continue

    print(f"\nFound {len(hits)} matches:")

    # Group by page
    pages = {}
    for hit in hits:
        source = hit["_source"]
        page = source.get("page")
        tag = source.get("tag")

        if page not in pages:
            pages[page] = []
        pages[page].append(
            {
                "tag": tag,
                "doc_id": source.get("doc_id", "")[:60],
                "bbox": source.get("bbox"),
                "score": hit["_score"],
            }
        )

    # Display results
    for page in sorted(pages.keys()):
        matches = pages[page]
        icon = "✅" if page == test["expected_page"] else "  "
        print(f"\n{icon} Page {page}: {len(matches)} match(es)")
        for match in matches[:3]:  # Show max 3 per page
            print(f"     - {match['tag']} (score={match['score']:.2f})")
            print(f"       doc_id: ...{match['doc_id'][-40:]}")

    # Check if expected page exists
    if test["expected_page"] in pages:
        print(f"\n✅ Expected page {test['expected_page']} FOUND")
    else:
        print(f"\n❌ Expected page {test['expected_page']} NOT FOUND")
        print(f"   Available pages: {sorted(pages.keys())}")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
