#!/usr/bin/env python
"""Inspect chunk p13 content to understand tag format"""

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

print("\n" + "=" * 80)
print("INSPECTING PAGE 13 CHUNKS WITH TAG 04 ZLH 2038A")
print("=" * 80 + "\n")

# Search for page 13 chunks containing the tag
tag = "04 ZLH 2038A"

# Method 1: BM25 search for the tag
print(f"Searching for: {tag}")
print("-" * 80 + "\n")

response = collection.query.bm25(
    query=tag,
    limit=10,
    return_properties=["text", "page", "doc_id", "tags"],
    filters=weaviate.classes.query.Filter.by_property("page").equal(13),
)

if not response.objects:
    print("No chunks found on page 13")
else:
    print(f"Found {len(response.objects)} chunks on page 13\n")

    for i, obj in enumerate(response.objects, 1):
        text = obj.properties.get("text", "")
        tags_prop = obj.properties.get("tags", [])

        print(f"\n{'='*80}")
        print(f"CHUNK {i}")
        print("=" * 80)
        print(f"UUID: {obj.uuid}")
        print(f"Page: {obj.properties.get('page')}")
        print(f"Tags property: {tags_prop}")
        print(f"\nText length: {len(text)} chars")
        print(f"Tag found in text: {tag in text}")

        # Show full text
        print(f"\n--- FULL TEXT ---")
        print(text)

        # Highlight tag occurrences
        if tag in text:
            print(f"\n--- TAG CONTEXT ---")
            idx = text.index(tag)
            start = max(0, idx - 200)
            end = min(len(text), idx + len(tag) + 200)
            context = text[start:end]

            # Highlight the tag
            highlighted = context.replace(tag, f">>>{tag}<<<")
            print(highlighted)

        print("\n" + "=" * 80)

# Also check via context_used chunk IDs from API response
print("\n\n" + "=" * 80)
print("CHECKING CONTEXT_USED CHUNKS FROM API")
print("=" * 80 + "\n")

context_ids = [
    "TAG_DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b_p13_04_IS_2037",
    "TAG_DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b_p13_04_IS_2036A",
    "TAG_DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b_p13_04_IS_2036B",
]

print("Context IDs mentioning p13:")
for chunk_id in context_ids:
    print(f"  - {chunk_id}")

print(
    "\nNote: These chunk_ids suggest chunks exist on page 13, but content may be in different format"
)

print("\n" + "=" * 80 + "\n")

client.close()
