"""
Simple test to verify Weaviate vector search works
"""
import weaviate
from sentence_transformers import SentenceTransformer


def test_weaviate_vector_search():
    # Initialize embedding model (same as indexing script)
    print("Loading embedding model...")
    embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    print(
        f"✅ Model loaded: dimension={embedding_model.get_sentence_embedding_dimension()}"
    )

    # Connect to Weaviate
    print("\nConnecting to Weaviate...")
    client = weaviate.connect_to_local("localhost", 8080)
    collection = client.collections.get("Chunk")

    # Check collection stats
    response = collection.aggregate.over_all(total_count=True)
    print(f"✅ Connected! Total objects: {response.total_count}")

    # Test query
    query = "Fire detection system configuration"
    print(f"\n🔍 Query: '{query}'\n")

    # Generate query embedding
    print("Generating query embedding...")
    query_embedding = embedding_model.encode(query).tolist()
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
            print(f"  Tags: {props.get('tags', [])}")
            print(f"  Text preview: {props.get('text', '')[:100]}...")
            print()

    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    test_weaviate_vector_search()
