#!/usr/bin/env python
"""
Test batch OCR on quarantined files
"""
import json
import sys
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor


def test_quarantined_files():
    """Test OCR on files from quarantine.jsonl"""

    # Read quarantine file
    quarantine_file = Path("artifacts/ingestion_production/quarantine.jsonl")

    if not quarantine_file.exists():
        logger.error(f"Quarantine file not found: {quarantine_file}")
        return

    # Parse quarantine file and filter ocr_failed entries
    ocr_failed_files = []
    with open(quarantine_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            # Only test ocr_failed, not corrupt, not __MACOSX files
            if entry["reason_code"] == "ocr_failed" and "__MACOSX" not in entry["file"]:
                ocr_failed_files.append(entry["file"])

    # Get unique files (since quarantine may have duplicates from multiple runs)
    unique_files = list(dict.fromkeys(ocr_failed_files))

    logger.info(
        f"Found {len(unique_files)} unique ocr_failed files (excluding corrupt/__MACOSX)"
    )

    # Test first 8 files
    test_files = unique_files[:8]

    logger.info("=" * 80)
    logger.info(f"TESTING OCR ON {len(test_files)} QUARANTINED FILES")
    logger.info("=" * 80)

    # Initialize processor with OCR enabled
    processor = PDFProcessor(
        enable_ocr=True,
        ocr_language="vie+eng",
        ocr_min_confidence=30.0,
        extract_tables=False,
    )

    results = []

    for idx, file_path in enumerate(test_files, 1):
        pdf_path = Path(file_path)

        logger.info("")
        logger.info(f"[{idx}/{len(test_files)}] Testing: {pdf_path.name}")
        logger.info("-" * 80)

        if not pdf_path.exists():
            logger.warning(f"  ⚠️ File not found: {pdf_path}")
            results.append(
                {
                    "file": pdf_path.name,
                    "status": "NOT_FOUND",
                    "pages": 0,
                    "chars": 0,
                    "words": 0,
                }
            )
            continue

        try:
            doc = processor.process_pdf(pdf_path)
            total_chars = doc.total_chars
            total_words = doc.total_words

            status = "✅ SUCCESS" if total_chars > 100 else "⚠️ MINIMAL_TEXT"

            logger.info(f"  {status}")
            logger.info(f"  Pages: {doc.num_pages}")
            logger.info(f"  Chars: {total_chars:,}")
            logger.info(f"  Words: {total_words:,}")
            logger.info(f"  Format: {doc.source_format}")

            results.append(
                {
                    "file": pdf_path.name,
                    "status": "SUCCESS" if total_chars > 100 else "MINIMAL",
                    "pages": doc.num_pages,
                    "chars": total_chars,
                    "words": total_words,
                    "format": doc.source_format,
                }
            )

        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            results.append(
                {
                    "file": pdf_path.name,
                    "status": "ERROR",
                    "pages": 0,
                    "chars": 0,
                    "words": 0,
                    "error": str(e),
                }
            )

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    minimal_count = sum(1 for r in results if r["status"] == "MINIMAL")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")

    logger.info(f"✅ Success (>100 chars): {success_count}/{len(results)}")
    logger.info(f"⚠️ Minimal text (<100 chars): {minimal_count}/{len(results)}")
    logger.info(f"✗ Error: {error_count}/{len(results)}")
    logger.info(f"⚠️ Not found: {not_found_count}/{len(results)}")

    total_chars = sum(
        r["chars"] for r in results if r["status"] in ["SUCCESS", "MINIMAL"]
    )
    total_words = sum(
        r["words"] for r in results if r["status"] in ["SUCCESS", "MINIMAL"]
    )

    logger.info("")
    logger.info(f"Total extracted: {total_chars:,} chars, {total_words:,} words")

    logger.info("")
    logger.info("=" * 80)
    logger.info("DETAILED RESULTS")
    logger.info("=" * 80)

    for r in results:
        status_icon = {
            "SUCCESS": "✅",
            "MINIMAL": "⚠️",
            "ERROR": "❌",
            "NOT_FOUND": "⚠️",
        }.get(r["status"], "?")

        logger.info(
            f"{status_icon} {r['file'][:60]:<60} | {r['chars']:>8} chars | {r['words']:>6} words"
        )

    return results


if __name__ == "__main__":
    test_quarantined_files()
