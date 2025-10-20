#!/usr/bin/env python
"""Verify page numbers after reindex"""

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
print("VERIFICATION: Page Numbers After Fix")
print("=" * 80 + "\n")

# Sample 10 objects
response = collection.query.fetch_objects(limit=10)

page_stats = {"zero": 0, "valid": 0, "none": 0}

for i, obj in enumerate(response.objects, 1):
    page = obj.properties.get("page")
    text_preview = obj.properties.get("text", "")[:100]

    if page is None:
        page_stats["none"] += 1
        status = "❌ None"
    elif page == 0:
        page_stats["zero"] += 1
        status = "❌ 0"
    else:
        page_stats["valid"] += 1
        status = "✅"

    print(f"{i}. UUID: {str(obj.uuid)[:8]}... | Page: {page:>4} {status}")
    print(f"   Text: {text_preview}...")
    print()

print("=" * 80)
print(f"Sample Stats (n=10):")
print(f"  ✅ Valid (page > 0): {page_stats['valid']}")
print(f"  ❌ Page = 0: {page_stats['zero']}")
print(f"  ❌ Page = None: {page_stats['none']}")
print("=" * 80 + "\n")

client.close()
