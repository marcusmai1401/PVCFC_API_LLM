"""Test that tags with spaces are searchable in OpenSearch and Weaviate"""
import weaviate
from opensearchpy import OpenSearch

# Test OpenSearch
print("=" * 80)
print("TESTING OPENSEARCH TAG SEARCH")
print("=" * 80)

client = OpenSearch([{"host": "localhost", "port": 9200}], use_ssl=False)

# Test query for tag with spaces
test_tags = ["NDH 2022", "H 2022", "04 ZLH 2055A", "NG 04109"]

for tag in test_tags:
    result = client.search(
        index="rag_chunks", body={"query": {"match": {"tags": tag}}, "size": 2}
    )

    total = result["hits"]["total"]["value"]
    print(f"\nTag: '{tag}'")
    print(f"  Total hits: {total}")

    if total > 0:
        hit = result["hits"]["hits"][0]
        src = hit["_source"]
        print(f"  Sample chunk: {src['chunk_id']}")
        print(f"  Page: {src.get('page')}")
        print(f"  Tags (first 5): {src.get('tags', [])[:5]}")

# Test Weaviate
print("\n" + "=" * 80)
print("TESTING WEAVIATE TAG SEARCH")
print("=" * 80)

wv_client = weaviate.connect_to_local(host="localhost", port=8080)
collection = wv_client.collections.get("Chunk")

for tag in test_tags:
    result = collection.query.fetch_objects(
        filters=weaviate.classes.query.Filter.by_property("tags").contains_any([tag]),
        limit=2,
        return_properties=["chunk_id", "page", "tags"],
    )

    print(f"\nTag: '{tag}'")
    print(f"  Results: {len(result.objects)}")

    if result.objects:
        obj = result.objects[0]
        props = obj.properties
        print(f"  Sample chunk: {props.get('chunk_id')}")
        print(f"  Page: {props.get('page')}")
        print(f"  Tags (first 5): {props.get('tags', [])[:5]}")

wv_client.close()

print("\n" + "=" * 80)
print("TAG SEARCH TEST COMPLETE")
print("=" * 80)
