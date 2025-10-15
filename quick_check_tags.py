"""Quick check for tags in OpenSearch"""
from opensearchpy import OpenSearch

c = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)

# Check all chunks with tags field
r = c.search(
    index="rag_chunks",
    body={
        "query": {"bool": {"must": [{"exists": {"field": "tags"}}]}},
        "size": 10,
        "_source": ["doc_id", "page", "tags", "file_name"],
    },
)

total = r["hits"]["total"]["value"]
print(f"✅ Total chunks with 'tags' field: {total}\n")

if total > 0:
    print("📋 Sample chunks:\n")
    for hit in r["hits"]["hits"][:5]:
        src = hit["_source"]
        doc_id = src.get("doc_id", "")
        page = src.get("page", "N/A")
        tags = src.get("tags", [])
        file_name = src.get("file_name", "N/A")

        print(f"  Doc: {file_name}")
        print(f"  Page: {page}, Tags: {len(tags)}")
        print(f"  Sample tags: {tags[:5]}")
        print()
else:
    print("❌ No chunks with tags found in index")
    print("\nPossible reasons:")
    print("  1. Index was not refreshed properly")
    print("  2. Chunks were indexed without tags field")
    print("  3. Mapping doesn't support tags field")
