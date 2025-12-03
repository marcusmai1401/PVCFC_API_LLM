"""Check Weaviate schema"""
import weaviate

client = weaviate.connect_to_local(host="localhost", port=8080)

try:
    collection = client.collections.get("Chunk")
    config = collection.config.get()

    print("Chunk collection properties:")
    print("=" * 60)

    for prop in config.properties:
        print(f"- {prop.name} ({prop.data_type})")

finally:
    client.close()
