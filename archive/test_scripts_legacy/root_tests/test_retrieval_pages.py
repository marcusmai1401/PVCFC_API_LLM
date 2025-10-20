#!/usr/bin/env python
"""Test real query to verify page numbers in retrieval"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.hybrid_weaviate_opensearch_retriever import (
    HybridWeaviateOpenSearchRetriever,
)

print("\n" + "=" * 80)
print("REAL QUERY TEST - PAGE NUMBER VERIFICATION")
print("=" * 80 + "\n")

# Initialize retriever
retriever = HybridWeaviateOpenSearchRetriever()

# Test query
query = "torque của turbine"
print(f"Query: {query}")
print("-" * 80 + "\n")

# Retrieve
results = retriever.retrieve_enhanced(
    query=query,
    top_k=10,
    enable_pid_enhancement=False,  # Disable PID for simpler test
)

print(f"Retrieved {len(results)} results:\n")

for i, result in enumerate(results, 1):
    print(f"{i}. Score: {result.score:.4f} | Page: {result.page}")
    print(f"   Doc ID: {result.doc_id}")
    print(f"   Text: {result.text[:100]}...")

    # Check if page marker exists in text
    import re

    markers = re.findall(r"<!-- Page (\d+) -->", result.text)
    if markers:
        marker_page = int(markers[0])
        if marker_page != result.page:
            print(f"   ⚠️  MISMATCH: stored={result.page}, marker={marker_page}")
        else:
            print(f"   ✅ Page marker matches")
    else:
        # Check table markers
        table_markers = re.findall(r"TABLE START \(Page (\d+)", result.text)
        if table_markers:
            marker_page = int(table_markers[0])
            # Note: table marker might be off by 1 due to 0-indexing
            if abs(marker_page - result.page) <= 1:
                print(f"   ✅ Table marker close: {marker_page}")
            else:
                print(f"   ⚠️  Table marker mismatch: {marker_page}")
        else:
            print(f"   ℹ️  No page marker in text (might be OK)")

    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Check for page=0 or None
invalid_pages = [r for r in results if r.page is None or r.page == 0]
if invalid_pages:
    print(f"⚠️  Found {len(invalid_pages)} results with invalid pages")
else:
    print(f"✅ All {len(results)} results have valid page numbers")

# Check page range
if results:
    pages = [r.page for r in results if r.page]
    print(f"   Page range: {min(pages)} - {max(pages)}")

print("=" * 80 + "\n")
