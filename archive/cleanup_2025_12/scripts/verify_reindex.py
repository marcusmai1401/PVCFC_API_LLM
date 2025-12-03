"""Verify re-indexed data in OpenSearch and Weaviate"""
import json

import requests
import weaviate
from weaviate.classes.init import Auth

print("=" * 70)
print("VERIFYING RE-INDEXED DATA")
print("=" * 70)

# Initialize counts
opensearch_count = 0
weaviate_count = 0

# OpenSearch verification
print("\n" + "=" * 70)
print("OPENSEARCH VERIFICATION")
print("=" * 70)

try:
    # Count documents
    response = requests.get("http://localhost:9200/rag_chunks/_count")
    count_data = response.json()
    opensearch_count = count_data.get("count", 0)
    print(f"✅ Total documents: {opensearch_count:,}")

    # Get sample documents with metadata.page
    search_query = {
        "size": 5,
        "_source": ["chunk_id", "doc_id", "page", "page_start", "metadata.page"],
        "query": {"match_all": {}},
    }
    response = requests.post(
        "http://localhost:9200/rag_chunks/_search",
        json=search_query,
        headers={"Content-Type": "application/json"},
    )
    search_data = response.json()
    hits = search_data.get("hits", {}).get("hits", [])

    print(f"\nSample 5 documents:")
    for i, hit in enumerate(hits, 1):
        source = hit["_source"]
        print(f"\n  Doc {i}:")
        print(f"    chunk_id: {source.get('chunk_id')}")
        print(f"    page (root): {source.get('page')}")
        print(f"    page_start: {source.get('page_start')}")
        print(f"    metadata.page: {source.get('metadata', {}).get('page')}")

    # Check if root-level 'page' field exists
    mapping_response = requests.get("http://localhost:9200/rag_chunks/_mapping")
    mapping = mapping_response.json()
    properties = mapping.get("rag_chunks", {}).get("mappings", {}).get("properties", {})

    if "page" in properties:
        print(f"\n✅ Root-level 'page' field exists in mapping")
        print(f"   Type: {properties['page'].get('type')}")
    else:
        print(f"\n❌ Root-level 'page' field NOT in mapping!")

    if "tags" in properties:
        print(f"✅ Root-level 'tags' field exists in mapping")
        print(f"   Type: {properties['tags'].get('type')}")
    else:
        print(f"❌ Root-level 'tags' field NOT in mapping!")

    if "tags_raw" in properties:
        print(f"✅ Root-level 'tags_raw' field exists in mapping")
        print(f"   Type: {properties['tags_raw'].get('type')}")
    else:
        print(f"❌ Root-level 'tags_raw' field NOT in mapping!")

except Exception as e:
    print(f"❌ Error checking OpenSearch: {e}")

# Weaviate verification
print("\n" + "=" * 70)
print("WEAVIATE VERIFICATION")
print("=" * 70)

try:
    client = weaviate.connect_to_local(
        host="localhost",
        port=8080,
        grpc_port=50051,
    )

    collection = client.collections.get("Chunk")

    # Count objects
    response = collection.aggregate.over_all(total_count=True)
    weaviate_count = response.total_count
    print(f"✅ Total objects: {weaviate_count:,}")

    # Get sample objects
    results = collection.query.fetch_objects(limit=5)

    print(f"\nSample 5 objects:")
    for i, obj in enumerate(results.objects, 1):
        props = obj.properties
        print(f"\n  Object {i}:")
        print(f"    chunk_id: {props.get('chunk_id')}")
        print(f"    page (property): {props.get('page')}")
        print(f"    page_start: {props.get('page_start')}")
        print(
            f"    tags: {props.get('tags', [])[:3] if props.get('tags') else None}..."
        )
        print(
            f"    tags_raw: {props.get('tags_raw', [])[:3] if props.get('tags_raw') else None}..."
        )

    # Check schema
    schema_props = collection.config.get().properties
    prop_names = [p.name for p in schema_props]

    print(f"\n✅ Schema properties: {', '.join(prop_names)}")

    if "page" in prop_names:
        print(f"✅ 'page' property exists in schema")
    else:
        print(f"❌ 'page' property NOT in schema!")

    if "tags" in prop_names:
        print(f"✅ 'tags' property exists in schema")
    else:
        print(f"❌ 'tags' property NOT in schema!")

    if "tags_raw" in prop_names:
        print(f"✅ 'tags_raw' property exists in schema")
    else:
        print(f"❌ 'tags_raw' property NOT in schema!")

    client.close()

except Exception as e:
    print(f"❌ Error checking Weaviate: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"OpenSearch documents: {opensearch_count:,}")
print(f"Weaviate objects: {weaviate_count:,}")

if opensearch_count == weaviate_count == 66512:
    print("\n✅ ALL INDEXES COMPLETE AND CONSISTENT!")
else:
    print(f"\n⚠️  Index counts don't match expected 66,512")
