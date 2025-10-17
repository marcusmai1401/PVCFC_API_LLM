#!/usr/bin/env python
"""
Simple Test for CAD Tags Extraction
Run: python test_cad_extraction_simple.py
"""
import os
import sys
import time
from pathlib import Path

# CRITICAL: Load .env BEFORE any app imports
from dotenv import load_dotenv

load_dotenv(override=True)

# Force enable feature via environment
os.environ["ENABLE_PID_TAGS"] = "true"
os.environ["GATE_MODE"] = "auto"

print("=" * 80)
print("CAD TAGS EXTRACTION - SIMPLE TEST")
print("=" * 80)
print(f"ENABLE_PID_TAGS from env: {os.environ.get('ENABLE_PID_TAGS')}")
print()

# NOW import app modules (after .env loaded)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_config
from app.ingestion.tags.orchestrator import TagExtractionOrchestrator

config = get_config()
print(f"Config ENABLE_PID_TAGS: {config.ENABLE_PID_TAGS}")
print(f"Config GATE_MODE: {config.GATE_MODE}")
print()

if not config.ENABLE_PID_TAGS:
    print("ERROR: Feature still disabled despite env vars!")
    sys.exit(1)

# Initialize orchestrator
print("Initializing orchestrator...")
orch = TagExtractionOrchestrator(enable_crops=False, lazy_crops=True)
print(f"Orchestrator enabled: {orch.enabled}")
print()

if not orch.enabled:
    print("ERROR: Orchestrator disabled!")
    sys.exit(1)

# Test PDF
pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
doc_id = "test_ammonia_001"

if not pdf_path.exists():
    print(f"ERROR: PDF not found: {pdf_path}")
    sys.exit(1)

print(f"Processing: {pdf_path.name}")
print(f"Doc ID: {doc_id}")
print()

# Process
start_time = time.perf_counter()

try:
    result = orch.process_document(pdf_path, doc_id)
    elapsed = time.perf_counter() - start_time

    if result:
        print("=" * 80)
        print("SUCCESS!")
        print("=" * 80)
        print(f"Tags extracted: {result.get('tags_extracted', 0)}")
        print(f"Pages processed: {result.get('pages_processed', 0)}")
        print(f"Crops generated: {result.get('crops_generated', 0)}")
        print(f"Elapsed: {elapsed:.1f}s")
        print()

        # Check artifacts
        print("Artifacts:")
        tags_file = config.ENTITIES_DIR / "tags.jsonl"
        if tags_file.exists():
            lines = sum(1 for _ in open(tags_file))
            print(f"  tags.jsonl: {lines} lines")

        log_file = config.LOGS_DIR / "tag_extraction_telemetry.jsonl"
        if log_file.exists():
            print(f"  telemetry.jsonl: exists")

    else:
        print("Document is not CAD-like or no tags extracted")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 80)
print("Test completed!")
print("=" * 80)
