#!/usr/bin/env python
"""
Re-ingest files bị read_error với error handling tốt hơn
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv

env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

    # Explicitly set GOOGLE_APPLICATION_CREDENTIALS
    import os

    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
                    creds_path = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
                    break

import json

# Increase recursion limit
import sys

from loguru import logger

sys.setrecursionlimit(10000)  # Increase from default 1000

from app.ingestion.document_classifier import DocumentClassifier
from app.ingestion.pdf_processor import PDFProcessor
from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker
from app.storage.manifest_writer import ManifestWriter

# Read list of files
read_error_files_path = PROJECT_ROOT / "read_error_files.txt"
if not read_error_files_path.exists():
    logger.error(f"File not found: {read_error_files_path}")
    sys.exit(1)

with open(read_error_files_path, "r", encoding="utf-8") as f:
    files = [line.strip() for line in f if line.strip()]

logger.info(f"Found {len(files)} files to re-ingest")

# Initialize components
output_dir = PROJECT_ROOT / "artifacts" / "ingestion_production"
classifier = DocumentClassifier()
chunker = HierarchicalChunker(
    max_chunk_size=1000, chunk_overlap=200, chunking_strategy="hierarchical"
)

success_count = 0
failed_count = 0
quarantined_count = 0

results = []

for file_path_str in files:
    file_path = Path(file_path_str)

    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        failed_count += 1
        continue

    logger.info(f"Processing: {file_path.name}")

    try:
        # Try with simplified settings (no table extraction first)
        try:
            processor = PDFProcessor(
                enable_ocr=True,
                extract_tables=False,  # Disable table extraction to avoid recursion
                table_min_rows=2,
                table_min_cols=2,
                force_ocr_all_pages=False,
            )
            pdf_doc = processor.process_pdf(file_path)

            # Check if we got text
            full_text = "\n".join(page.text for page in pdf_doc.pages)

            if not full_text.strip():
                # Try with OCR
                logger.info(f"  No text found, trying with OCR: {file_path.name}")
                processor = PDFProcessor(
                    enable_ocr=True,
                    extract_tables=False,
                    force_ocr_all_pages=True,
                )
                pdf_doc = processor.process_pdf(file_path)
                full_text = "\n".join(page.text for page in pdf_doc.pages)

            if not full_text.strip():
                logger.warning(f"  No text extracted from {file_path.name}")
                quarantined_count += 1
                continue

            logger.success(
                f"  Successfully processed {file_path.name}: {len(pdf_doc.pages)} pages, {len(full_text)} chars"
            )
            success_count += 1

            # Classify document (safe fallback if method changes)
            try:
                doc_type, _ = classifier.classify(file_path)
                quick_doc_type = doc_type
            except Exception as _e:
                # Fallback: infer from filename; for manual runs, default to "Manual" if name matches
                name_lower = file_path.name.lower()
                if "manual" in name_lower:
                    quick_doc_type = "Manual"
                else:
                    quick_doc_type = "unknown"

            # Chunk document
            chunks = chunker.chunk_document(
                pdf_doc, doc_id=f"REINGEST_{file_path.stem}"
            )

            result = {
                "file": str(file_path),
                "status": "processed",
                "pages": len(pdf_doc.pages),
                "chunks": len(chunks),
                "text_length": len(full_text),
                "doc_type": quick_doc_type,
            }
            results.append(result)

        except RecursionError as e:
            logger.error(
                f"  Recursion error (even without table extraction): {file_path.name} - {e}"
            )
            failed_count += 1
            continue
        except Exception as e:
            logger.error(f"  Error processing {file_path.name}: {e}")
            failed_count += 1
            continue

    except Exception as e:
        logger.error(f"  Fatal error: {file_path.name} - {e}")
        failed_count += 1
        continue

logger.info("=" * 80)
logger.info("Re-ingestion Summary:")
logger.info(f"  Success: {success_count}")
logger.info(f"  Failed: {failed_count}")
logger.info(f"  Quarantined: {quarantined_count}")
logger.info(f"  Total: {len(files)}")
logger.info("=" * 80)

# Save results
results_file = output_dir / "re_ingest_read_error_results.json"
with open(results_file, "w", encoding="utf-8") as f:
    json.dump(
        {
            "summary": {
                "success": success_count,
                "failed": failed_count,
                "quarantined": quarantined_count,
                "total": len(files),
            },
            "results": results,
        },
        f,
        indent=2,
        ensure_ascii=False,
    )

logger.info(f"Results saved to: {results_file}")
