"""Verify newly indexed chunks with tags"""
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    timeout=30,
)

# Search for the new doc_id
doc_id = "DOCID_116_3N4-S4275354_Instrument_List_Rev.1_bd4e5ef8"

print(f"🔍 Searching for newly indexed chunks...")
print(f"📄 Doc ID: {doc_id}\n")

# Query chunks with this doc_id
result = client.search(
    index="rag_chunks",
    body={
        "query": {"term": {"doc_id.keyword": doc_id}},
        "size": 20,
        "_source": ["chunk_id", "page", "tags", "tags_raw", "text"],
    },
)

hits = result["hits"]["hits"]
print(f"✅ Found {len(hits)} chunks\n")

# Count chunks with tags
chunks_with_tags = [h for h in hits if h["_source"].get("tags")]
print(f"📊 Chunks with tags: {len(chunks_with_tags)}/{len(hits)}\n")

# Show chunks with most tags
if chunks_with_tags:
    print("🏷️  Top chunks with tags:\n")
    for hit in chunks_with_tags[:5]:
        src = hit["_source"]
        tags = src.get("tags", [])
        page = src.get("page", "N/A")
        text_preview = src.get("text", "")[:150]

        print(f"Page {page}: {len(tags)} tags")
        print(f"  Tags (first 10): {tags[:10]}")
        print(f"  Text: {text_preview}...")
        print()

    # Check for specific tags
    all_tags = set()
    for hit in chunks_with_tags:
        all_tags.update(hit["_source"].get("tags", []))

    print(f"\n📊 Total unique tags: {len(all_tags)}")
    print(f"🔍 Tags containing '0254': {[t for t in all_tags if '0254' in t]}")
    print(f"🔍 Tags containing '0255': {[t for t in all_tags if '0255' in t]}")
    print(f"🔍 Tags containing '0252': {[t for t in all_tags if '0252' in t]}")
    print(f"🔍 Tags containing '0257': {[t for t in all_tags if '0257' in t]}")

else:
    print("⚠️  No chunks with tags found")

print("\n" + "=" * 80)
print("✅ VERIFICATION COMPLETE")
print("=" * 80)
