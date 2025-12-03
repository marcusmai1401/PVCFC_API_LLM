#!/usr/bin/env python
"""
Test OCR speed with different worker counts
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor


def test_ocr_speed():
    """Test OCR on 5 quarantined files"""

    # Get 5 ocr_failed files
    quarantine_file = Path("artifacts/ingestion_production/quarantine.jsonl")

    ocr_failed_files = []
    with open(quarantine_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry["reason_code"] == "ocr_failed" and "__MACOSX" not in entry["file"]:
                ocr_failed_files.append(entry["file"])
                if len(ocr_failed_files) >= 5:
                    break

    logger.info(f"Testing OCR speed on {len(ocr_failed_files)} files")

    # Initialize processor
    processor = PDFProcessor(
        enable_ocr=True,
        ocr_language="vie+eng",
        ocr_min_confidence=30.0,
        extract_tables=False,
    )

    start_time = time.time()
    total_pages = 0
    total_chars = 0

    for idx, file_path in enumerate(ocr_failed_files, 1):
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            continue

        logger.info(f"[{idx}/{len(ocr_failed_files)}] Processing: {pdf_path.name}")

        try:
            doc = processor.process_pdf(pdf_path)
            total_pages += doc.num_pages
            total_chars += doc.total_chars
            logger.info(f"  ✅ {doc.num_pages} pages, {doc.total_chars:,} chars")
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")

    elapsed = time.time() - start_time

    logger.info("")
    logger.info("=" * 80)
    logger.info("SPEED TEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"Files processed: {len(ocr_failed_files)}")
    logger.info(f"Total pages: {total_pages}")
    logger.info(f"Total chars: {total_chars:,}")
    logger.info(f"Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"Speed: {total_pages/elapsed:.2f} pages/sec")
    logger.info("")
    logger.info(
        f"Estimated time for 56 files (avg {total_pages/len(ocr_failed_files):.0f} pages/file):"
    )

    avg_pages_per_file = total_pages / len(ocr_failed_files)
    total_pages_estimate = 56 * avg_pages_per_file

    # Single worker estimate
    time_1_worker = (total_pages_estimate / total_pages) * elapsed
    logger.info(f"  1 worker:  {time_1_worker/3600:.1f} hours")
    logger.info(f"  4 workers: {time_1_worker/4/3600:.1f} hours")
    logger.info(f"  6 workers: {time_1_worker/6/3600:.1f} hours")


if __name__ == "__main__":
    test_ocr_speed()
