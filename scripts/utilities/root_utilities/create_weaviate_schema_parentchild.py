"""Create Weaviate Chunk collection with Parent-Child schema (Phase 3)

Configured for 768-dimensional Gemini embeddings (gemini-embedding-001)
Supports Parent-Child chunking strategy with Option A (parent_text in child)
"""
import weaviate
from weaviate.classes.config import Configure, DataType, Property, VectorDistances

print("Creating Weaviate Chunk collection with Parent-Child schema...")
print("Configured for 768-dimensional Gemini embeddings")

try:
    client = weaviate.connect_to_local(host="localhost", port=8080)

    # Delete existing collection if it exists
    try:
        client.collections.delete("Chunk")
        print("✓ Deleted existing Chunk collection")
    except Exception:
        print("ℹ No existing collection to delete")

    # Create collection with parent-child properties
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
            # Original fields
            Property(
                name="text",
                data_type=DataType.TEXT,
                description="Child chunk text for indexing",
            ),
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
                description="Equipment tags extracted from chunk",
            ),
            # NEW: Parent-Child fields
            Property(
                name="parent_text",
                data_type=DataType.TEXT,
                description="Full parent chunk text (1500-2000 chars) for LLM context",
            ),
            Property(
                name="parent_id",
                data_type=DataType.TEXT,
                description="ID of parent chunk",
            ),
            Property(
                name="chunk_type",
                data_type=DataType.TEXT,
                description="Type: 'child' or 'parent'",
            ),
            Property(
                name="is_parent",
                data_type=DataType.BOOL,
                description="False for child chunks (indexed), True for parent (not used)",
            ),
            Property(
                name="parent_index",
                data_type=DataType.INT,
                description="Index of parent chunk in document",
            ),
            Property(
                name="parent_char_count",
                data_type=DataType.INT,
                description="Character count of parent text",
            ),
        ],
    )

    print("✅ Weaviate Chunk collection created successfully")
    print("✅ Phase 3 Parent-Child schema applied")
    print(
        "✅ New fields: parent_text, parent_id, chunk_type, is_parent, parent_index, parent_char_count"
    )

    # Verify
    collection = client.collections.get("Chunk")
    config = collection.config.get()
    props = [p.name for p in config.properties]
    print(f"\nTotal properties: {len(props)}")
    print(f"Properties: {', '.join(props)}")

    client.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
