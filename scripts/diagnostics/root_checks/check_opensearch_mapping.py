#!/usr/bin/env python3
"""Check OpenSearch index mapping for is_tag_entity field"""

import json
import os

from opensearchpy import OpenSearch

# Load credentials from environment variables
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")

if not OPENSEARCH_PASSWORD:
    raise ValueError(
        "OPENSEARCH_PASSWORD environment variable is required. "
        "Please set it before running this script."
    )

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

# Get index mapping
mapping = client.indices.get_mapping(index="rag_chunks")

print("\n" + "=" * 80)
print("OPENSEARCH INDEX MAPPING")
print("=" * 80)

# Pretty print mapping
print(json.dumps(mapping, indent=2))

# Check if is_tag_entity field exists
if "rag_chunks" in mapping:
    properties = mapping["rag_chunks"]["mappings"].get("properties", {})

    print("\n" + "=" * 80)
    print("FIELD CHECK")
    print("=" * 80)

    if "is_tag_entity" in properties:
        print("\n✅ is_tag_entity field EXISTS (top-level)")
        print(f"   Type: {properties['is_tag_entity']}")
    else:
        print("\n❌ is_tag_entity field NOT FOUND (top-level)")

    # Check in metadata
    if "metadata" in properties:
        metadata_props = properties["metadata"].get("properties", {})
        if "is_tag_entity" in metadata_props:
            print("\n✅ is_tag_entity found in metadata")
            print(f"   Type: {metadata_props['is_tag_entity']}")
        else:
            print("\n❌ is_tag_entity NOT in metadata")
