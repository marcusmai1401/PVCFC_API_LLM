#!/usr/bin/env python3
"""Debug retrieval for PU 2049 query"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)
from app.rag.query_transform import QueryIntent, TransformedQuery

# Initialize retriever
retriever = HybridWeaviateOpenSearchRetriever()

# Create query
query = TransformedQuery(
    original="Tìm cho tôi thiết bị 04 PU 2049 nằm ở đâu trong bản vẽ P&ID",
    normalized="tìm cho tôi thiết bị 04 pu 2049 nằm ở đâu trong bản vẽ p id",
    intent=QueryIntent.ASK,
    language="vi",
    filters={},
    metadata={},
)

# Search
print("\n" + "=" * 80)
print("RETRIEVAL DEBUG: 04 PU 2049")
print("=" * 80)

results = retriever.search(query)

print(f"\nRetrieved {len(results)} results:\n")

# Group by is_tag_entity
tag_results = []
text_results = []

for i, doc in enumerate(results[:20], 1):
    is_tag = doc.metadata.get("is_tag_entity", False) if doc.metadata else False

    if is_tag:
        tag_results.append((i, doc))
    else:
        text_results.append((i, doc))

    marker = "TAG" if is_tag else "TEXT"

    print(f"[{i}] {marker} | Page {doc.page} | Score {doc.score:.4f}")
    print(f"    Text: {doc.text[:100]}")
    print(f"    is_tag_entity: {is_tag}")
    print(f"    Source: {doc.source}")
    print()

print("=" * 80)
print(f"\nSUMMARY:")
print(f"  Tags: {len(tag_results)}")
print(f"  Text chunks: {len(text_results)}")

if tag_results:
    print(f"\n  Tag positions: {[pos for pos, _ in tag_results]}")
    print(f"  Tag pages: {[doc.page for _, doc in tag_results]}")
else:
    print(f"\n  ⚠️  NO TAGS in top 20 results!")

# Check if "04 PU 2049" tag is in results
pu_2049_found = False
for i, doc in enumerate(results, 1):
    if "04 PU 2049" in doc.text and doc.metadata.get("is_tag_entity"):
        pu_2049_found = True
        print(f"\n  ✅ Found '04 PU 2049' tag at position {i}, page {doc.page}")
        break

if not pu_2049_found:
    print(f"\n  ❌ '04 PU 2049' tag NOT in top 20!")
