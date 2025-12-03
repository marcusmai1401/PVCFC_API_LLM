#!/usr/bin/env python3
"""
Generate text_by_page.jsonl from processed ingestion data

Purpose:
    Recreate the text_by_page.jsonl lookup file from existing processed JSON files
    without re-running OCR. This file is used for Citation Verification and Highlighting.

Usage:
    python scripts/utilities/generate_text_by_page.py

Output:
    D:\PVCFC_Artifacts\text_by_page.jsonl

Format:
    Each line: {"doc_id": "...", "page": 1, "text": "..."}
"""

import json
import os
import sys
from glob import glob
from pathlib import Path
from typing import Dict, List

from loguru import logger
from tqdm import tqdm

# ============================================================================
# Configuration
# ============================================================================

# Artifacts directory (configurable via environment variable)
ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "D:\\PVCFC_Artifacts")

# Input: Processed JSON files from ingestion
INPUT_DIR = os.path.join(ARTIFACTS_DIR, "ingestion_production", "documents")

# Output: text_by_page.jsonl lookup file
OUTPUT_FILE = os.path.join(ARTIFACTS_DIR, "text_by_page.jsonl")


# ============================================================================
# Core Functions
# ============================================================================


def extract_doc_id_from_filename(filepath: str) -> str:
    """
    Extract doc_id from filename pattern: DOCID_XXX_..._processed.json

    Args:
        filepath: Full path to processed JSON file

    Returns:
        Extracted doc_id (without DOCID_ prefix and _processed.json suffix)
    """
    filename = os.path.basename(filepath)
    # Remove _processed.json suffix
    filename = filename.replace("_processed.json", "")
    return filename


def process_single_file(filepath: str) -> List[Dict]:
    """
    Process a single processed JSON file and extract page texts

    Args:
        filepath: Path to *_processed.json file

    Returns:
        List of {"doc_id": ..., "page": ..., "text": ...} dicts
    """
    results = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract doc_id from filename (fallback if not in JSON)
        doc_id = extract_doc_id_from_filename(filepath)

        # Check if "pages" key exists
        if "pages" not in data:
            logger.warning(f"No 'pages' key in {filepath}, skipping")
            return results

        pages = data["pages"]

        # Extract text from each page
        for page_data in pages:
            page_num = page_data.get("page_num") or page_data.get("page")
            text = page_data.get("text")

            # Data cleaning: convert None to empty string
            if text is None:
                text = ""

            # Skip if page number is missing
            if page_num is None:
                logger.warning(f"Page without page_num in {filepath}, skipping page")
                continue

            results.append({"doc_id": doc_id, "page": page_num, "text": text})

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error processing {filepath}: {e}")

    return results


def generate_text_by_page():
    """
    Main function to generate text_by_page.jsonl from all processed JSON files
    """
    logger.info("=" * 80)
    logger.info("GENERATE TEXT_BY_PAGE.JSONL")
    logger.info("=" * 80)
    logger.info(f"Input directory: {INPUT_DIR}")
    logger.info(f"Output file: {OUTPUT_FILE}")

    # Check if input directory exists
    if not os.path.exists(INPUT_DIR):
        logger.error(f"Input directory not found: {INPUT_DIR}")
        logger.error("Please verify ARTIFACTS_DIR configuration")
        sys.exit(1)

    # Find all processed JSON files
    pattern = os.path.join(INPUT_DIR, "*_processed.json")
    json_files = glob(pattern)

    if not json_files:
        logger.error(f"No *_processed.json files found in {INPUT_DIR}")
        sys.exit(1)

    logger.info(f"Found {len(json_files)} processed JSON files")

    # Process all files with progress bar
    all_pages = []
    total_pages_count = 0
    total_docs_count = 0

    logger.info("Processing files...")
    for filepath in tqdm(json_files, desc="Processing", unit="file"):
        pages = process_single_file(filepath)
        all_pages.extend(pages)

        if pages:
            total_docs_count += 1
            total_pages_count += len(pages)

    # Write output JSONL file
    logger.info(f"Writing output to {OUTPUT_FILE}...")

    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for page_entry in all_pages:
                # Write each entry as a single JSON line
                json_line = json.dumps(page_entry, ensure_ascii=False)
                f.write(json_line + "\n")

        logger.success(f"✅ Successfully generated {OUTPUT_FILE}")
        logger.success(f"📄 Total documents processed: {total_docs_count}")
        logger.success(f"📑 Total pages extracted: {total_pages_count}")

    except Exception as e:
        logger.error(f"Failed to write output file: {e}")
        sys.exit(1)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    # Configure logger
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    try:
        generate_text_by_page()
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)
