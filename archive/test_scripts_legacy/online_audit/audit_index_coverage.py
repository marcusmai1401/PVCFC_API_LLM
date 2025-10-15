"""
Audit Index Coverage for Golden Pages

Checks if the expected pages from golden dataset are actually indexed in BM25/FAISS.

This is CRITICAL: if the correct pages aren't in the index, retrieval can't find them!
"""

import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_bm25_index():
    """Load BM25 metadata"""
    metadata_path = Path("artifacts/index/bm25/metadata.json")

    if not metadata_path.exists():
        print(f"ERROR: BM25 metadata not found at {metadata_path}")
        return None

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadatas = json.load(f)

    print(f"* Loaded BM25 metadata: {len(metadatas)} chunks")
    return {"documents": metadatas}  # Use metadata as documents for page checking


def load_faiss_metadata():
    """Load FAISS metadata"""
    metadata_path = Path("artifacts/index/faiss/metadatas.json")

    if not metadata_path.exists():
        print(f"ERROR: FAISS metadata not found at {metadata_path}")
        return None

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadatas = json.load(f)

    print(f"* Loaded FAISS metadata: {len(metadatas)} vectors")

    # Load texts to build full doc objects
    texts_path = Path("artifacts/index/faiss/texts.json")
    with open(texts_path, "r", encoding="utf-8") as f:
        texts = json.load(f)

    # Combine into documents
    documents = []
    for i, (text, metadata) in enumerate(zip(texts, metadatas)):
        documents.append(
            {
                "text": text,
                "metadata": metadata,
            }
        )

    return documents


def check_page_coverage(
    doc_id_pattern: str, expected_page: int, bm25_data: Dict, faiss_docs: List
):
    """Check if expected page exists in indices"""

    coverage = {
        "doc_id_pattern": doc_id_pattern,
        "expected_page": expected_page,
        "bm25_found": False,
        "faiss_found": False,
        "bm25_pages_for_doc": [],
        "faiss_pages_for_doc": [],
        "bm25_match_count": 0,
        "faiss_match_count": 0,
    }

    # Check BM25
    for doc in bm25_data["documents"]:
        metadata = doc.get("metadata", {})
        doc_id = metadata.get("doc_id", "")

        # Match doc_id pattern
        import re

        if re.search(doc_id_pattern, doc_id, re.IGNORECASE):
            page = metadata.get("page") or metadata.get("page_start", 1)
            coverage["bm25_pages_for_doc"].append(page)
            coverage["bm25_match_count"] += 1

            if page == expected_page:
                coverage["bm25_found"] = True

    # Check FAISS
    for doc in faiss_docs:
        metadata = doc.get("metadata", {})
        doc_id = metadata.get("doc_id", "")

        import re

        if re.search(doc_id_pattern, doc_id, re.IGNORECASE):
            page = metadata.get("page") or metadata.get("page_start", 1)
            coverage["faiss_pages_for_doc"].append(page)
            coverage["faiss_match_count"] += 1

            if page == expected_page:
                coverage["faiss_found"] = True

    # Get unique pages
    coverage["bm25_unique_pages"] = sorted(set(coverage["bm25_pages_for_doc"]))
    coverage["faiss_unique_pages"] = sorted(set(coverage["faiss_pages_for_doc"]))

    return coverage


def main():
    # Load golden dataset
    dataset_path = Path(
        "scripts/test_scripts/online_audit/golden_citation_dataset.json"
    )
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # Load indices
    print("Loading indices...")
    bm25_data = load_bm25_index()
    faiss_docs = load_faiss_metadata()

    if not bm25_data or not faiss_docs:
        print("ERROR: Cannot load indices")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("INDEX COVERAGE AUDIT")
    print("=" * 80)

    results = []

    for question in dataset["questions"]:
        q_id = question["id"]
        gt = question["ground_truth"]

        print(f"\n[{q_id}]")
        print(f"  Expected: {gt['file_name']}, page {gt['page']}")

        coverage = check_page_coverage(
            gt["doc_id_pattern"], gt["page"], bm25_data, faiss_docs
        )

        results.append(
            {
                "question_id": q_id,
                "coverage": coverage,
            }
        )

        # Print results
        print(f"  BM25:")
        print(f"    Chunks for this doc: {coverage['bm25_match_count']}")
        print(
            f"    Unique pages: {coverage['bm25_unique_pages'][:10]}"
            + ("..." if len(coverage["bm25_unique_pages"]) > 10 else "")
        )
        print(
            f"    Page {gt['page']} indexed: {'YES' if coverage['bm25_found'] else 'NO'}"
        )

        print(f"  FAISS:")
        print(f"    Vectors for this doc: {coverage['faiss_match_count']}")
        print(
            f"    Unique pages: {coverage['faiss_unique_pages'][:10]}"
            + ("..." if len(coverage["faiss_unique_pages"]) > 10 else "")
        )
        print(
            f"    Page {gt['page']} indexed: {'YES' if coverage['faiss_found'] else 'NO'}"
        )

        if not coverage["bm25_found"] and not coverage["faiss_found"]:
            print(f"  *** CRITICAL: Expected page {gt['page']} NOT IN INDEX ***")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    total = len(results)
    bm25_found = sum(1 for r in results if r["coverage"]["bm25_found"])
    faiss_found = sum(1 for r in results if r["coverage"]["faiss_found"])
    either_found = sum(
        1
        for r in results
        if r["coverage"]["bm25_found"] or r["coverage"]["faiss_found"]
    )

    print(f"\nExpected pages in index:")
    print(f"  BM25: {bm25_found}/{total} ({bm25_found/total:.0%})")
    print(f"  FAISS: {faiss_found}/{total} ({faiss_found/total:.0%})")
    print(f"  Either: {either_found}/{total} ({either_found/total:.0%})")

    if either_found < total:
        print(
            f"\n! CRITICAL FINDING: {total - either_found} expected pages are MISSING from indices!"
        )
        print(f"  This explains why retrieval cannot find them.")

    # Save results
    output_file = Path("reports/test_results/index_coverage_audit.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n* Results saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
