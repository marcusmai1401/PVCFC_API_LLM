#!/usr/bin/env python
"""
Re-ingest a single PDF (targeted), bypassing quick_classify usage.
Usage:
  python scripts/re_ingest_single.py "D:\\path\\to\\file.pdf"
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
                    creds_path = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
                    break

from loguru import logger

from app.ingestion.document_classifier import DocumentClassifier
from app.ingestion.pdf_processor import PDFProcessor
from app.ingestion.text_chunker import TextChunker


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: python scripts/re_ingest_single.py <pdf_path>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    logger.info(f"Processing single file: {file_path}")

    # Processor with conservative settings
    processor = PDFProcessor(
        enable_ocr=True,
        extract_tables=False,
        force_ocr_all_pages=False,
    )

    pdf_doc = processor.process_pdf(file_path)
    full_text = "\n".join(p.text for p in pdf_doc.pages)

    if not full_text.strip():
        logger.info("No vector text; forcing OCR for all pages")
        processor = PDFProcessor(
            enable_ocr=True,
            extract_tables=False,
            force_ocr_all_pages=True,
        )
        pdf_doc = processor.process_pdf(file_path)
        full_text = "\n".join(p.text for p in pdf_doc.pages)

    if not full_text.strip():
        logger.error("No text extracted after OCR")
        sys.exit(2)

    # Classification with safe fallback (no quick_classify)
    quick_doc_type = "unknown"
    try:
        doc_type, _ = DocumentClassifier().classify(file_path)
        quick_doc_type = doc_type
    except Exception:
        if "manual" in file_path.name.lower():
            quick_doc_type = "Manual"

    # Chunking using TextChunker which supports chunk_document on dict-like docs
    chunker = TextChunker(
        chunk_size=1000,
        chunk_overlap=200,
        chunking_strategy="semantic",
    )
    # Convert to dict for TextChunker
    doc_dict = (
        pdf_doc.to_dict()
        if hasattr(pdf_doc, "to_dict")
        else {
            "pages": [
                {"page_num": p.page_num, "text": p.text}
                for p in getattr(pdf_doc, "pages", [])
            ],
            "file_name": file_path.name,
        }
    )
    chunks = chunker.chunk_document(doc_dict, doc_id=f"REINGEST_{file_path.stem}")

    logger.success(
        f"Processed {file_path.name}: pages={len(pdf_doc.pages)}, chars={len(full_text)}, chunks={len(chunks)}, type={quick_doc_type}"
    )


if __name__ == "__main__":
    sys.exit(main())
