"""Check if specific tags exist in Weaviate"""
import weaviate
from weaviate.classes.query import Filter

# Tags to search for
tags_to_find = ["04 ZLH 2038A", "04 LAHH 2091", "04 TI 5027"]

print("Connecting to Weaviate...")
client = weaviate.connect_to_local(host="localhost", port=8080)

try:
    collection = client.collections.get("Chunk")

    for tag in tags_to_find:
        print(f"\n{'='*60}")
        print(f"Searching for: {tag}")
        print(f"{'='*60}")

        # Search with text contains
        result = collection.query.fetch_objects(
            limit=10, filters=Filter.by_property("text").like(f"*{tag}*")
        )

        print(f"Found {len(result.objects)} results")

        for i, obj in enumerate(result.objects, 1):
            text = obj.properties.get("text", "")
            page = obj.properties.get("page", "N/A")
            doc_id = obj.properties.get("doc_id", "N/A")
            print(f"\n{i}. Page {page}")
            print(f"   Text: {text[:100]}...")
            print(f"   Doc: {doc_id}")

finally:
    client.close()
    print("\n\nConnection closed.")
