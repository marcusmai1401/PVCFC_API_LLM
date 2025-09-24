#!/usr/bin/env python
"""
Test OCR status and PDF processing with/without OCR
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from loguru import logger

from app.ingestion.ocr_config import get_ocr_status
from app.ingestion.pdf_processor import PDFProcessor


def display_ocr_status():
    """Display OCR configuration status"""
    logger.info("=" * 80)
    logger.info("OCR CONFIGURATION STATUS")
    logger.info("=" * 80)

    status = get_ocr_status()

    # Display status
    if status["pytesseract_installed"]:
        logger.success("✓ pytesseract Python package is installed")
    else:
        logger.warning("✗ pytesseract Python package is NOT installed")

    if status["pillow_installed"]:
        logger.success("✓ Pillow (PIL) is installed")
    else:
        logger.warning("✗ Pillow (PIL) is NOT installed")

    if status["tesseract_available"]:
        logger.success(f"✓ Tesseract OCR is available")
        if status["tesseract_path"]:
            logger.info(f"  Path: {status['tesseract_path']}")
        if status["tesseract_version"]:
            logger.info(f"  Version: {status['tesseract_version']}")
    else:
        logger.warning("✗ Tesseract OCR executable is NOT available")
        logger.info(
            "  Tesseract needs to be installed separately from: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    logger.info("")
    if status["ocr_enabled"]:
        logger.success("✓ OCR is ENABLED and ready to use")
    else:
        logger.warning(
            "⚠ OCR is DISABLED - system will only extract vector text from PDFs"
        )
        logger.info("  Scanned PDFs may not be processed correctly without OCR")


def test_pdf_processing():
    """Test PDF processing with current OCR status"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("PDF PROCESSING TEST")
    logger.info("=" * 80)

    status = get_ocr_status()

    # Create processor
    processor = PDFProcessor(
        enable_ocr=status["ocr_enabled"],  # Use OCR only if available
        ocr_language="eng",
        ocr_min_confidence=30.0,
    )

    logger.info(
        f"PDF Processor initialized (OCR: {'enabled' if processor.enable_ocr else 'disabled'})"
    )

    # Find test PDFs
    pdf_dir = Path("data/raw/phase1_pilot")
    if not pdf_dir.exists():
        logger.error(f"PDF directory not found: {pdf_dir}")
        return

    pdf_files = list(pdf_dir.glob("*.pdf"))[:2]  # Test with first 2 PDFs

    if not pdf_files:
        logger.error("No PDF files found for testing")
        return

    logger.info(f"Found {len(pdf_files)} test PDFs")

    for pdf_file in pdf_files:
        logger.info("")
        logger.info(f"Processing: {pdf_file.name}")
        logger.info("-" * 40)

        try:
            # Process the PDF
            doc = processor.process_pdf(pdf_file)

            # Display results
            logger.info(f"  Pages: {doc.num_pages}")
            logger.info(f"  Format: {doc.source_format}")
            logger.info(f"  Total words: {doc.total_words}")
            logger.info(f"  Total chars: {doc.total_chars}")

            # Check for empty pages
            empty_pages = [p.page_num for p in doc.pages if p.char_count < 40]
            if empty_pages and not processor.enable_ocr:
                logger.warning(f"  ⚠ Pages with little/no text: {empty_pages}")
                logger.info(f"    These might be scanned pages that need OCR")

            # Show sample from first page with content
            for page in doc.pages:
                if page.char_count > 40:
                    sample = page.text[:150].replace("\n", " ")
                    logger.info(f"  Sample (page {page.page_num}): {sample}...")
                    break

        except Exception as e:
            logger.error(f"  Failed to process: {e}")


def test_build_index_with_ocr():
    """Test building BM25 index with OCR flag"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("BUILD INDEX TEST")
    logger.info("=" * 80)

    status = get_ocr_status()

    if status["ocr_enabled"]:
        logger.info("Testing build_bm25_index.py with --enable-ocr flag")
        logger.info("Command: python tools/build_bm25_index.py --enable-ocr")
    else:
        logger.info("Testing build_bm25_index.py without OCR (not available)")
        logger.info("Command: python tools/build_bm25_index.py")

    logger.info("")
    logger.info("You can run the index build manually with:")
    if status["ocr_enabled"]:
        logger.info("  python tools/build_bm25_index.py --enable-ocr")
    else:
        logger.info("  python tools/build_bm25_index.py")
        logger.info("  (OCR will be automatically disabled since it's not available)")


def main():
    """Run OCR status check and tests"""
    # Display OCR status
    display_ocr_status()

    # Test PDF processing
    test_pdf_processing()

    # Show index building command
    test_build_index_with_ocr()

    logger.info("")
    logger.info("=" * 80)
    logger.info("TESTING COMPLETE")
    logger.info("=" * 80)

    status = get_ocr_status()
    if not status["ocr_enabled"]:
        logger.info("")
        logger.info("💡 TIP: To enable OCR support:")
        logger.info(
            "1. Install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki"
        )
        logger.info("2. The system will automatically detect it after installation")
        logger.info("3. Then use: python tools/build_bm25_index.py --enable-ocr")


if __name__ == "__main__":
    main()
