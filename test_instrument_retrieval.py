"""
Test if Instrument List document can be retrieved with Tag No. query
"""
import os

os.environ["LOGURU_LEVEL"] = "INFO"

from app.rag.hybrid_weaviate_opensearch_retriever import HybridModernRetriever
from app.rag.query_transform import QueryTransformer

# Initialize
retriever = HybridModernRetriever()
transformer = QueryTransformer(enable_hyde=False)

# Test query with Tag number
query = "06-TE-0256 A/B Tag No instrument list"

print("=" * 80)
print("TESTING INSTRUMENT LIST RETRIEVAL")
print("=" * 80)
print(f"Query: {query}\n")

# Transform and search
transformed = transformer.transform(query, language="en")
results = retriever.search(transformed)

print(f"Retrieved {len(results)} documents:\n")

# Check if Instrument List is in results
instrument_found = False
for i, result in enumerate(results[:10], 1):
    doc_id = result.doc_id[:80] if result.doc_id else "None"
    page = result.page
    score = result.score

    is_instrument = "Instrument" in doc_id
    marker = "✅ FOUND!" if is_instrument else ""

    print(f"{i}. doc_id: {doc_id}")
    print(f"   page: {page}, score: {score:.4f} {marker}")
    print()

    if is_instrument:
        instrument_found = True
        print(f"   Text snippet: {result.text[:200]}...")
        print()

if not instrument_found:
    print("❌ Instrument List NOT in top 10 results!")
    print("\nPossible reasons:")
    print("  1. Tag number '06-TE-0256' might not be in the indexed text")
    print("  2. Query keywords don't match well with Instrument List content")
    print("  3. Operating Manual has higher BM25/semantic scores")
else:
    print("✅ Instrument List found in retrieval results!")
