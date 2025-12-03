import requests

# Check OpenSearch
print("Checking OpenSearch for doc_id field...")
response = requests.post(
    "http://localhost:9200/rag_chunks/_search",
    json={
        "size": 5,
        "_source": ["chunk_id", "doc_id", "page", "page_start"],
        "query": {"match_all": {}},
    },
)
data = response.json()
hits = data.get("hits", {}).get("hits", [])

print(f"Found {len(hits)} documents\n")
for i, hit in enumerate(hits, 1):
    source = hit["_source"]
    print(f"Doc {i}:")
    print(f"  chunk_id: {source.get('chunk_id')}")
    print(f"  doc_id: {source.get('doc_id')}")
    print(f"  page (root): {source.get('page')}")
    print(f"  page_start: {source.get('page_start')}")
    print()
