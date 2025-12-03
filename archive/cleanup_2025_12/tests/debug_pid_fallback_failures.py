"""
Script kiểm tra và thống kê nguyên nhân P&ID fallback sai

Kiểm tra:
1. doc_id distribution ở mỗi step (OS/WV/RRF/BGE)
2. Biến thể tag trong text tại trang đúng
3. Match reason của Tag Reranker top-10
4. Phân bố page vs page_start/page_end
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import re
from collections import Counter, defaultdict

from app.core.config import settings
from app.rag.indexers.opensearch_bm25_retriever import OpenSearchBM25Retriever
from app.rag.rerankers.pid_tag_reranker import PIDTagReranker
from app.rag.weaviate_retriever import WeaviateRetriever, WeaviateSearchConfig


def analyze_doc_id_distribution(results, step_name):
    """Phân tích phân bố doc_id"""
    doc_ids = []
    for r in results:
        if hasattr(r, "metadata") and r.metadata:
            doc_id = r.metadata.get("doc_id", "unknown")
        elif isinstance(r, dict):
            doc_id = r.get("metadata", {}).get("doc_id", "unknown")
        else:
            doc_id = "unknown"
        doc_ids.append(doc_id)

    counter = Counter(doc_ids)
    print(f"\n{step_name} - Doc ID Distribution:")
    print(f"  Total: {len(results)} results")
    for doc_id, count in counter.most_common(5):
        abbrev = doc_id[:60] + "..." if len(doc_id) > 60 else doc_id
        print(f"  {abbrev}: {count} ({count/len(results)*100:.1f}%)")

    return counter


def analyze_page_fields(results, step_name):
    """Phân tích phân bố page vs page_start/page_end"""
    has_page = 0
    has_page_start = 0
    both = 0
    neither = 0

    for r in results:
        r_page = getattr(r, "page", None) if hasattr(r, "page") else None

        if hasattr(r, "metadata") and r.metadata:
            page_start = r.metadata.get("page_start")
        elif isinstance(r, dict):
            page_start = r.get("metadata", {}).get("page_start")
        else:
            page_start = None

        if r_page and page_start:
            both += 1
        elif r_page:
            has_page += 1
        elif page_start:
            has_page_start += 1
        else:
            neither += 1

    total = len(results)
    print(f"\n{step_name} - Page Field Distribution:")
    print(f"  Both page & page_start: {both} ({both/total*100:.1f}%)")
    print(f"  Only page: {has_page} ({has_page/total*100:.1f}%)")
    print(f"  Only page_start: {has_page_start} ({has_page_start/total*100:.1f}%)")
    print(f"  Neither: {neither} ({neither/total*100:.1f}%)")


def check_tag_variants_in_text(opensearch_retriever, tag, correct_page, doc_id):
    """Kiểm tra biến thể tag trong text tại trang đúng"""
    print(f"\n=== Checking tag variants for '{tag}' on page {correct_page} ===")

    # Tìm chunks của trang đúng
    from opensearchpy import OpenSearch

    client = opensearch_retriever.client

    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.doc_id.keyword": doc_id}},
                    {"term": {"metadata.page_start": correct_page}},
                ]
            }
        },
        "size": 10,
    }

    try:
        response = client.search(index=opensearch_retriever.index_name, body=query)
        chunks = response["hits"]["hits"]

        if not chunks:
            print(
                f"  ⚠️  No chunks found for page {correct_page} in doc {doc_id[:40]}..."
            )
            return

        print(f"  Found {len(chunks)} chunks on page {correct_page}")

        # Tách tag thành các phần
        parts = tag.split()
        if len(parts) >= 2:
            unit = parts[0]
            prefix = parts[1]
            suffix = parts[2] if len(parts) > 2 else ""
        else:
            print(f"  ⚠️  Cannot parse tag: {tag}")
            return

        # Các biến thể cần tìm
        variants = [
            f"{unit} {prefix} {suffix}",
            f"{unit}{prefix}{suffix}",
            f"{unit}-{prefix}-{suffix}",
            f"{unit} {prefix}-{suffix}",
            f"{unit}-{prefix} {suffix}",
            f"{prefix} {suffix}",
            f"{prefix}-{suffix}",
            f"{prefix}{suffix}",
        ]

        found_variants = []
        for chunk in chunks:
            text = chunk["_source"].get("text", "").upper()
            for variant in variants:
                if variant.upper() in text:
                    found_variants.append(variant)

        if found_variants:
            print(f"  ✓ Found variants in text: {set(found_variants)}")
        else:
            print(f"  ✗ No exact variants found. Checking partial matches...")
            # Kiểm tra từng phần
            for chunk in chunks:
                text = chunk["_source"].get("text", "").upper()
                has_unit = unit.upper() in text
                has_prefix = prefix.upper() in text
                has_suffix = suffix.upper() in text
                if has_unit or has_prefix or has_suffix:
                    print(
                        f"    Partial: unit={has_unit}, prefix={has_prefix}, suffix={has_suffix}"
                    )
                    print(f"    Text snippet: {text[:200]}...")
                    break

    except Exception as e:
        print(f"  ✗ Error: {e}")


def analyze_tag_rerank_matches(reranker, results, query_tags, top_k=10):
    """Phân tích match reason của Tag Reranker"""
    print(f"\n=== Tag Reranker Match Analysis (Top {top_k}) ===")

    # Convert to dict format
    results_dicts = []
    for r in results[:top_k]:
        if isinstance(r, dict):
            results_dicts.append(r)
        else:
            results_dicts.append(
                {
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "score": r.score,
                    "metadata": r.metadata,
                }
            )

    # Manually check matches (simplified version of reranker logic)
    for i, result in enumerate(results_dicts):
        text_upper = result["text"].upper()
        metadata = result.get("metadata", {})
        metadata_tags_upper = [t.upper() for t in metadata.get("tags", [])]

        matches = []
        for query_tag in query_tags:
            query_upper = query_tag.upper()

            # Check metadata exact
            if query_upper in metadata_tags_upper:
                matches.append(f"meta_exact:{query_tag}")
            # Check text exact
            elif query_upper in text_upper:
                matches.append(f"text_exact:{query_tag}")
            # Check proximity (simplified - just check if all parts present)
            else:
                parts = query_tag.split()
                if len(parts) >= 2 and all(p.upper() in text_upper for p in parts):
                    matches.append(f"proximity:{query_tag}")

        print(f"  Rank {i+1}: {matches if matches else ['no_match']}")
        if matches:
            # Show snippet
            snippet = result["text"][:100].replace("\n", " ")
            print(f"    Snippet: {snippet}...")


async def test_query(query_text, tag, correct_page, doc_id_hint):
    """Test một query và phân tích"""
    print("\n" + "=" * 80)
    print(f"TESTING: {query_text}")
    print(f"Expected: Page {correct_page}")
    print("=" * 80)

    # Initialize components
    opensearch_retriever = OpenSearchBM25Retriever(
        host=settings.opensearch_host,
        port=settings.opensearch_port,
        index_name=settings.opensearch_index,
    )

    weaviate_retriever = WeaviateRetriever()

    # Step 1: Generate variants
    parts = tag.split()
    variants = [tag]
    if len(parts) >= 2:
        variants.append("".join(parts))
        variants.append("-".join(parts))
        if len(parts) > 2:
            variants.append(f"{parts[1]} {parts[2]}")

    print(f"\nStep 1: Tag variants: {variants}")

    # Step 2: OpenSearch tag-boosted
    print("\nStep 2: OpenSearch tag-boosted search...")
    os_results = opensearch_retriever.search_with_tag_boosting(
        query=query_text, detected_tags=variants, top_k=50
    )
    analyze_doc_id_distribution(os_results, "OpenSearch")
    analyze_page_fields(os_results, "OpenSearch")

    # Step 3: Weaviate semantic
    print("\nStep 3: Weaviate semantic search...")
    from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery

    # Create TransformedQuery object
    transformed = TransformedQuery(
        original=query_text,
        normalized=query_text.lower(),
        intent=QueryIntent.ASK,
        filters=QueryFilters(),
    )

    wv_config = WeaviateSearchConfig(
        retrieval_limit=50,
        top_k_final=50,
        enable_bge_rerank=False,
    )
    wv_results = weaviate_retriever.search(transformed, config_override=wv_config)
    analyze_doc_id_distribution(wv_results, "Weaviate")
    analyze_page_fields(wv_results, "Weaviate")

    # Step 4: Would be RRF fusion (skip for now, just analyze inputs)

    # Step 5: Tag Reranking analysis
    print("\nStep 5: Tag Reranking Match Analysis...")
    tag_reranker = PIDTagReranker()
    # Use combined results for analysis
    combined = os_results[:30] + wv_results[:30]
    analyze_tag_rerank_matches(tag_reranker, combined, variants, top_k=10)

    # Check tag variants in correct page
    check_tag_variants_in_text(opensearch_retriever, tag, correct_page, doc_id_hint)


async def main():
    """Main test runner"""
    test_cases = [
        {
            "query": "Tìm cho tôi tag name 04 FIC 5041 nằm ở đâu trong bản vẽ P&ID của cụm Amo",
            "tag": "04 FIC 5041",
            "correct_page": 65,
            "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
        },
        {
            "query": "Tìm cho tôi tag name 04 HV 5501 nằm ở đâu trong bản vẽ P&ID của cụm Amo",
            "tag": "04 HV 5501",
            "correct_page": 55,
            "doc_id": "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b",
        },
    ]

    for tc in test_cases:
        await test_query(tc["query"], tc["tag"], tc["correct_page"], tc["doc_id"])
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
