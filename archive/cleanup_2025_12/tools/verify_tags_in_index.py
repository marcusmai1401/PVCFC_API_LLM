"""
Verify that tags were extracted and indexed for a given document.
"""
import sys
from typing import List

try:
    from opensearchpy import OpenSearch
except Exception:
    print("❌ opensearchpy not installed. Run: pip install opensearch-py")
    sys.exit(1)

INDEX = "rag_chunks"
DOC_ID_CONTAINS = "Instrument_116_3N4-S4275354"
TARGET_TAGS: List[str] = ["06-TE-0256", "06 TE 0256", "06TE0256"]


def main():
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=30,
    )

    # Fetch chunks for doc
    body = {
        "query": {"bool": {"must": [{"wildcard": {"doc_id": f"*{DOC_ID_CONTAINS}*"}}]}},
        "size": 100,
        "_source": [
            "doc_id",
            "page",
            "text",
            "tags",
            "tags_raw",
            "metadata",
            "chunk_id",
        ],
    }

    resp = client.search(index=INDEX, body=body)
    hits = resp.get("hits", {}).get("hits", [])
    print(f"Found {len(hits)} chunks for document filter '{DOC_ID_CONTAINS}'\n")

    # Check tags presence
    total_with_tags = 0
    for h in hits:
        src = h["_source"]
        page = src.get("page") or src.get("metadata", {}).get("page")
        tags = src.get("tags", [])
        if tags:
            total_with_tags += 1
        if page in [4, 5, 6] or any(
            t.replace("-", " ") in src.get("text", "").replace("-", " ")
            for t in TARGET_TAGS
        ):
            print(
                f"Page {page}: tags={tags} | sample='{src.get('text','')[:150]}...'\n"
            )

    print(f"Summary: {total_with_tags}/{len(hits)} chunks have 'tags' field populated")


if __name__ == "__main__":
    sys.exit(main())
