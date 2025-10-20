"""
Test that Weaviate vector search now works with 768-dim embeddings
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import weaviate
from src.models.embedding import GeminiEmbeddingModel


def test_weaviate_vector_search():
    # Initialize embedding model
    print("Loading Gemini embedding model...")
    embedding_model = GeminiEmbeddingModel()

    # Connect to Weaviate
    print("Connecting to Weaviate...")
    client = weaviate.connect_to_local("localhost", 8080)
    collection = client.collections.get("Chunk")

    # Test query
    query = "Fire detection system configuration"
    print(f"\n🔍 Query: '{query}'\n")

    # Generate query embedding
    print("Generating query embedding...")
    query_embedding = embedding_model.embed_text(query)
    print(f"✅ Embedding dimension: {len(query_embedding)}")

    # Perform vector search
    print("\n🔎 Performing vector search in Weaviate...")
    try:
        results = collection.query.near_vector(
            near_vector=query_embedding, limit=5, return_metadata=["distance"]
        )

        print(f"✅ Vector search successful! Found {len(results.objects)} results\n")

        for i, obj in enumerate(results.objects, 1):
            props = obj.properties
            distance = (
                obj.metadata.distance if hasattr(obj.metadata, "distance") else "N/A"
            )

            print(f"Result {i}:")
            print(f"  Distance: {distance}")
            print(f"  Doc ID: {props.get('doc_id', 'N/A')}")
            print(f"  Page: {props.get('page', 'N/A')}")
            print(f"  Equipment: {props.get('equipment_type', 'N/A')}")
            print(f"  Tags: {props.get('tags', [])}")
            print(f"  Text preview: {props.get('text', '')[:150]}...")
            print()

    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    test_weaviate_vector_search()
