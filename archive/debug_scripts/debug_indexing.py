"""Debug why tag is not getting indexed"""
import time

from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    ssl_assert_hostname=False,
    ssl_show_warn=False,
)

index_name = "pvcfc_pid_tags"

# Try direct index
print("Testing direct indexing of 04 TXI 2077...")

test_doc = {
    "doc_id": "Ammonia",
    "page": 17,
    "tag_text": "04 TXI 2077",
    "tag_parts": {"unit": "04", "prefix": "TXI", "suffix": "2077", "variant": None},
    "confidence": 0.85,
    "bbox": [474.33, 460.32, 487.44, 471.33],
    "chunk_id": "Ammonia_page17_tag_04_TXI_2077",
}

# Index directly
response = client.index(
    index=index_name, body=test_doc, refresh="wait_for"  # Wait for refresh
)

print(f"Index response: {response['result']}")
print(f"Document ID: {response['_id']}")

# Wait a bit
time.sleep(1)

# Search for it
print("\nSearching for tag...")
search_response = client.search(
    index=index_name,
    body={
        "query": {
            "bool": {
                "must": [
                    {"term": {"tag_parts.unit": "04"}},
                    {"term": {"tag_parts.prefix": "TXI"}},
                    {"term": {"tag_parts.suffix": "2077"}},
                ]
            }
        }
    },
)

print(f"Search hits: {search_response['hits']['total']['value']}")

if search_response["hits"]["total"]["value"] > 0:
    print("✓ Tag found after direct indexing!")
    for hit in search_response["hits"]["hits"]:
        src = hit["_source"]
        print(f"  {src['tag_text']} on page {src['page']}")
else:
    print("✗ Tag still not found")

    # Try match query
    print("\nTrying match query...")
    match_response = client.search(
        index=index_name, body={"query": {"match": {"tag_text": "04 TXI 2077"}}}
    )
    print(f"Match hits: {match_response['hits']['total']['value']}")
