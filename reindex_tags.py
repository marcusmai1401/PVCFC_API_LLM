"""
Re-index tags from tags.jsonl to OpenSearch
"""
import json
from pathlib import Path

from opensearchpy import OpenSearch, helpers

# Setup
tags_file = Path("output/pid_ingestion/tags.jsonl")
index_name = "pvcfc_pid_tags"

# Connect to OpenSearch
client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}], http_compress=True, timeout=30
)

print(f"Reading tags from: {tags_file}")
tags = []
with open(tags_file, encoding="utf-8") as f:
    for line in f:
        tags.append(json.loads(line))

print(f"Loaded {len(tags)} tags")

# Delete and recreate index
if client.indices.exists(index=index_name):
    print(f"Deleting existing index: {index_name}")
    client.indices.delete(index=index_name)

print(f"Creating index: {index_name}")
client.indices.create(
    index=index_name,
    body={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "page": {"type": "integer"},
                "tag": {"type": "text"},
                "unit": {"type": "keyword"},
                "prefix": {"type": "keyword"},
                "suffix": {"type": "keyword"},
                "variant": {"type": "keyword"},
                "annotation": {"type": "keyword"},
                "bbox": {"type": "float"},
                "confidence": {"type": "float"},
                "has_variant": {"type": "boolean"},
                "has_annotation": {"type": "boolean"},
            }
        },
    },
)

# Bulk index
print(f"Indexing {len(tags)} tags...")

actions = [{"_index": index_name, "_source": tag} for tag in tags]

success, failed = helpers.bulk(client, actions, raise_on_error=False)

print(f"\n✅ Indexing complete!")
print(f"   Success: {success}")
print(f"   Failed: {len(failed) if isinstance(failed, list) else 0}")

# Refresh index
client.indices.refresh(index=index_name)

# Verify
count = client.count(index=index_name)["count"]
print(f"   Index count: {count}")

# Check for target tag
result = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [
                    {"term": {"unit": "04"}},
                    {"term": {"prefix": "TI"}},
                    {"term": {"suffix": "5058"}},
                ]
            }
        }
    },
)

if result["hits"]["total"]["value"] > 0:
    tag = result["hits"]["hits"][0]["_source"]
    print(f"\n✅ Target tag '04 TI 5058' found in index (page {tag['page']})")
else:
    print(f"\n❌ Target tag '04 TI 5058' NOT in index")
