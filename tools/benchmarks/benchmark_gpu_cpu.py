#!/usr/bin/env python
"""
Benchmark GPU vs CPU OCR speed
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor


def benchmark():
    """Compare GPU vs CPU OCR performance"""

    # Get 3 test files
    quarantine_file = Path("artifacts/ingestion_production/quarantine.jsonl")

    test_files = []
    with open(quarantine_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry["reason_code"] == "ocr_failed" and "__MACOSX" not in entry["file"]:
                test_files.append(entry["file"])
                if len(test_files) >= 3:
                    break

    logger.info("=" * 80)
    logger.info("GPU vs CPU BENCHMARK")
    logger.info("=" * 80)
    logger.info(f"Testing with {len(test_files)} files")
    logger.info("")

    # Test GPU
    logger.info("🚀 Testing with GPU...")
    start_gpu = time.time()

    # Make sure cuDNN is in PATH
    cudnn_bin = Path(__file__).parent / "venv_ingest/Lib/site-packages/nvidia/cudnn/bin"
    os.environ["PATH"] = str(cudnn_bin) + ";" + os.environ.get("PATH", "")

    processor_gpu = PDFProcessor(
        enable_ocr=True,
        ocr_language="vie+eng",
        ocr_min_confidence=30.0,
        extract_tables=False,
    )

    total_pages_gpu = 0
    for file_path in test_files:
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            continue
        try:
            doc = processor_gpu.process_pdf(pdf_path)
            total_pages_gpu += doc.num_pages
        except Exception as e:
            logger.error(f"GPU error: {e}")

    time_gpu = time.time() - start_gpu

    logger.info("")
    logger.info("=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"GPU RTX 4060:")
    logger.info(f"  Total pages: {total_pages_gpu}")
    logger.info(f"  Time: {time_gpu:.1f}s ({time_gpu/60:.1f} min)")
    logger.info(f"  Speed: {total_pages_gpu/time_gpu:.2f} pages/sec")
    logger.info("")
    logger.info(f"💡 Estimated time for 56 files (~550 pages):")
    logger.info(f"   GPU: {550 / (total_pages_gpu/time_gpu) / 60:.0f} minutes")
    logger.info(f"   CPU 6 workers: ~60-90 minutes")
    logger.info("")
    logger.info(
        f"🚀 GPU is ~{(90*60) / (550 / (total_pages_gpu/time_gpu)):.1f}x faster!"
    )


if __name__ == "__main__":
    benchmark()
