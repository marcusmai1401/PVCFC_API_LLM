"""Create OpenSearch index with Parent-Child schema (Phase 3)

Supports Parent-Child chunking strategy with Option A (parent_text in child)
"""
import os

from opensearchpy import OpenSearch

print("Creating OpenSearch index with Parent-Child schema...")

# Connect to OpenSearch (no auth in dev mode)
client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

index_name = "rag_chunks"

try:
    # Delete existing index if it exists
    if client.indices.exists(index=index_name):
        client.indices.delete(index=index_name)
        print(f"✓ Deleted existing index: {index_name}")

    # Create index with parent-child mapping
    index_body = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index": {
                "similarity": {
                    "default": {
                        "type": "BM25",
                        "k1": 1.2,  # Term frequency saturation
                        "b": 0.75,  # Length normalization
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                # Original fields
                "text": {
                    "type": "text",
                    "analyzer": "standard",
                    "description": "Child chunk text for indexing",
                },
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "page": {"type": "integer"},
                "score": {"type": "float"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 768,
                    "index": False,
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "doc_type": {"type": "keyword"},
                        "equipment_type": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                        "source": {"type": "text"},
                        "file_name": {"type": "text"},
                        # NEW: Parent-Child fields in metadata
                        "parent_id": {"type": "keyword"},
                        "chunk_type": {"type": "keyword"},
                        "is_parent": {"type": "boolean"},
                        "parent_index": {"type": "integer"},
                        "parent_char_count": {"type": "integer"},
                    },
                },
                # NEW: Parent text as top-level field for fast access
                "parent_text": {
                    "type": "text",
                    "index": False,  # Not indexed, only stored for retrieval
                    "description": "Full parent chunk text (1500-2000 chars) for LLM context",
                },
            }
        },
    }

    # Create the index
    response = client.indices.create(index=index_name, body=index_body)

    print(f"✅ OpenSearch index created successfully: {index_name}")
    print("✅ Phase 3 Parent-Child schema applied")
    print(
        "✅ New fields: parent_text (top-level), parent_id, chunk_type, is_parent, parent_index, parent_char_count (in metadata)"
    )

    # Verify mapping
    mapping = client.indices.get_mapping(index=index_name)
    properties = mapping[index_name]["mappings"]["properties"]

    print(f"\nTotal properties: {len(properties)}")
    print(f"Top-level fields: {', '.join(properties.keys())}")

    if "metadata" in properties:
        metadata_props = properties["metadata"].get("properties", {})
        print(f"Metadata fields: {', '.join(metadata_props.keys())}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
finally:
    client.close()
