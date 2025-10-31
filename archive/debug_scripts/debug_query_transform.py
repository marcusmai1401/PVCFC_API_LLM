"""
Debug query transformation to see how Vietnamese context affects retrieval
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.query_transform import QueryTransformer
from app.rag.schemas import QueryRequest

# Initialize transformer
transformer = QueryTransformer()

# Test queries
queries = ["04 TI 5058", "Tìm cho tôi tag name 04 TI 5058 trong bản vẽ P&ID"]

print("=" * 80)
print("QUERY TRANSFORMATION COMPARISON")
print("=" * 80)
print()

for i, query_text in enumerate(queries, 1):
    print(f"Query {i}: {query_text}")
    print("-" * 80)

    # Create request
    request = QueryRequest(
        query=query_text, query_type="pid", language="vi", max_context=8, hyde=False
    )

    # Transform
    try:
        transformed = transformer.transform(request)

        print(f"  Normalized query: {transformed.normalized_query}")
        print(f"  Intent: {transformed.intent}")
        print(f"  Query type: {transformed.query_type}")
        print(f"  Detected tags: {transformed.detected_tags}")
        print(
            f"  Has PID components: {hasattr(transformed, 'pid_components') and transformed.pid_components}"
        )

        if hasattr(transformed, "pid_components") and transformed.pid_components:
            print(f"  PID components: {transformed.pid_components}")

        print()

    except Exception as e:
        print(f"  ERROR: {e}")
        print()

print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print()
print("If 'detected_tags' or 'pid_components' differ between queries,")
print("that's the cause of retrieval differences.")
