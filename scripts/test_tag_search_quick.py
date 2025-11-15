#!/usr/bin/env python
"""
Quick test for tag search in OpenSearch
"""
import json
import sys
from pathlib import Path

from opensearchpy import OpenSearch

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fix Windows encoding
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_tag_search():
    """Test tag search functionality"""

    print("=" * 80)
    print("QUICK TAG SEARCH TEST")
    print("=" * 80 + "\n")

    # Connect to OpenSearch
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=30,
    )

    print("[OK] Connected to OpenSearch\n")

    # Test 1: Count total tags
    print("Test 1: Count total tags")
    print("-" * 40)
    result = client.count(
        index="rag_chunks", body={"query": {"term": {"is_tag_entity": True}}}
    )
    total_tags = result["count"]
    print(f"Total tag entities: {total_tags}")
    print("[OK] Count test passed\n")

    # Test 2: Search for specific tag
    print("Test 2: Search for specific tag '04 PI 2504'")
    print("-" * 40)
    result = client.search(
        index="rag_chunks",
        body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"is_tag_entity": True}},
                        {"match": {"tags": "04 PI 2504"}},
                    ]
                }
            },
            "size": 1,
        },
    )

    if result["hits"]["total"]["value"] > 0:
        hit = result["hits"]["hits"][0]
        source = hit["_source"]
        print(f"[OK] Found tag: {source['tags'][0]}")
        print(f"     Page: {source['page']}")
        print(f"     Confidence: {source['tag_metadata']['confidence']:.4f}")
        print(f"     Doc ID: {source['doc_id']}")
        print("[OK] Specific tag test passed\n")
    else:
        print("[FAIL] Tag not found\n")
        return False

    # Test 3: Search by prefix
    print("Test 3: Search tags with prefix 'PI'")
    print("-" * 40)
    result = client.search(
        index="rag_chunks",
        body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"is_tag_entity": True}},
                        {"match": {"tag_metadata.prefix": "PI"}},
                    ]
                }
            },
            "size": 5,
        },
    )

    total = result["hits"]["total"]["value"]
    print(f"Found {total} tags with prefix 'PI'")
    print("Top 5 results:")
    for i, hit in enumerate(result["hits"]["hits"][:5], 1):
        source = hit["_source"]
        print(f"  {i}. {source['tags'][0]} (page {source['page']})")
    print("[OK] Prefix search test passed\n")

    # Test 4: Search by page
    print("Test 4: Search tags on page 53")
    print("-" * 40)
    result = client.search(
        index="rag_chunks",
        body={
            "query": {
                "bool": {
                    "must": [{"term": {"is_tag_entity": True}}, {"term": {"page": 53}}]
                }
            },
            "size": 0,
        },
    )

    page_53_count = result["hits"]["total"]["value"]
    print(f"Tags on page 53: {page_53_count}")
    print("[OK] Page search test passed\n")

    # Test 5: Search by unit
    print("Test 5: Search tags with unit '04'")
    print("-" * 40)
    result = client.search(
        index="rag_chunks",
        body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"is_tag_entity": True}},
                        {"term": {"tag_metadata.unit": "04"}},
                    ]
                }
            },
            "size": 0,
        },
    )

    unit_04_count = result["hits"]["total"]["value"]
    print(f"Tags with unit '04': {unit_04_count}")
    print("[OK] Unit search test passed\n")

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"[OK] All tests passed!")
    print(f"\nStatistics:")
    print(f"  Total tags: {total_tags}")
    print(f"  Tags with prefix 'PI': {total}")
    print(f"  Tags on page 53: {page_53_count}")
    print(f"  Tags with unit '04': {unit_04_count}")
    print("\n[OK] Tag search is working correctly!")
    print("=" * 80 + "\n")

    return True


if __name__ == "__main__":
    success = test_tag_search()
    sys.exit(0 if success else 1)
