"""Test script to verify Weaviate retrieval"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.rag.query_transform import QueryTransformer
from app.rag.weaviate_retriever import create_weaviate_retriever

# Create retriever
print("Creating Weaviate retriever...")
retriever = create_weaviate_retriever(collection_name="Chunk")

# Perform health check
print("\nHealth check:")
health = retriever.health_check()
print(health)

# Transform a simple query
print("\nTransforming query...")
transformer = QueryTransformer()
transformed_query = transformer.transform("What is PVCFC?")
print(f"Normalized query: {transformed_query.normalized}")

# Search
print("\nSearching...")
try:
    results = retriever.search(transformed_query)
    print(f"Found {len(results)} results")

    if results:
        print("\nFirst result:")
        r = results[0]
        print(f"  chunk_id: {r.chunk_id}")
        print(f"  score: {r.score}")
        print(f"  source: {r.source}")
        print(f"  doc_id: {r.doc_id}")
        print(f"  text: {r.text[:200]}...")
    else:
        print("No results found!")
except Exception as e:
    print(f"Error during search: {e}")
    import traceback

    traceback.print_exc()
