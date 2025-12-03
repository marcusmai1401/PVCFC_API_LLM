"""Create Weaviate Chunk collection with full schema including tags

Configured for 768-dimensional Gemini embeddings (gemini-embedding-001)
"""
import weaviate
from weaviate.classes.config import Configure, DataType, Property, VectorDistances

print("Creating Weaviate Chunk collection...")
print("Configured for 768-dimensional Gemini embeddings")

try:
    client = weaviate.connect_to_local(host="localhost", port=8080)

    # Create collection with all properties including tags
    # Explicitly configure for 768-dimensional vectors (Gemini embeddings)
    client.collections.create(
        name="Chunk",
        vectorizer_config=Configure.Vectorizer.none(),
        vector_index_config=Configure.VectorIndex.hnsw(
            distance_metric=VectorDistances.COSINE,
            ef_construction=128,
            ef=64,
            max_connections=64,
            vector_cache_max_objects=100000,
        ),
        properties=[
            Property(name="text", data_type=DataType.TEXT),
            Property(name="doc_id", data_type=DataType.TEXT),
            Property(name="page", data_type=DataType.INT),
            Property(name="equipment_type", data_type=DataType.TEXT),
            Property(name="doc_type", data_type=DataType.TEXT),
            Property(name="equipment_id", data_type=DataType.TEXT),
            Property(name="vendor", data_type=DataType.TEXT),
            Property(name="source_path", data_type=DataType.TEXT),
            Property(name="lang", data_type=DataType.TEXT),
            Property(
                name="tags",
                data_type=DataType.TEXT_ARRAY,
                description="Equipment tags extracted from chunk (e.g., ['04 ZLH 2038A', 'P-04201A'])",
            ),
        ],
    )

    print("✅ Weaviate Chunk collection created successfully")
    print("✅ Includes 'tags' property (TEXT_ARRAY)")
    print("✅ Configured for 768-dimensional vectors (Gemini embeddings)")

    # Verify
    collection = client.collections.get("Chunk")
    config = collection.config.get()
    props = [p.name for p in config.properties]
    print(f"\nProperties: {props}")

    client.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
