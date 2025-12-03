"""
Tìm tài liệu Ammonia thực sự trong OpenSearch
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.rag.indexers.opensearch_bm25_retriever import OpenSearchBM25Retriever


def find_ammonia_docs():
    """Tìm tất cả tài liệu có 'Ammonia' hoặc '04000' trong doc_id"""

    retriever = OpenSearchBM25Retriever(
        host=settings.opensearch_host,
        port=settings.opensearch_port,
        index_name=settings.opensearch_index,
    )
    client = retriever.client

    # Query 1: Tìm doc_id chứa "Ammonia"
    print("\n[Query 1] Documents containing 'Ammonia' in doc_id:")
    query1 = {
        "query": {"wildcard": {"metadata.doc_id.keyword": "*Ammonia*"}},
        "size": 0,
        "aggs": {
            "unique_docs": {"terms": {"field": "metadata.doc_id.keyword", "size": 20}}
        },
    }

    try:
        response = client.search(index=retriever.index_name, body=query1)
        buckets = response["aggregations"]["unique_docs"]["buckets"]

        if buckets:
            for bucket in buckets:
                doc_id = bucket["key"]
                count = bucket["doc_count"]
                print(f"  {doc_id}")
                print(f"    Chunks: {count}")
        else:
            print("  No documents found")
    except Exception as e:
        print(f"  Error: {e}")

    # Query 2: Tìm doc_id chứa "04000"
    print("\n[Query 2] Documents containing '04000' in doc_id:")
    query2 = {
        "query": {"wildcard": {"metadata.doc_id.keyword": "*04000*"}},
        "size": 0,
        "aggs": {
            "unique_docs": {"terms": {"field": "metadata.doc_id.keyword", "size": 20}}
        },
    }

    try:
        response = client.search(index=retriever.index_name, body=query2)
        buckets = response["aggregations"]["unique_docs"]["buckets"]

        if buckets:
            for bucket in buckets:
                doc_id = bucket["key"]
                count = bucket["doc_count"]
                print(f"  {doc_id}")
                print(f"    Chunks: {count}")
        else:
            print("  No documents found")
    except Exception as e:
        print(f"  Error: {e}")

    # Query 3: Tìm chunks chứa "04 FIC 5041"
    print("\n[Query 3] Chunks containing '04 FIC 5041':")
    query3 = {
        "query": {"match_phrase": {"text": "04 FIC 5041"}},
        "size": 5,
        "_source": ["metadata.doc_id", "metadata.page_start", "chunk_id"],
    }

    try:
        response = client.search(index=retriever.index_name, body=query3)
        hits = response["hits"]["hits"]

        if hits:
            for hit in hits:
                src = hit["_source"]
                print(f"  Doc: {src.get('metadata', {}).get('doc_id', 'unknown')}")
                print(f"  Page: {src.get('metadata', {}).get('page_start')}")
                print(f"  Chunk: {src.get('chunk_id', 'unknown')[:50]}...")
                print()
        else:
            print("  No chunks found")
    except Exception as e:
        print(f"  Error: {e}")

    # Query 4: List ALL doc_ids in index
    print("\n[Query 4] All documents in index (first 50):")
    query4 = {
        "size": 0,
        "aggs": {
            "unique_docs": {"terms": {"field": "metadata.doc_id.keyword", "size": 50}}
        },
    }

    try:
        response = client.search(index=retriever.index_name, body=query4)
        buckets = response["aggregations"]["unique_docs"]["buckets"]
        total_chunks = response["hits"]["total"]["value"]

        print(f"  Total chunks in index: {total_chunks}")
        print(f"  Total unique documents: {len(buckets)}")
        print(f"\n  Documents:")
        for i, bucket in enumerate(buckets, 1):
            doc_id = bucket["key"]
            count = bucket["doc_count"]
            # Abbreviate long doc_ids
            abbrev = doc_id if len(doc_id) <= 70 else doc_id[:67] + "..."
            print(f"  [{i}] {abbrev} ({count} chunks)")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    find_ammonia_docs()
