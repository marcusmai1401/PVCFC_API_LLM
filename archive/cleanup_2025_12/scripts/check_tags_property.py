"""Check tags property in Weaviate"""
import weaviate
from weaviate.classes.query import Filter

tags_to_find = ["04 ZLH 2038A", "04 LAHH 2091", "04 TI 5027"]

client = weaviate.connect_to_local(host="localhost", port=8080)

try:
    collection = client.collections.get("Chunk")

    for tag in tags_to_find:
        print(f"\n{'='*60}")
        print(f"Searching tags property for: {tag}")
        print(f"{'='*60}")

        # Try exact match in tags array
        result = collection.query.fetch_objects(
            limit=5, filters=Filter.by_property("tags").contains_any([tag])
        )

        print(f"Found {len(result.objects)} results with tag in 'tags' property")

        for obj in result.objects:
            text = obj.properties.get("text", "")
            page = obj.properties.get("page", "N/A")
            tags_prop = obj.properties.get("tags", [])
            print(f"  Page {page}: {text[:80]}...")
            print(f"  Tags: {tags_prop}")

finally:
    client.close()
