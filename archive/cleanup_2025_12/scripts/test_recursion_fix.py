#!/usr/bin/env python
"""
Test script to verify recursion error fixes on 7 problematic files
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

from loguru import logger

# Increase recursion limit (matching ingest.py)
sys.setrecursionlimit(10000)

from app.ingestion.document_classifier import DocumentClassifier
from app.ingestion.pdf_processor import PDFProcessor

# 7 files with recursion errors from quarantine.jsonl
test_files = [
    r"D:\Data_Raw\092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf",
    r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Data\002_3N4-S4274342 Data Sheet of Compressor_Rev.01.pdf",
    r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Data\002_3N4-S4274343 datasheet for K06101_Rev.02.pdf",
    r"D:\Data_Raw\K06101_CO2 COMPRESSOR_HITACHI\K06101_CO2 COMPRESSOR_HITACHI\Spare parts\091B_3N4-S4275548-Operational Spare Parts List Of Gear_Rev.0.pdf",
    r"D:\Data_Raw\KT06101_TURBINE_HTC\KT06101_TURBINE_HTC\Data\3N4-S4275356 Steam turbine datasheet.pdf",
    r"D:\Data_Raw\KT06101_TURBINE_HTC\KT06101_TURBINE_HTC\Data\3N4-S4275357.pdf",
    r"D:\Data_Raw\KT06101_TURBINE_HTC\KT06101_TURBINE_HTC\Manual\manual.pdf",
]

logger.info("=" * 80)
logger.info("Testing Recursion Error Fix on 7 Files")
logger.info("=" * 80)

classifier = DocumentClassifier()
success_count = 0
failed_count = 0
partial_count = 0

results = []

for file_path_str in test_files:
    file_path = Path(file_path_str)

    if not file_path.exists():
        logger.warning(f"❌ File not found: {file_path.name}")
        failed_count += 1
        results.append({"file": file_path.name, "status": "not_found"})
        continue

    logger.info(f"\n{'='*80}")
    logger.info(f"Testing: {file_path.name}")
    logger.info(f"{'='*80}")

    try:
        # Classify document type
        doc_type, _ = classifier.classify(file_path)
        logger.info(f"  Document type: {doc_type}")

        # Try processing with table extraction enabled (the source of recursion)
        processor = PDFProcessor(
            enable_ocr=True,
            extract_tables=True,  # Enable to test recursion handling
            table_min_rows=2,
            table_min_cols=2,
            force_ocr_all_pages=(doc_type in {"P&ID", "Drawing", "unknown"}),
            document_type=doc_type,
        )

        pdf_doc = processor.process_pdf(file_path)

        # Check results
        full_text = "\n".join(page.text for page in pdf_doc.pages)

        if len(pdf_doc.pages) == 0:
            logger.error(f"  ❌ FAILED: No pages extracted")
            failed_count += 1
            results.append(
                {"file": file_path.name, "status": "failed", "reason": "no_pages"}
            )
        elif not full_text.strip():
            logger.warning(
                f"  ⚠️  PARTIAL: {len(pdf_doc.pages)} pages extracted but no text"
            )
            partial_count += 1
            results.append(
                {
                    "file": file_path.name,
                    "status": "partial",
                    "pages": len(pdf_doc.pages),
                    "text_length": 0,
                }
            )
        else:
            logger.success(
                f"  ✅ SUCCESS: {len(pdf_doc.pages)} pages, "
                f"{len(full_text)} chars, {len(full_text.split())} words"
            )
            success_count += 1
            results.append(
                {
                    "file": file_path.name,
                    "status": "success",
                    "pages": len(pdf_doc.pages),
                    "text_length": len(full_text),
                    "word_count": len(full_text.split()),
                    "doc_type": doc_type,
                }
            )

    except RecursionError as e:
        logger.error(f"  ❌ RECURSION ERROR STILL OCCURS: {e}")
        failed_count += 1
        results.append(
            {"file": file_path.name, "status": "recursion_error", "error": str(e)}
        )

    except Exception as e:
        logger.error(f"  ❌ ERROR: {e}")
        failed_count += 1
        results.append({"file": file_path.name, "status": "error", "error": str(e)})

# Summary
logger.info("\n" + "=" * 80)
logger.info("Test Summary")
logger.info("=" * 80)
logger.info(f"✅ Success: {success_count}/{len(test_files)}")
logger.info(
    f"⚠️  Partial: {partial_count}/{len(test_files)} (pages extracted but no text)"
)
logger.info(f"❌ Failed: {failed_count}/{len(test_files)}")
logger.info("=" * 80)

# Save results
output_file = PROJECT_ROOT / "test_recursion_fix_results.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(
        {
            "summary": {
                "total": len(test_files),
                "success": success_count,
                "partial": partial_count,
                "failed": failed_count,
            },
            "results": results,
        },
        f,
        indent=2,
        ensure_ascii=False,
    )

logger.info(f"\nResults saved to: {output_file}")

# Exit code: 0 if all success, 1 if any failures
sys.exit(0 if failed_count == 0 else 1)
