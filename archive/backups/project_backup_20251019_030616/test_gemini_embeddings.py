"""
Test that Weaviate now has 768-dimensional Gemini embeddings
"""
import weaviate

from app.core.config import settings
from app.services.embedding_enhanced import UniversalEmbeddingService


def test_gemini_embeddings():
    # Initialize Gemini embedding service
    print("Initializing Gemini embedding service...")
    print(f"Provider: {settings.embedding_provider}")
    print(f"Model: {settings.embedding_model}")

    embedding_service = UniversalEmbeddingService(
        provider=settings.embedding_provider, model_name=settings.embedding_model
    )

    # Connect to Weaviate
    print("\nConnecting to Weaviate...")
    client = weaviate.connect_to_local("localhost", 8080)
    collection = client.collections.get("Chunk")

    # Check collection stats
    response = collection.aggregate.over_all(total_count=True)
    print(f"✅ Total objects: {response.total_count}")

    # Test query
    query = "Fire detection system configuration"
    print(f"\n🔍 Query: '{query}'\n")

    # Generate query embedding with Gemini
    print("Generating query embedding with Gemini...")
    query_embedding = embedding_service.embed_texts([query], batch_size=1)[0]
    print(f"✅ Embedding dimension: {len(query_embedding)}")

    if len(query_embedding) != 768:
        print(f"❌ ERROR: Expected 768 dimensions, got {len(query_embedding)}")
    else:
        print("✅ Correct dimension (768) - Gemini embeddings confirmed!")

    # Perform vector search
    print("\n🔎 Performing vector search with Gemini embeddings...")
    try:
        results = collection.query.near_vector(
            near_vector=query_embedding.tolist(), limit=5, return_metadata=["distance"]
        )

        print(f"✅ Vector search successful! Found {len(results.objects)} results\n")

        for i, obj in enumerate(results.objects, 1):
            props = obj.properties
            distance = (
                obj.metadata.distance if hasattr(obj.metadata, "distance") else "N/A"
            )

            print(f"Result {i}:")
            print(f"  Distance: {distance}")
            print(f"  Doc ID: {props.get('doc_id', 'N/A')[:60]}")
            print(f"  Page: {props.get('page', 'N/A')}")
            print(f"  Tags: {props.get('tags', [])[:5]}")
            print(f"  Text preview: {props.get('text', '')[:100]}...")
            print()

    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    test_gemini_embeddings()
