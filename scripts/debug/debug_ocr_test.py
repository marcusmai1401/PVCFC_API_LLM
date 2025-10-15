#!/usr/bin/env python
"""
Debug OCR Test Script
Test PaddleOCR directly on a quarantined file
"""
import sys
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor


def test_ocr_on_file(pdf_path: str):
    """Test OCR on a specific PDF file"""
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        return

    logger.info(f"Testing OCR on: {pdf_path}")
    logger.info("=" * 80)

    # Test 1: Without OCR
    logger.info("\n1️⃣ Testing WITHOUT OCR...")
    processor_no_ocr = PDFProcessor(
        enable_ocr=False,
        extract_tables=False,
    )

    try:
        doc_no_ocr = processor_no_ocr.process_pdf(pdf_path)
        total_text_no_ocr = "\n".join(page.text for page in doc_no_ocr.pages)
        logger.info(f"✓ Pages: {doc_no_ocr.num_pages}")
        logger.info(f"✓ Total chars (no OCR): {len(total_text_no_ocr)}")
        logger.info(f"✓ First 200 chars: {total_text_no_ocr[:200]}")
    except Exception as e:
        logger.error(f"✗ Failed without OCR: {e}")
        return

    # Test 2: With OCR
    logger.info("\n2️⃣ Testing WITH OCR (PaddleOCR)...")
    processor_with_ocr = PDFProcessor(
        enable_ocr=True,
        ocr_language="vie+eng",
        ocr_min_confidence=30.0,
        extract_tables=False,
    )

    try:
        doc_with_ocr = processor_with_ocr.process_pdf(pdf_path)
        total_text_with_ocr = "\n".join(page.text for page in doc_with_ocr.pages)
        logger.info(f"✓ Pages: {doc_with_ocr.num_pages}")
        logger.info(f"✓ Total chars (with OCR): {len(total_text_with_ocr)}")
        logger.info(f"✓ First 500 chars: {total_text_with_ocr[:500]}")

        # Show per-page stats
        logger.info("\n📄 Per-page text extraction:")
        for i, page in enumerate(doc_with_ocr.pages[:5]):  # First 5 pages
            logger.info(
                f"   Page {i+1}: {page.char_count} chars, {page.word_count} words"
            )

        if len(total_text_with_ocr.strip()) > 100:
            logger.success("✅ OCR successfully extracted text!")
        else:
            logger.warning("⚠️ OCR extracted minimal text (<100 chars)")

    except Exception as e:
        logger.error(f"✗ Failed with OCR: {e}")
        logger.exception(e)


if __name__ == "__main__":
    # Test file
    test_file = r"D:\Data_Raw\092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf"

    logger.info("=" * 80)
    logger.info("DEBUG OCR TEST")
    logger.info("=" * 80)

    test_ocr_on_file(test_file)
