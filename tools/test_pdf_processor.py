#!/usr/bin/env python
"""Test PDF processor module"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor


def test_pdf_processor():
    logger.info("Testing PDF Processor")
    processor = PDFProcessor()

    # Test with sample PDFs
    pdf_dir = Path("data/raw/phase1_pilot")
    if pdf_dir.exists():
        pdfs = list(pdf_dir.glob("*.pdf"))[:1]  # Test with first PDF
        if pdfs:
            doc = processor.process_pdf(pdfs[0])
            logger.info(
                f"✅ Processed: {doc.file_name}, Pages: {doc.num_pages}, Words: {doc.total_words}"
            )
            return True

    logger.warning("No PDFs found to test")
    return False


if __name__ == "__main__":
    test_pdf_processor()
