"""Delete Weaviate Chunk collection"""
import weaviate

try:
    client = weaviate.connect_to_local(host="localhost", port=8080)
    client.collections.delete("Chunk")
    print("✅ Weaviate Chunk collection deleted")
    client.close()
except Exception as e:
    print(f"❌ Error: {e}")
