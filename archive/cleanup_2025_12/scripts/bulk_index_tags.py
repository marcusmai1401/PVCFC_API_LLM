#!/usr/bin/env python
"""
Bulk Index Tags to OpenSearch
Extract tags from P&ID and bulk index them
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from opensearchpy import OpenSearch, helpers

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor


def main():
    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"

    print("\n" + "=" * 80)
    print("BULK INDEX TAGS TO OPENSEARCH")
    print("=" * 80)
    print(f"PDF: {pdf_path.name}")
    print(f"Doc ID: {doc_id}")
    print()

    # Extract tags
    print("Extracting tags...")
    extractor = TagExtractor()
    layout_builder = PageLayoutBuilder()

    all_tags = []

    # Extract ALL pages (full document)
    import fitz

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    print(f"Processing {total_pages} pages...")

    for page_num in range(
        1, min(total_pages + 1, 120)
    ):  # Limit to first 120 pages for speed
        try:
            layout = layout_builder.build_layout(pdf_path, page_num, doc_id)
            page_tags = extractor.extract_tags(layout)

            if page_tags:
                all_tags.extend(page_tags)
                print(f"  Page {page_num}: {len(page_tags)} tags")
        except Exception as e:
            print(f"  Page {page_num}: ERROR - {e}")

    if not all_tags:
        print("\nNo tags extracted!")
        return 1

    print(f"\nTotal tags extracted: {len(all_tags)}")

    # Connect to OpenSearch
    print("\nConnecting to OpenSearch...")
    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,
    )

    # Prepare bulk actions
    print("Preparing bulk index actions...")
    actions = []

    # Debug: Check first 5 tags
    print("\n" + "=" * 80)
    print("DEBUG: First 5 tags page numbers")
    print("=" * 80)
    for i, tag in enumerate(all_tags[:5]):
        print(f"Tag {i+1}: {tag.tag} -> page={tag.page} (type: {type(tag.page)})")

    # Find PU 2049 tags specifically
    pu_2049_tags = [t for t in all_tags if "PU" in t.tag and "2049" in t.tag]
    if pu_2049_tags:
        print("\n" + "=" * 80)
        print("DEBUG: PU 2049 tags found")
        print("=" * 80)
        for tag in pu_2049_tags:
            print(f"  Tag: {tag.tag} -> page={tag.page}")

    for tag in all_tags:
        # Create unique ID for tag
        tag_id = f"{tag.doc_id}_p{tag.page}_{tag.tag.replace(' ', '_')}"

        # DEBUG: Log if page is 0 or None
        if tag.page is None or tag.page == 0:
            print(f"⚠️  WARNING: Tag '{tag.tag}' has invalid page={tag.page}")

        action = {
            "_op_type": "index",
            "_index": "rag_chunks",  # Index to main chunks index
            "_id": f"TAG_{tag_id}",
            "_source": {
                "chunk_id": f"TAG_{tag_id}",
                "doc_id": tag.doc_id,
                "page": tag.page if tag.page else 1,  # Fallback to 1 if None/0
                "text": f"Equipment tag: {tag.tag}",
                "is_tag_entity": True,  # Top-level field for easy filtering
                "metadata": {
                    "tags": [tag.tag],
                    "tags_raw": [tag.tag],
                    "tag_parts": {
                        "area": tag.parts.area,
                        "code": tag.parts.code,
                        "num": tag.parts.num,
                        "suffix": tag.parts.suffix,
                    },
                    "page": tag.page if tag.page else 1,  # Also in metadata
                },
            },
        }
        actions.append(action)

    # Bulk index
    print(f"Bulk indexing {len(actions)} tags to OpenSearch...")

    success, errors = helpers.bulk(client, actions, raise_on_error=False)

    print(f"\n{'=' * 80}")
    print("INDEXING COMPLETE")
    print(f"{'=' * 80}")
    print(f"Success: {success}")
    print(f"Errors: {len(errors) if errors else 0}")

    if errors:
        print("\nFirst 3 errors:")
        for err in errors[:3]:
            print(f"  {err}")

    # Verify
    print("\nVerifying indexed tags...")

    result = client.search(
        index="rag_chunks",
        body={
            "query": {"term": {"is_tag_entity": True}},  # Top-level field
            "size": 0,
        },
    )

    tag_count = result["hits"]["total"]["value"]
    print(f"Total tag entities in index: {tag_count}")

    # Search for "04 PU 2049"
    result = client.search(
        index="rag_chunks",
        body={
            "query": {"match": {"metadata.tags": "04 PU 2049"}},
            "size": 1,
        },
    )

    if result["hits"]["total"]["value"] > 0:
        print("\n✅ Found '04 PU 2049' in index!")
        hit = result["hits"]["hits"][0]
        print(f"   Tag: {hit['_source']['metadata']['tags']}")
        print(f"   Page: {hit['_source']['page']}")
    else:
        print("\n⚠️  '04 PU 2049' not found in index")

    print(f"\n{'=' * 80}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
