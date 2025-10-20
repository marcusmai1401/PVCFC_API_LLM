#!/usr/bin/env python
"""
Direct Tag Injection - Extract and inject tags into chunks in-memory
Bypass tags.jsonl intermediate file
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.orchestrator import TagExtractionOrchestrator
from app.ingestion.tags.tag_extractor import TagExtractor


def main():
    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"
    chunks_file = PROJECT_ROOT / "artifacts/ingestion_production/chunks/chunks.jsonl"

    if not chunks_file.exists():
        print(f"ERROR: Chunks file not found: {chunks_file}")
        return 1

    print("\n" + "=" * 80)
    print("DIRECT TAG INJECTION")
    print("=" * 80)
    print(f"PDF: {pdf_path}")
    print(f"Doc ID: {doc_id}")
    print(f"Chunks: {chunks_file}")
    print()

    # Step 1: Extract tags
    print("Extracting tags...")
    extractor = TagExtractor()
    layout_builder = PageLayoutBuilder()

    all_tags = []
    tags_by_page = {}

    # Extract for page 13 (as example - where "04 PU 2049" is)
    for page_num in [13]:
        layout = layout_builder.build_layout(pdf_path, page_num, doc_id)
        page_tags = extractor.extract_tags(layout)

        if page_tags:
            all_tags.extend(page_tags)
            tags_by_page[page_num] = [tag.tag for tag in page_tags]
            print(f"  Page {page_num}: {len(page_tags)} tags extracted")

    if not all_tags:
        print("No tags extracted!")
        return 1

    # Build tag lookup: (doc_id, page) -> [tags]
    tag_lookup = {}
    for tag in all_tags:
        key = (tag.doc_id, tag.page)
        if key not in tag_lookup:
            tag_lookup[key] = []
        tag_lookup[key].append(tag.tag)

    print(f"\nTotal tags: {len(all_tags)}")
    print(f"Pages with tags: {list(tags_by_page.keys())}")
    print(f"Sample tags: {tags_by_page.get(13, [])[:5]}")

    # Step 2: Update chunks
    print("\nUpdating chunks with tags...")

    chunks_updated = 0
    chunks_with_tags = 0

    updated_lines = []

    with open(chunks_file, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)

            # Check if chunk belongs to our doc
            chunk_doc_id = chunk.get("doc_id")
            chunk_page = chunk.get("page")

            if chunk_doc_id == doc_id and chunk_page in tags_by_page:
                # Add tags to metadata
                if "metadata" not in chunk:
                    chunk["metadata"] = {}

                chunk["metadata"]["tags"] = tags_by_page[chunk_page]
                chunk["metadata"]["tags_raw"] = tags_by_page[chunk_page]

                chunks_updated += 1
                if tags_by_page[chunk_page]:
                    chunks_with_tags += 1

            updated_lines.append(json.dumps(chunk, ensure_ascii=False))

    # Write updated chunks back
    print(f"  Updated {chunks_updated} chunks")
    print(f"  Chunks with tags: {chunks_with_tags}")

    with open(chunks_file, "w", encoding="utf-8") as f:
        for line in updated_lines:
            f.write(line + "\n")

    print(f"\nChunks updated: {chunks_file}")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
