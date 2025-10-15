#!/usr/bin/env python
"""
Test Deduplication Behavior
Tests file hash vs content hash deduplication

Creates 3 test scenarios:
1. Exact duplicate (file copy)
2. Near-duplicate (95% similar content)
3. Original file

Verifies:
- Exact duplicates are skipped (file_hash)
- Near-duplicates are kept (95% content similarity)
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger


def create_test_pdfs(output_dir: Path):
    """
    Create test PDFs for deduplication testing

    Uses existing test PDF and creates:
    1. original.pdf
    2. original_copy.pdf (exact copy - should be skipped)
    3. original_v1.1.pdf (modified version - should be kept)
    """
    logger.info("Creating test PDFs...")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Use existing test PDF as source
    source_pdf = PROJECT_ROOT / "test_docs" / "Equipment_Datasheet_KT06101.pdf"

    if not source_pdf.exists():
        logger.error(f"Source PDF not found: {source_pdf}")
        return False

    # 1. Copy as original
    original = output_dir / "original.pdf"
    shutil.copy2(source_pdf, original)
    logger.info(f"  Created: {original.name}")

    # 2. Exact copy (file duplicate)
    exact_copy = output_dir / "original_copy.pdf"
    shutil.copy2(original, exact_copy)
    logger.info(f"  Created: {exact_copy.name} (exact duplicate)")

    # 3. Near-duplicate (modify file slightly)
    # Note: Can't easily modify PDF content programmatically
    # For now, document that this needs manual creation
    logger.warning("  Near-duplicate (95% similar) needs manual creation")
    logger.info("    Suggestion: Manually edit PDF, save as original_v1.1.pdf")

    return True


def run_dedup_test(test_pdfs_dir: Path, output_dir: Path):
    """Run ingestion and check dedup behavior"""
    logger.info("\nRunning dedup test...")

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "ingest.py"),
        "--source-dir",
        str(test_pdfs_dir),
        "--output-dir",
        str(output_dir),
        "--chunk-size",
        "1000",
        "--chunk-overlap",
        "200",
    ]

    logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    logger.info(f"Exit code: {result.returncode}")

    # Parse stats from output
    if result.returncode == 0:
        # Check outputs
        doc_id_map_file = output_dir / "doc_id_map.json"
        if doc_id_map_file.exists():
            with open(doc_id_map_file, encoding="utf-8") as f:
                doc_id_map = json.load(f)

            processed_count = len(doc_id_map)
            logger.info(f"\n📊 Results:")
            logger.info(f"  Processed files: {processed_count}")

            # Expected with file_hash dedup: 1 (skip exact copy)
            # Actual without file_hash dedup: 2 (processes both)
            if processed_count == 1:
                logger.info(
                    "  ✅ PASS: Exact duplicate was skipped (file_hash dedup works)"
                )
            elif processed_count == 2:
                logger.warning(
                    "  ⚠️  ISSUE: Both files processed (file_hash dedup NOT working)"
                )
                logger.warning("      Expected: Skip exact copy, process only 1 file")
                logger.warning("      Actual: Processed both files")
            else:
                logger.error(f"  ❌ UNEXPECTED: {processed_count} files processed")

            logger.info(f"\n  Files in doc_id_map:")
            for doc_id, pdf_path in doc_id_map.items():
                logger.info(f"    - {Path(pdf_path).name}")

        return processed_count
    else:
        logger.error("Ingestion failed")
        logger.error(result.stderr)
        return None


def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("DEDUPLICATION BEHAVIOR TEST")
    logger.info("=" * 80)

    # Setup
    test_pdfs_dir = PROJECT_ROOT / "data" / "test" / "dedup_test"
    output_dir = PROJECT_ROOT / "artifacts" / "test_dedup"

    # Clean previous test
    if output_dir.exists():
        shutil.rmtree(output_dir)
    if test_pdfs_dir.exists():
        shutil.rmtree(test_pdfs_dir)

    # Create test PDFs
    if not create_test_pdfs(test_pdfs_dir):
        logger.error("Failed to create test PDFs")
        return 1

    # Run test
    processed_count = run_dedup_test(test_pdfs_dir, output_dir)

    # Report
    logger.info("\n" + "=" * 80)
    logger.info("TEST CONCLUSION")
    logger.info("=" * 80)

    if processed_count == 1:
        logger.info("✅ PASS: File hash deduplication is working")
        logger.info("   Exact duplicates are correctly skipped")
        return 0
    elif processed_count == 2:
        logger.error("❌ FAIL: File hash deduplication is NOT working")
        logger.error("   Exact duplicates are being processed")
        logger.error("")
        logger.error("FIX REQUIRED:")
        logger.error("  Add file_hash dedup check in tools/ingest.py before line 395")
        logger.error("  See: OFFLINE_BUILD_AUDIT_REPORT_20251007.md for code snippet")
        return 1
    else:
        logger.error(
            f"❌ UNEXPECTED: {processed_count} files processed (expected 1 or 2)"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
