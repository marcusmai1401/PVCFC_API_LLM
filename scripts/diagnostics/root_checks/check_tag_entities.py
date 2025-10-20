"""Check if TAG entities exist for specific tags"""
import weaviate
from weaviate.classes.query import Filter

tags_search = [
    ("04_ZLH_2038A", "04 ZLH 2038A"),
    ("04_LAHH_2091", "04 LAHH 2091"),
    ("04_TI_5027", "04 TI 5027"),
]

print("Connecting to Weaviate...")
client = weaviate.connect_to_local(host="localhost", port=8080)

try:
    collection = client.collections.get("Chunk")

    for tag_id, tag_name in tags_search:
        print(f"\n{'='*60}")
        print(f"TAG entity search for: {tag_name} (chunk_id pattern: *{tag_id}*)")
        print(f"{'='*60}")

        result = collection.query.fetch_objects(
            limit=5, filters=Filter.by_property("chunk_id").like(f"*{tag_id}*")
        )

        print(f"Found {len(result.objects)} TAG entities")

        if len(result.objects) == 0:
            print(f"❌ NO TAG entity found for {tag_name}")
        else:
            for obj in result.objects:
                text = obj.properties.get("text", "")
                page = obj.properties.get("page", "N/A")
                chunk_id = obj.properties.get("chunk_id", "N/A")
                print(f"  ✅ Page {page}: {text}")
                print(f"     ID: {chunk_id}")

finally:
    client.close()
    print("\n\nConnection closed.")
