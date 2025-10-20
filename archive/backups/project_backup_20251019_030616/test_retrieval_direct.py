"""Direct test of retrieval system without API or LLM generation"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import weaviate
from opensearchpy import OpenSearch

from app.core.config import settings

print("=" * 100)
print("DIRECT RETRIEVAL TEST - Tags with Spaces")
print("=" * 100)

# Test tags
test_queries = [
    ("NDH 2022", "Equipment tag with space"),
    ("04 ZLH 2055A", "Valve tag with spaces"),
    ("NG 04109", "Tag with space"),
    ("H 2024", "Short tag with space"),
]

print("\n1. Testing OpenSearch BM25 Retrieval")
print("-" * 100)

os_client = OpenSearch(
    hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
    use_ssl=False,
)

for query, description in test_queries:
    print(f"\n🔍 Query: '{query}' ({description})")

    # Search by tag field
    result = os_client.search(
        index=settings.opensearch_index,
        body={
            "query": {
                "bool": {
                    "should": [
                        {"match": {"tags": {"query": query, "boost": 3.0}}},
                        {"match": {"text": query}},
                    ]
                }
            },
            "size": 3,
            "_source": ["chunk_id", "page", "tags", "doc_id"],
        },
    )

    total_hits = result["hits"]["total"]["value"]
    print(f"  Total hits: {total_hits}")

    if total_hits > 0:
        print(f"  Top 3 results:")
        for i, hit in enumerate(result["hits"]["hits"][:3], 1):
            src = hit["_source"]
            score = hit["_score"]
            print(f"    {i}. Page {src.get('page', 'N/A')} - Score: {score:.2f}")
            print(f"       Chunk: {src.get('chunk_id', 'N/A')[:70]}")
            tags = src.get("tags", [])
            if tags:
                # Check if query tag is in the tags
                matching_tags = [t for t in tags if query.upper() in t.upper()]
                print(f"       Matching tags: {matching_tags[:5]}")
            print()
    else:
        print("  ⚠️  No results found!")

print("\n" + "=" * 100)
print("2. Testing Weaviate Vector Retrieval")
print("-" * 100)

wv_client = weaviate.connect_to_local(
    host=settings.weaviate_host, port=settings.weaviate_port
)

collection = wv_client.collections.get(settings.weaviate_collection)

for query, description in test_queries:
    print(f"\n🔍 Query: '{query}' ({description})")

    # Hybrid search with tag filter
    try:
        result = collection.query.hybrid(
            query=query,
            limit=3,
            return_properties=["chunk_id", "page", "tags", "doc_id"],
            return_metadata=["score"],
        )

        print(f"  Results: {len(result.objects)}")

        if result.objects:
            print(f"  Top 3 results:")
            for i, obj in enumerate(result.objects[:3], 1):
                props = obj.properties
                score = obj.metadata.score if hasattr(obj.metadata, "score") else 0
                print(f"    {i}. Page {props.get('page', 'N/A')} - Score: {score:.4f}")
                print(f"       Chunk: {props.get('chunk_id', 'N/A')[:70]}")
                tags = props.get("tags", [])
                if tags:
                    matching_tags = [t for t in tags if query.upper() in t.upper()]
                    print(f"       Matching tags: {matching_tags[:5]}")
                print()
        else:
            print("  ⚠️  No results found!")

    except Exception as e:
        print(f"  ❌ Error: {e}")

wv_client.close()

print("\n" + "=" * 100)
print("3. Testing Tag Filter Query in Weaviate")
print("-" * 100)

wv_client = weaviate.connect_to_local(
    host=settings.weaviate_host, port=settings.weaviate_port
)

collection = wv_client.collections.get(settings.weaviate_collection)

for query, description in test_queries:
    print(f"\n🔍 Query: '{query}' ({description})")

    try:
        # Use filter for exact tag matching
        result = collection.query.fetch_objects(
            filters=weaviate.classes.query.Filter.by_property("tags").contains_any(
                [query]
            ),
            limit=3,
            return_properties=["chunk_id", "page", "tags", "doc_id"],
        )

        print(f"  Results with exact tag: {len(result.objects)}")

        if result.objects:
            print(f"  Sample results:")
            for i, obj in enumerate(result.objects[:3], 1):
                props = obj.properties
                print(f"    {i}. Page {props.get('page', 'N/A')}")
                print(f"       Chunk: {props.get('chunk_id', 'N/A')[:70]}")
                tags = props.get("tags", [])
                matching_tags = [t for t in tags if query.upper() in t.upper()]
                print(f"       Matching tags: {matching_tags[:5]}")
                print()
        else:
            print("  ⚠️  No results with exact tag match!")

    except Exception as e:
        print(f"  ❌ Error: {e}")

wv_client.close()

print("\n" + "=" * 100)
print("✅ RETRIEVAL TEST COMPLETE")
print("=" * 100)
