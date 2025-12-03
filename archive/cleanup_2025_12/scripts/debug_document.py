"""
Debug Document Indexing Content

Purpose: Check what was actually indexed for a specific document/page
to diagnose why certain data (like numbers on charts) are missing.

Usage:
    python scripts/utilities/debug_document.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from opensearchpy import OpenSearch

# Load environment
load_dotenv()

# Configuration
DOC_ID_MAP_PATH = r"D:\PVCFC_Artifacts\ingestion_production\doc_id_map.json"
TARGET_FILENAME = "003_3N4-S4274344 Expected Performance Curve of Compressor_Rev.01.pdf"
TARGET_PAGE = 2

# OpenSearch connection
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "rag_chunks")


def find_doc_id(filename: str) -> str | None:
    """Find doc_id for a given filename in doc_id_map.json"""
    print(f"📂 Loading doc_id_map from: {DOC_ID_MAP_PATH}")

    if not Path(DOC_ID_MAP_PATH).exists():
        print(f"❌ doc_id_map.json not found at {DOC_ID_MAP_PATH}")
        return None

    with open(DOC_ID_MAP_PATH, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print(f"✓ Loaded {len(doc_id_map)} documents\n")

    # Search for matching filename
    # doc_id_map format: {doc_id: pdf_path_string}
    for doc_id, pdf_path in doc_id_map.items():
        # Extract filename from path
        path_obj = Path(pdf_path)
        current_filename = path_obj.name

        if current_filename == filename:
            print(f"✅ Found doc_id: {doc_id}")
            print(f"   Filename: {current_filename}")
            print(f"   PDF Path: {pdf_path}\n")
            return doc_id

    print(f"❌ No doc_id found for filename: {filename}\n")
    print("Available filenames:")
    for doc_id, pdf_path in list(doc_id_map.items())[:5]:
        print(f"  - {Path(pdf_path).name}")
    print(f"  ... and {len(doc_id_map) - 5} more\n")
    return None


def query_opensearch_chunks(doc_id: str, page: int) -> list:
    """Query OpenSearch for chunks belonging to specific doc_id and page"""
    print(f"🔍 Connecting to OpenSearch at {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")

    client = OpenSearch([f"http://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}"])

    # Check connection
    try:
        info = client.info()
        print(f"✓ Connected to OpenSearch {info['version']['number']}\n")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return []

    # Query for chunks
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_id": doc_id}},  # doc_id is already keyword type
                    {"term": {"page": page}},
                ]
            }
        },
        "size": 100,  # Get all chunks for this page
        "_source": ["chunk_id", "doc_id", "page", "text", "metadata"],
    }

    print(f"🔍 Querying index '{OPENSEARCH_INDEX}' for:")
    print(f"   doc_id: {doc_id}")
    print(f"   page: {page}\n")

    try:
        response = client.search(index=OPENSEARCH_INDEX, body=query)
        hits = response["hits"]["hits"]

        print(f"✅ Found {len(hits)} chunks for page {page}\n")
        return hits

    except Exception as e:
        print(f"❌ Query failed: {e}")
        return []


def analyze_chunks(hits: list, search_terms: list[str]) -> None:
    """Analyze chunk content and search for specific terms"""
    print("=" * 80)
    print("CHUNK ANALYSIS")
    print("=" * 80 + "\n")

    for i, hit in enumerate(hits, 1):
        source = hit["_source"]
        chunk_id = source.get("chunk_id", "N/A")
        text = source.get("text", "")
        metadata = source.get("metadata", {})

        print(f"📄 Chunk {i}/{len(hits)}")
        print(f"   Chunk ID: {chunk_id}")
        print(f"   Text Length: {len(text)} chars")
        print(f"   Source Format: {metadata.get('source_format', 'N/A')}")
        print(f"   OCR Applied: {metadata.get('ocr_applied', 'N/A')}")
        print(f"   Chunk Method: {metadata.get('chunk_method', 'N/A')}")
        print(f"\n   Text Content:")
        print(f"   {'─' * 76}")

        # Print first 500 chars of text
        preview = text[:500] if len(text) > 500 else text
        print(f"   {preview}")
        if len(text) > 500:
            print(f"   ... (truncated, total {len(text)} chars)")
        print(f"   {'─' * 76}\n")

        # Search for specific terms
        found_terms = []
        for term in search_terms:
            if term.lower() in text.lower():
                found_terms.append(term)

        if found_terms:
            print(f"   ✅ FOUND TERMS: {', '.join(found_terms)}\n")
        else:
            print(f"   ❌ None of the search terms found\n")

        print("─" * 80 + "\n")


def main():
    """Main execution"""
    print("\n" + "=" * 80)
    print("DOCUMENT INDEXING DEBUG TOOL")
    print("=" * 80 + "\n")

    # Step 1: Find doc_id
    doc_id = find_doc_id(TARGET_FILENAME)
    if not doc_id:
        return

    # Step 2: Query OpenSearch
    hits = query_opensearch_chunks(doc_id, TARGET_PAGE)
    if not hits:
        print("⚠️ No chunks found in OpenSearch.")
        print("\n🔍 Checking Weaviate...")

        # Try Weaviate as fallback
        import weaviate

        try:
            client = weaviate.connect_to_local()
            collection = client.collections.get("Chunk")

            result = collection.query.fetch_objects(
                filters=weaviate.classes.query.Filter.by_property("doc_id").equal(
                    doc_id
                )
                & weaviate.classes.query.Filter.by_property("page").equal(
                    float(TARGET_PAGE)
                ),
                limit=100,
            )

            if result.objects:
                print(
                    f"✅ Found {len(result.objects)} chunks in Weaviate for page {TARGET_PAGE}"
                )
                print("\n🚨 CRITICAL BUG DETECTED:")
                print("   - Document exists in Weaviate")
                print("   - Document MISSING from OpenSearch")
                print("   - Indexing script has inconsistency!\n")

                # Convert to OpenSearch-like format for analysis
                weaviate_hits = []
                for obj in result.objects:
                    weaviate_hits.append(
                        {
                            "_source": {
                                "chunk_id": obj.properties.get("chunk_id"),
                                "doc_id": obj.properties.get("doc_id"),
                                "page": obj.properties.get("page"),
                                "text": obj.properties.get("text"),
                                "metadata": obj.properties.get("metadata", {}),
                            }
                        }
                    )
                hits = weaviate_hits
            else:
                print(f"❌ Also no chunks in Weaviate for page {TARGET_PAGE}")
                print("\nPossible reasons:")
                print("  1. Page not indexed at all")
                print("  2. Page number mismatch (check if 0-indexed vs 1-indexed)")
                client.close()
                return

            client.close()
        except Exception as e:
            print(f"❌ Failed to check Weaviate: {e}")
            return

    # Step 3: Analyze chunks
    search_terms = ["17800", "17,800", "17 800", "performance", "curve"]
    analyze_chunks(hits, search_terms)

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Document: {TARGET_FILENAME}")
    print(f"Doc ID: {doc_id}")
    print(f"Page: {TARGET_PAGE}")
    print(f"Total Chunks: {len(hits)}")
    print("\n💡 DIAGNOSIS:")

    if hits:
        first_chunk = hits[0]["_source"]
        metadata = first_chunk.get("metadata", {})
        source_format = metadata.get("source_format", "N/A")
        ocr_applied = metadata.get("ocr_applied", False)

        print(f"   Source Format: {source_format}")
        print(f"   OCR Applied: {ocr_applied}")

        if source_format == "vector" and not ocr_applied:
            print("\n⚠️ POTENTIAL ISSUE DETECTED:")
            print("   - Document went through Standard Pipeline (vector text)")
            print("   - OCR was NOT applied")
            print("   - Chart numbers are likely embedded in images, not text")
            print("\n💡 RECOMMENDATION:")
            print("   1. Check if vector text length > 100 chars (bypassed OCR)")
            print("   2. If yes, increase OCR threshold or force OCR for this doc type")
            print("   3. Re-run ingestion with OCR enabled for this document")
        elif source_format == "scan" and ocr_applied:
            print("\n✅ Document was processed with OCR")
            print("   If numbers still missing, check OCR quality/settings")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
