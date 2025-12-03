"""
Script kiểm tra chi tiết tại sao trang 65 và 55 không tìm thấy trong database

Kiểm tra:
1. Trang có tồn tại trong OpenSearch không (không filter page)
2. Nếu có, page_start/page_end là gì
3. Nếu không có, kiểm tra các trang lân cận
4. Kiểm tra trong Weaviate
5. So sánh với spatial search cache
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.rag.indexers.opensearch_bm25_retriever import OpenSearchBM25Retriever


def investigate_opensearch(doc_id, target_page, tag):
    """Kiểm tra OpenSearch chi tiết"""
    print(f"\n{'='*80}")
    print(f"INVESTIGATING: Page {target_page} with tag '{tag}'")
    print(f"Doc ID: {doc_id[:60]}...")
    print(f"{'='*80}")

    retriever = OpenSearchBM25Retriever(
        host=settings.opensearch_host,
        port=settings.opensearch_port,
        index_name=settings.opensearch_index,
    )
    client = retriever.client

    # Test 1: Query theo page_start chính xác
    print(f"\n[Test 1] Query by exact page_start={target_page}")
    query1 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.doc_id.keyword": doc_id}},
                    {"term": {"metadata.page_start": target_page}},
                ]
            }
        },
        "size": 10,
    }

    try:
        response = client.search(index=retriever.index_name, body=query1)
        hits = response["hits"]["hits"]
        print(f"  Found: {len(hits)} chunks")

        if hits:
            for i, hit in enumerate(hits[:3]):
                src = hit["_source"]
                print(f"  [{i+1}] chunk_id: {src.get('chunk_id', 'unknown')[:50]}...")
                print(f"      page_start: {src.get('metadata', {}).get('page_start')}")
                print(f"      page_end: {src.get('metadata', {}).get('page_end')}")
                print(f"      text preview: {src.get('text', '')[:100]}...")
        else:
            print(f"  ⚠️  No chunks found with page_start={target_page}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # Test 2: Query theo text của tag (không filter page)
    print(f"\n[Test 2] Query by tag text '{tag}' (no page filter)")
    query2 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.doc_id.keyword": doc_id}},
                    {"match_phrase": {"text": tag}},
                ]
            }
        },
        "size": 10,
    }

    try:
        response = client.search(index=retriever.index_name, body=query2)
        hits = response["hits"]["hits"]
        print(f"  Found: {len(hits)} chunks containing '{tag}'")

        if hits:
            pages_found = set()
            for i, hit in enumerate(hits[:5]):
                src = hit["_source"]
                page_start = src.get("metadata", {}).get("page_start")
                page_end = src.get("metadata", {}).get("page_end")
                pages_found.add(page_start)

                print(f"  [{i+1}] page_start={page_start}, page_end={page_end}")
                print(f"      chunk_id: {src.get('chunk_id', 'unknown')[:50]}...")
                # Highlight tag in text
                text = src.get("text", "")
                idx = text.upper().find(tag.upper())
                if idx >= 0:
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(tag) + 50)
                    snippet = text[start:end]
                    print(f"      ...{snippet}...")

            print(f"\n  Summary: Tag found on pages: {sorted(pages_found)}")
            if target_page not in pages_found:
                print(f"  ⚠️  Target page {target_page} NOT in list!")
        else:
            print(f"  ✗ No chunks found containing '{tag}' in this document")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # Test 3: Query các trang lân cận (target_page ± 2)
    print(f"\n[Test 3] Query nearby pages ({target_page-2} to {target_page+2})")
    nearby_pages = range(max(1, target_page - 2), target_page + 3)
    query3 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.doc_id.keyword": doc_id}},
                    {"terms": {"metadata.page_start": list(nearby_pages)}},
                ]
            }
        },
        "size": 50,
        "sort": [{"metadata.page_start": "asc"}],
    }

    try:
        response = client.search(index=retriever.index_name, body=query3)
        hits = response["hits"]["hits"]
        print(f"  Found: {len(hits)} chunks in pages {target_page-2}-{target_page+2}")

        page_counts = {}
        for hit in hits:
            page = hit["_source"].get("metadata", {}).get("page_start")
            page_counts[page] = page_counts.get(page, 0) + 1

        print(f"  Page distribution:")
        for page in sorted(page_counts.keys()):
            marker = " ← TARGET" if page == target_page else ""
            print(f"    Page {page}: {page_counts[page]} chunks{marker}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # Test 4: Query toàn bộ document để xem page range
    print(f"\n[Test 4] Document page range analysis")
    query4 = {
        "query": {"term": {"metadata.doc_id.keyword": doc_id}},
        "size": 0,
        "aggs": {
            "page_start_stats": {"stats": {"field": "metadata.page_start"}},
            "page_end_stats": {"stats": {"field": "metadata.page_end"}},
        },
    }

    try:
        response = client.search(index=retriever.index_name, body=query4)
        page_start_stats = response["aggregations"]["page_start_stats"]
        page_end_stats = response["aggregations"]["page_end_stats"]

        print(f"  Total chunks in document: {response['hits']['total']['value']}")
        print(
            f"  page_start range: {page_start_stats.get('min')} - {page_start_stats.get('max')}"
        )
        print(
            f"  page_end range: {page_end_stats.get('min')} - {page_end_stats.get('max')}"
        )

        if page_start_stats.get("max", 0) < target_page:
            print(f"  ⚠️  Target page {target_page} EXCEEDS max indexed page!")
        elif page_start_stats.get("min", 999) > target_page:
            print(f"  ⚠️  Target page {target_page} BELOW min indexed page!")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # Test 5: Kiểm tra spatial search cache có page này không
    print(f"\n[Test 5] Check if page exists in spatial search cache")
    try:
        from app.rag.spatial.spatial_index_manager import SpatialIndexManager

        manager = SpatialIndexManager()
        doc_short_id = doc_id.split("_")[-1]  # Get hash part

        # Try to load index
        cache_file = f"artifacts/spatial_cache/{doc_short_id}_spatial_index.pkl"
        if os.path.exists(cache_file):
            print(f"  ✓ Spatial cache exists: {cache_file}")
            import pickle

            with open(cache_file, "rb") as f:
                spatial_data = pickle.load(f)

            # Check if target page in cache
            pages_in_cache = set()
            if isinstance(spatial_data, dict) and "pages" in spatial_data:
                pages_in_cache = set(spatial_data["pages"].keys())

            print(f"  Pages in spatial cache: {sorted(list(pages_in_cache))[:20]}...")
            print(f"  Total pages: {len(pages_in_cache)}")

            if target_page in pages_in_cache:
                print(f"  ✓ Page {target_page} EXISTS in spatial cache")
                # Show tags on this page
                page_data = spatial_data["pages"].get(target_page, {})
                if "tags" in page_data:
                    tags_on_page = [t.get("text", "") for t in page_data["tags"][:10]]
                    print(f"  Tags on page {target_page}: {tags_on_page}")
            else:
                print(f"  ✗ Page {target_page} NOT in spatial cache")
        else:
            print(f"  ⚠️  Spatial cache file not found: {cache_file}")
    except Exception as e:
        print(f"  ✗ Error checking spatial cache: {e}")


def main():
    """Main investigation"""
    test_cases = [
        {
            "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
            "target_page": 65,
            "tag": "04 FIC 5041",
        },
        {
            "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
            "target_page": 55,
            "tag": "04 HV 5501",
        },
    ]

    for tc in test_cases:
        investigate_opensearch(tc["doc_id"], tc["target_page"], tc["tag"])
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
