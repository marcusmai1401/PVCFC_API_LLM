#!/usr/bin/env python
"""Check specific P&ID tags in Weaviate"""

import sys
from pathlib import Path

import weaviate
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

# Connect
client = weaviate.connect_to_local(
    host=settings.weaviate_host,
    port=settings.weaviate_port,
)

collection = client.collections.get(settings.weaviate_collection)

# Tags to search
tags = ["04 ZLH 2038A", "04 LAHH 2091", "04 TI 5027"]

print("\n" + "=" * 80)
print("CHECKING P&ID TAGS IN WEAVIATE")
print("=" * 80 + "\n")

for tag in tags:
    print(f"\n{'='*80}")
    print(f"TAG: {tag}")
    print("=" * 80)

    # Search for tag using BM25
    response = collection.query.bm25(
        query=tag,
        limit=5,
        return_properties=["text", "page", "doc_id", "tags", "source_path"],
    )

    if not response.objects:
        print(f"  No results found for tag: {tag}")
        continue

    for i, obj in enumerate(response.objects, 1):
        page = obj.properties.get("page")
        text = obj.properties.get("text", "")
        doc_id = obj.properties.get("doc_id", "")

        print(f"\n  Result {i}:")
        print(f"    Page stored: {page}")
        print(f"    Doc ID: {doc_id[:60]}...")

        # Check if tag appears in text
        if tag in text:
            print(f"    Tag found in text: YES")
            # Show context around tag
            idx = text.index(tag)
            context_start = max(0, idx - 50)
            context_end = min(len(text), idx + len(tag) + 50)
            context = text[context_start:context_end]
            print(f"    Context: ...{context}...")
        else:
            print(f"    Tag found in text: NO (might be semantic match)")

        # Check for page markers in text
        import re

        markers = re.findall(r"<!-- Page (\d+) -->", text)
        if markers:
            print(f"    Page marker in content: {markers[0]}")

        table_markers = re.findall(r"TABLE START \(Page (\d+)", text)
        if table_markers:
            print(f"    Table marker in content: {table_markers[0]}")

print("\n" + "=" * 80 + "\n")

client.close()
