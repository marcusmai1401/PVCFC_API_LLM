#!/usr/bin/env python3
"""
Ingestion Pipeline Audit Script
Implements Phase 3 & 4 of the Audit Plan.

Usage:
    python scripts/audit_ingestion.py audit-file <path_to_pdf>
    python scripts/audit_ingestion.py audit-output --output-dir <path_to_output>
"""
import argparse
import json
import logging
import os
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("audit_ingestion.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def setup_environment():
    """Phase 2: Environment & Dependency Check"""
    logger.info("=== Phase 2: Environment Check ===")

    # 1. Check OCR Credentials
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds:
        creds_path = Path(creds)
        if creds_path.exists():
            logger.info(f"✅ GOOGLE_APPLICATION_CREDENTIALS found: {creds}")
        else:
            logger.error(
                f"❌ GOOGLE_APPLICATION_CREDENTIALS set but file missing: {creds}"
            )
    else:
        logger.warning(
            "⚠️ GOOGLE_APPLICATION_CREDENTIALS not set. OCR might fail or use default."
        )

    # 2. Check Real-ESRGAN Model
    model_path = PROJECT_ROOT / "RealESRGAN_x4plus_anime_6B.pth"
    if model_path.exists():
        logger.info(f"✅ Real-ESRGAN model found: {model_path.name}")
    else:
        logger.error(f"❌ Real-ESRGAN model missing at {model_path}")


def audit_file(pdf_path: Path, output_dir: Path):
    """Phase 3: Dynamic Execution Audit"""
    logger.info(f"\n=== Phase 3: Auditing File: {pdf_path.name} ===")

    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        return

    try:
        # Import pipeline components
        from app.ingestion.cadlike_gate import get_cadlike_gate
        from app.ingestion.pdf_processor import PDFProcessor
        from app.ingestion.text_chunker import TextChunker

        # 1. CAD-like Gate
        logger.info("--- Step 1: CAD-like Classification ---")
        gate = get_cadlike_gate()
        decision = gate.evaluate(pdf_path)
        logger.info(
            f"Decision: CAD-like={decision.is_cadlike}, Score={decision.score:.3f}"
        )
        logger.info(f"Detection Method: {decision.detection_method}")

        # 2. PDF Processing
        logger.info("--- Step 2: PDF Processing ---")
        document_type = "CAD-like" if decision.is_cadlike else "non-CAD-like"

        processor = PDFProcessor(
            enable_ocr=True, extract_tables=True, document_type=document_type
        )

        start_time = datetime.now()
        pdf_doc = processor.process_pdf(pdf_path)
        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Processing Time: {duration:.2f}s")
        logger.info(f"Source Format: {pdf_doc.source_format}")
        logger.info(f"Pages: {pdf_doc.num_pages}")
        logger.info(f"Total Chars: {pdf_doc.total_chars}")

        # Validation
        if pdf_doc.total_chars == 0:
            logger.error("❌ No text extracted from document!")
        else:
            logger.info(f"✅ Text extracted ({pdf_doc.total_chars} chars)")

        # Check page continuity
        extracted_pages = [p.page_num for p in pdf_doc.pages]
        expected_pages = list(range(1, pdf_doc.num_pages + 1))
        if extracted_pages != expected_pages:
            logger.warning(f"⚠️ Page number mismatch. Extracted: {extracted_pages}")
        else:
            logger.info("✅ Page numbering is sequential")

        # 3. Chunking
        logger.info("--- Step 3: Text Chunking ---")
        chunker = TextChunker(chunking_strategy="hierarchical")
        # Convert PDFDocument to dict for chunker
        doc_dict = pdf_doc.to_dict()
        chunks = chunker.chunk_document(doc_dict, doc_id=pdf_path.stem)

        logger.info(f"Generated {len(chunks)} chunks")

        if not chunks:
            logger.warning("⚠️ No chunks generated")
        else:
            # Check chunk metadata
            sample_chunk = chunks[0]
            logger.info(f"Sample Chunk Metadata: {sample_chunk.metadata}")

            # Verify page numbers in metadata
            pages_in_chunks = set(c.metadata.get("page") for c in chunks)
            logger.info(f"Pages represented in chunks: {sorted(list(pages_in_chunks))}")

            # Check for 'page: 1' fallback issue
            page_1_count = sum(1 for c in chunks if c.metadata.get("page") == 1)
            if page_1_count == len(chunks) and pdf_doc.num_pages > 1:
                logger.warning(
                    "⚠️ All chunks assigned to Page 1 (possible mapping failure)"
                )

        # Save debug artifacts
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / f"{pdf_path.stem}_doc.json", "w", encoding="utf-8") as f:
            f.write(pdf_doc.to_json())

        with open(
            output_dir / f"{pdf_path.stem}_chunks.jsonl", "w", encoding="utf-8"
        ) as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

        logger.info(f"Saved artifacts to {output_dir}")

    except Exception as e:
        logger.exception(f"❌ Audit failed with error: {e}")


def audit_output_dir(output_dir: Path):
    """Phase 4: Data Quality & Artifact Inspection"""
    logger.info(f"\n=== Phase 4: Analyzing Output Directory: {output_dir} ===")

    if not output_dir.exists():
        logger.error(f"Output directory not found: {output_dir}")
        return

    manifest_path = output_dir / "manifests" / "corpus.jsonl"
    chunks_path = output_dir / "chunks" / "chunks.jsonl"

    # 1. Manifest Analysis
    if manifest_path.exists():
        logger.info("--- Manifest Analysis ---")
        modes = Counter()
        types = Counter()
        formats = Counter()

        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    modes[entry.get("processing_mode", "unknown")] += 1
                    types[entry.get("doc_type", "unknown")] += 1
                    formats[entry.get("source_format", "unknown")] += 1
                except:
                    pass

        logger.info("Processing Modes:")
        for mode, count in modes.items():
            logger.info(f"  - {mode}: {count}")

        logger.info("Document Types:")
        for dtype, count in types.items():
            logger.info(f"  - {dtype}: {count}")

        logger.info("Source Formats:")
        for fmt, count in formats.items():
            logger.info(f"  - {fmt}: {count}")
    else:
        logger.warning(f"Manifest file missing: {manifest_path}")

    # 2. Chunk Quality Check
    if chunks_path.exists():
        logger.info("--- Chunk Quality Analysis ---")
        total_chunks = 0
        empty_chunks = 0
        page_1_chunks = 0
        page_types = Counter()

        with open(chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    chunk = json.loads(line)
                    total_chunks += 1
                    text = chunk.get("text", "").strip()

                    if not text:
                        empty_chunks += 1

                    page = chunk.get("metadata", {}).get("page")
                    if page == 1:
                        page_1_chunks += 1

                    # Track page type
                    page_types[type(page).__name__] += 1

                except:
                    pass

        logger.info(f"Total Chunks: {total_chunks}")
        logger.info(
            f"Empty Chunks: {empty_chunks} ({(empty_chunks/total_chunks*100 if total_chunks else 0):.2f}%)"
        )
        logger.info(
            f"Page 1 Chunks: {page_1_chunks} ({(page_1_chunks/total_chunks*100 if total_chunks else 0):.2f}%)"
        )
        logger.info(f"Page Value Types: {dict(page_types)}")

    else:
        logger.warning(f"Chunks file missing: {chunks_path}")


def main():
    parser = argparse.ArgumentParser(description="Ingestion Pipeline Audit Tool")
    subparsers = parser.add_subparsers(dest="command", help="Audit command")

    # Audit File Command
    file_parser = subparsers.add_parser(
        "audit-file", help="Audit single file processing"
    )
    file_parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    file_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("audit_output"),
        help="Directory for debug artifacts",
    )

    # Audit Output Command
    dir_parser = subparsers.add_parser(
        "audit-output", help="Analyze existing output directory"
    )
    dir_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Path to ingestion output directory",
    )

    args = parser.parse_args()

    setup_environment()

    if args.command == "audit-file":
        audit_file(args.pdf_path, args.output_dir)
    elif args.command == "audit-output":
        audit_output_dir(args.output_dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
