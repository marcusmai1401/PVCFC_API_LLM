#!/usr/bin/env python
"""
Simple Tag Extraction Script
Extracts tags from PDF and saves directly to production entities dir
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.tags.orchestrator import TagExtractionOrchestrator


def main():
    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_27bfb26b"  # Match existing doc_id in index

    print("\n" + "=" * 80)
    print("TAG EXTRACTION - SIMPLE")
    print("=" * 80)
    print(f"PDF: {pdf_path}")
    print(f"Doc ID: {doc_id}")
    print()

    # Initialize orchestrator
    orchestrator = TagExtractionOrchestrator(
        enable_crops=False,
        lazy_crops=True,
    )

    if not orchestrator.enabled:
        print("ERROR: Tag extraction is disabled!")
        print("Enable with: ENABLE_PID_TAGS=true in .env")
        return 1

    # Process document
    print("Processing...")
    result = orchestrator.process_document(pdf_path, doc_id)

    if result is None:
        print("Document is not CAD-like, no tags extracted.")
        return 0

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Tags extracted: {result['tags_extracted']}")
    print(f"Pages processed: {result['pages_processed']}")
    print(f"Elapsed: {result['elapsed_sec']:.1f}s")
    print()

    # Check output file
    tags_file = PROJECT_ROOT / "artifacts/ingestion_production/entities/tags.jsonl"
    if tags_file.exists():
        line_count = len(tags_file.read_text(encoding="utf-8").strip().split("\n"))
        print(f"✅ Tags saved: {tags_file}")
        print(f"✅ File contains {line_count} tag records")
    else:
        print(f"⚠️  Tags file not found at expected location: {tags_file}")

    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
