"""
Test PaddleOCR Integration in PDF Processor
Verifies that PaddleOCR is properly integrated and working
"""
import sys
from pathlib import Path

from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO", format="<level>{level: <8}</level> | {message}")

logger.info("=" * 80)
logger.info("TESTING PADDLEOCR INTEGRATION")
logger.info("=" * 80)

# Step 1: Test PaddleOCR config module
logger.info("\n[1/4] Testing PaddleOCR config module...")
try:
    from app.ingestion.paddle_ocr_config import (
        OCR_AVAILABLE,
        get_ocr_status,
        initialize_paddleocr,
        verify_ppocrv5_models,
    )

    if not OCR_AVAILABLE:
        logger.error("✗ PaddleOCR not available!")
        sys.exit(1)

    logger.info("✓ PaddleOCR module imported successfully")

    # Check models
    if not verify_ppocrv5_models():
        logger.error("✗ PP-OCRv5 models not found!")
        sys.exit(1)

    logger.info("✓ PP-OCRv5 models verified")

    # Get OCR status
    status = get_ocr_status()
    logger.info(f"✓ OCR Status: {status}")

except Exception as e:
    logger.error(f"✗ Failed to import PaddleOCR config: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Step 2: Initialize PaddleOCR
logger.info("\n[2/4] Initializing PaddleOCR...")
try:
    ocr = initialize_paddleocr(show_log=False)
    if ocr is None:
        logger.error("✗ Failed to initialize PaddleOCR")
        sys.exit(1)

    logger.info("✓ PaddleOCR initialized successfully")

except Exception as e:
    logger.error(f"✗ Failed to initialize PaddleOCR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Step 3: Test with PDFProcessor
logger.info("\n[3/4] Testing PDF Processor with PaddleOCR...")
try:
    from app.ingestion.pdf_processor import PDFProcessor

    # Create processor with OCR enabled
    processor = PDFProcessor(
        extract_tables=True,
        enable_ocr=True,
        ocr_min_confidence=30.0,
    )

    logger.info("✓ PDFProcessor created with OCR enabled")

    # Check OCR is enabled
    if not processor.enable_ocr:
        logger.error("✗ OCR not enabled in PDFProcessor")
        sys.exit(1)

    logger.info("✓ OCR enabled in PDFProcessor")

except Exception as e:
    logger.error(f"✗ Failed to create PDFProcessor: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Step 4: Test with a real PDF file
logger.info("\n[4/4] Testing with a real PDF file...")
try:
    # Find a test PDF
    data_dir = Path(r"D:\Data_Raw")
    pdf_files = list(data_dir.rglob("*.pdf"))[:1]  # Get first PDF

    if not pdf_files:
        logger.warning("⚠ No PDF files found in D:\\Data_Raw")
        logger.info("Skipping PDF processing test")
    else:
        test_pdf = pdf_files[0]
        logger.info(f"Testing with: {test_pdf.name}")

        # Process the PDF
        pdf_doc = processor.process_pdf(test_pdf)

        logger.info(f"✓ PDF processed successfully")
        logger.info(f"  Pages: {pdf_doc.num_pages}")
        logger.info(f"  Total chars: {pdf_doc.total_chars}")
        logger.info(f"  Total words: {pdf_doc.total_words}")
        logger.info(f"  Source format: {pdf_doc.source_format}")

        # Show first page info
        if pdf_doc.pages:
            first_page = pdf_doc.pages[0]
            logger.info(f"  First page chars: {first_page.char_count}")
            logger.info(f"  First page text (first 100 chars): {first_page.text[:100]}")

except Exception as e:
    logger.error(f"✗ Failed to process PDF: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Success!
logger.info("\n" + "=" * 80)
logger.info("✅ ALL TESTS PASSED!")
logger.info("=" * 80)
logger.info("\nPaddleOCR is properly integrated and working!")
logger.info("Ready to run full ingestion with PP-OCRv5")
logger.info("=" * 80)
