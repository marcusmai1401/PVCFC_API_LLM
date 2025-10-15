"""Index test chunks into OpenSearch rag_chunks index"""
import json
from pathlib import Path

from opensearchpy import OpenSearch, helpers

# Connect to OpenSearch
client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    timeout=60,
)

# Load chunks
chunks_file = Path("artifacts/ingestion_test/chunks/chunks.jsonl")
lines = chunks_file.read_text(encoding="utf-8").strip().split("\n")
chunks = [json.loads(line) for line in lines]

print(f"✅ Loaded {len(chunks)} chunks from {chunks_file}")
print(f"📊 Sample chunk keys: {list(chunks[0].keys())}\n")

# Prepare bulk actions
actions = []
for chunk in chunks:
    # Extract fields
    chunk_id = chunk.get("chunk_id", "unknown")
    text = chunk.get("text", "")
    doc_id = chunk.get("doc_id", "")
    metadata = chunk.get("metadata", {})

    # Build document for OpenSearch
    doc = {
        "text": text,
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "chunk_index": chunk.get("chunk_index", 0),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "page": metadata.get("page"),  # Single page field for easy query
        "doc_type": metadata.get("doc_type"),
        "revision": metadata.get("revision"),
        "file_name": metadata.get("file_name"),
        "source_format": metadata.get("source_format"),
        # NEW: Tag fields from Week 1/2
        "tags": metadata.get("tags", []),
        "tags_raw": metadata.get("tags_raw", []),
    }

    # Remove None values
    doc = {k: v for k, v in doc.items() if v is not None}

    actions.append(
        {"_op_type": "index", "_index": "rag_chunks", "_id": chunk_id, "_source": doc}
    )

print(f"📤 Indexing {len(actions)} chunks into OpenSearch...")

try:
    # Bulk insert
    success, errors = helpers.bulk(client, actions, raise_on_error=False)

    print(f"✅ Success: {success} chunks indexed")
    if errors:
        print(f"⚠️  Errors: {len(errors)} chunks failed")
        for err in errors[:3]:  # Show first 3 errors
            print(f"   - {err}")

    # Refresh index
    client.indices.refresh(index="rag_chunks")
    print(f"✅ Index refreshed")

    # Verify count
    count_result = client.count(
        index="rag_chunks", body={"query": {"match": {"doc_id": doc_id}}}
    )
    count = count_result["count"]
    print(f"\n📊 Total chunks for doc_id '{doc_id}': {count}")

    # Sample query: find chunks with tags
    search_result = client.search(
        index="rag_chunks",
        body={"query": {"bool": {"must": [{"exists": {"field": "tags"}}]}}, "size": 3},
    )

    hits = search_result["hits"]["hits"]
    print(f"\n🔍 Sample chunks with tags: {len(hits)}")
    for hit in hits[:2]:
        src = hit["_source"]
        print(f"   - Chunk: {src.get('chunk_id')}")
        print(f"     Tags: {src.get('tags', [])[:5]}")  # Show first 5 tags
        print(f"     Page: {src.get('page')}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
