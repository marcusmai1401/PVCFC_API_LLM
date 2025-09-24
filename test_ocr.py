#!/usr/bin/env python
"""
Test OCR functionality for PDF processing
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from loguru import logger


def test_ocr_setup():
    """Test if OCR dependencies are properly installed"""
    logger.info("=" * 80)
    logger.info("OCR SETUP TEST")
    logger.info("=" * 80)

    # Check Python dependencies
    try:
        from PIL import Image

        logger.success("✓ PIL/Pillow is installed")
    except ImportError:
        logger.error("✗ PIL/Pillow is not installed. Run: pip install Pillow")
        return False

    try:
        import pytesseract

        logger.success("✓ pytesseract is installed")
    except ImportError:
        logger.error("✗ pytesseract is not installed. Run: pip install pytesseract")
        return False

    # Check Tesseract executable
    try:
        import pytesseract

        # Try to get Tesseract version
        version = pytesseract.get_tesseract_version()
        logger.success(f"✓ Tesseract OCR is installed (version: {version})")
        return True
    except pytesseract.TesseractNotFoundError:
        logger.error("✗ Tesseract OCR executable not found!")
        logger.info("")
        logger.info("To install Tesseract OCR on Windows:")
        logger.info("1. Download from: https://github.com/UB-Mannheim/tesseract/wiki")
        logger.info("2. Run the installer")
        logger.info("3. Add Tesseract to PATH or set the path in pytesseract:")
        logger.info(
            "   pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'"
        )
        logger.info("")
        logger.info("To install Tesseract OCR on Linux:")
        logger.info("   sudo apt-get install tesseract-ocr")
        logger.info("")
        logger.info("To install Tesseract OCR on macOS:")
        logger.info("   brew install tesseract")
        return False


def test_pdf_with_ocr():
    """Test PDF processing with OCR"""
    from app.ingestion.pdf_processor import PDFProcessor

    logger.info("")
    logger.info("=" * 80)
    logger.info("PDF OCR TEST")
    logger.info("=" * 80)

    # Create processor with OCR enabled
    processor = PDFProcessor(
        enable_ocr=True, ocr_language="eng", ocr_min_confidence=30.0
    )

    # Find a test PDF
    pdf_dir = Path("data/raw/phase1_pilot")
    pdf_files = list(pdf_dir.glob("*.pdf"))[:1]  # Test with first PDF

    if not pdf_files:
        logger.error("No PDF files found for testing")
        return

    test_pdf = pdf_files[0]
    logger.info(f"Testing with: {test_pdf.name}")

    try:
        # Process the PDF
        doc = processor.process_pdf(test_pdf)

        logger.info(f"Processed {doc.num_pages} pages")
        logger.info(f"Document format: {doc.source_format}")
        logger.info(f"Total words: {doc.total_words}")

        # Check if any pages used OCR
        ocr_pages = [p for p in doc.pages if len(p.text) > 0]
        if doc.source_format in ["scan", "mixed"]:
            logger.success(f"✓ OCR was used for scanned pages")
        else:
            logger.info("Document appears to be vector-based (no OCR needed)")

        # Show sample text from first page
        if doc.pages:
            sample_text = doc.pages[0].text[:200]
            logger.info(f"\nSample text from page 1:\n{sample_text}...")

    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Run OCR tests"""
    # Test setup
    if not test_ocr_setup():
        logger.warning("OCR setup incomplete. OCR will be disabled.")
        logger.info(
            "The system will still work but won't be able to extract text from scanned PDFs."
        )
        return

    # Test PDF processing with OCR
    test_pdf_with_ocr()

    logger.info("")
    logger.info("=" * 80)
    logger.info("OCR testing complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
