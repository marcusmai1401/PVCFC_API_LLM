#!/usr/bin/env python3
"""
Debug script to investigate missing "Assembly Clearance Records" document.
Searches for document containing "0887" (rotor clearance value).

Usage: python scripts/utilities/debug_assembly_clearance.py
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from opensearchpy import OpenSearch


def search_doc_id_map():
    """Search doc_id_map.json for Assembly Clearance related files."""
    print("=" * 80)
    print("STEP 1: Searching doc_id_map.json for Assembly Clearance documents")
    print("=" * 80)

    # Load environment variables
    load_dotenv()

    # Load doc_id_map from ingestion_production directory
    artifacts_dir = os.getenv("ARTIFACTS_DIR", "D:\\PVCFC_Artifacts")
    # Try ingestion_production first (current location), fallback to index_production
    doc_id_map_path = Path(artifacts_dir) / "ingestion_production" / "doc_id_map.json"

    if not doc_id_map_path.exists():
        # Fallback to index_production
        index_dir = os.getenv("INDEX_DIR", f"{artifacts_dir}\\index_production")
        doc_id_map_path = Path(index_dir) / "doc_id_map.json"

    print(f"Looking for doc_id_map at: {doc_id_map_path}")

    if not doc_id_map_path.exists():
        print(f"❌ Error: doc_id_map.json not found at {doc_id_map_path}")
        return None, None

    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print(f"✅ Loaded doc_id_map with {len(doc_id_map)} documents\n")

    # Search for Assembly Clearance related files
    search_terms = ["assembly clearance", "clearance record", "0887", "kt06101"]
    matches = []

    for doc_id, doc_info in doc_id_map.items():
        # Handle both dict and string formats
        if isinstance(doc_info, dict):
            pdf_path = doc_info.get("pdf_path", "")
            file_name = doc_info.get("file_name", "")
        elif isinstance(doc_info, str):
            pdf_path = doc_info
            file_name = Path(pdf_path).name if pdf_path else ""
        else:
            continue

        # Search in file name and path
        search_text = f"{file_name} {pdf_path}".lower()

        for term in search_terms:
            if term in search_text:
                matches.append(
                    {
                        "doc_id": doc_id,
                        "file_name": file_name,
                        "pdf_path": pdf_path,
                        "matched_term": term,
                    }
                )
                break

    if matches:
        print(f"🔍 Found {len(matches)} matching document(s):\n")
        for i, match in enumerate(matches, 1):
            print(f"Match #{i}:")
            print(f"  Doc ID: {match['doc_id']}")
            print(f"  File Name: {match['file_name']}")
            print(f"  Matched Term: '{match['matched_term']}'")
            print(f"  PDF Path: {match['pdf_path']}")
            print()

        return matches[0]["doc_id"], matches[0]["file_name"]
    else:
        print("❌ No documents found matching:")
        for term in search_terms:
            print(f"  - '{term}'")
        print("\n💡 This document may not be ingested yet.")
        return None, None


def search_opensearch(doc_id, file_name):
    """Search OpenSearch for content containing '0887' in the identified document."""
    print("=" * 80)
    print(f"STEP 2: Searching OpenSearch for '0887' in document: {file_name}")
    print("=" * 80)

    # Load environment
    load_dotenv()

    # Connect to OpenSearch
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    index_name = os.getenv("OPENSEARCH_INDEX", "rag_chunks")

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=None,
        use_ssl=False,
        verify_certs=False,
        timeout=30,
    )

    # Check connection
    if not client.ping():
        print(f"❌ Cannot connect to OpenSearch at {host}:{port}")
        return

    print(f"✅ Connected to OpenSearch: {host}:{port}\n")

    # Query 1: Search for chunks with this doc_id containing "0887"
    print("Query 1: Searching for '0887' in document chunks...")
    query_0887 = {
        "size": 10,
        "query": {
            "bool": {
                "must": [{"term": {"doc_id": doc_id}}, {"match": {"text": "0887"}}]
            }
        },
        "_source": ["chunk_id", "text", "page", "doc_id"],
    }

    try:
        response = client.search(index=index_name, body=query_0887)
        hits = response["hits"]["hits"]

        if hits:
            print(f"✅ Found {len(hits)} chunk(s) containing '0887':\n")
            for i, hit in enumerate(hits, 1):
                src = hit["_source"]
                text = src.get("text", "")
                page = src.get("page", "?")
                chunk_id = src.get("chunk_id", "?")

                print(f"Chunk #{i}:")
                print(f"  Page: {page}")
                print(f"  Chunk ID: {chunk_id}")
                print(f"  Text Preview (first 200 chars):")
                print(f"    {text[:200]}...")
                print()
        else:
            print("❌ No chunks found containing '0887' in this document.\n")
            print("💡 Possible reasons:")
            print("  1. OCR failed to extract '0887' from scanned image")
            print("  2. Document is image-only without text layer")
            print("  3. Number '0887' might be handwritten or in a table")
            print()

    except Exception as e:
        print(f"❌ Query failed: {e}\n")

    # Query 2: Search for "rotor" keyword in same document
    print("Query 2: Searching for 'rotor' keyword in document...")
    query_rotor = {
        "size": 5,
        "query": {
            "bool": {
                "must": [{"term": {"doc_id": doc_id}}, {"match": {"text": "rotor"}}]
            }
        },
        "_source": ["chunk_id", "text", "page"],
    }

    try:
        response = client.search(index=index_name, body=query_rotor)
        hits = response["hits"]["hits"]

        if hits:
            print(f"✅ Found {len(hits)} chunk(s) containing 'rotor':\n")
            for i, hit in enumerate(hits, 1):
                src = hit["_source"]
                text = src.get("text", "")
                page = src.get("page", "?")

                print(f"Chunk #{i} (Page {page}):")
                print(f"  {text[:150]}...")
                print()
        else:
            print("❌ No chunks found containing 'rotor' in this document.\n")

    except Exception as e:
        print(f"❌ Query failed: {e}\n")

    # Query 3: Get total chunks count for this document
    print("Query 3: Checking total indexed chunks for this document...")
    query_total = {
        "size": 0,
        "query": {"term": {"doc_id": doc_id}},
        "aggs": {"pages": {"terms": {"field": "page", "size": 100}}},
    }

    try:
        response = client.search(index=index_name, body=query_total)
        total_chunks = response["hits"]["total"]["value"]
        pages = response["aggregations"]["pages"]["buckets"]

        print(f"✅ Total chunks indexed: {total_chunks}")
        print(f"✅ Pages covered: {len(pages)}")
        if pages:
            page_list = sorted([p["key"] for p in pages])
            print(f"   Page numbers: {page_list}")
        print()

    except Exception as e:
        print(f"❌ Query failed: {e}\n")


def analyze_alternatives():
    """Suggest alternative documents that might contain the answer."""
    print("=" * 80)
    print("STEP 3: Analyzing Alternative Documents")
    print("=" * 80)

    print("\n📋 Alternative documents that might contain clearance data:")
    print("  1. KT06101 Operating Manual (Installation/Maintenance section)")
    print("  2. KT06101 Technical Specification (Mechanical tolerances)")
    print("  3. KT06101 Datasheet (Design specifications)")
    print("  4. Compressor assembly drawings/P&IDs (CAD files)")
    print()
    print("💡 Recommendation:")
    print("  - If Assembly Clearance Records is a separate PDF, ensure it's in the")
    print("    ingestion folder and re-run the ingestion pipeline.")
    print("  - If it's a scanned document, consider:")
    print("    a) Re-scanning at higher DPI (300+)")
    print("    b) Manual OCR preprocessing")
    print("    c) Enabling Vision Always-On mode for image-based extraction")
    print()


def main():
    print("\n" + "=" * 80)
    print("🔍 DEBUG: Assembly Clearance Records Document")
    print("=" * 80)
    print("Target: Find document containing rotor clearance value '0.887 mm'")
    print("Expected: KT06101_Assembly Clearance Records")
    print("=" * 80 + "\n")

    # Step 1: Search doc_id_map
    doc_id, file_name = search_doc_id_map()

    if not doc_id:
        print("\n" + "=" * 80)
        print("❌ CONCLUSION: Document not found in index")
        print("=" * 80)
        analyze_alternatives()
        return

    # Step 2: Search OpenSearch
    search_opensearch(doc_id, file_name)

    # Step 3: Analyze
    print("=" * 80)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"✅ Document found in index: {file_name}")
    print(f"   Doc ID: {doc_id}")
    print()
    print("Next steps:")
    print("  1. Check if '0887' was found in OpenSearch results above")
    print("  2. If not found: Document likely has poor OCR quality")
    print("  3. Solution: Enable Vision mode to read numbers from images")
    print("  4. Alternative: Use Vision Page Selector to show relevant pages")
    print()


if __name__ == "__main__":
    main()
