#!/usr/bin/env python
"""
Quick test to verify tags.jsonl is preserved when P&ID extraction is disabled
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Temporarily disable P&ID tags
os.environ["ENABLE_PID_TAGS"] = "false"

# Force reload config
import app.config.pipeline_config as config_module

config_module._config_instance = None

from loguru import logger

from tools.ingest import IngestionPipeline

# Setup test
tags_file = (
    PROJECT_ROOT / "artifacts" / "ingestion_production" / "entities" / "tags.jsonl"
)
tags_before_count = 0

if tags_file.exists():
    with open(tags_file, "r") as f:
        tags_before_count = sum(1 for line in f if line.strip())
    print(f"✅ Tags before cleanup: {tags_before_count}")
else:
    print("❌ No tags.jsonl file exists")
    sys.exit(1)

# Initialize pipeline with P&ID disabled
pipeline = IngestionPipeline(
    source_dir=PROJECT_ROOT / "data" / "pdfs",
    output_dir=PROJECT_ROOT / "artifacts" / "ingestion_production",
    workers=1,
    enable_pid_tags=False,  # Explicitly disabled
)

# Call cleanup method
logger.info("Testing cleanup with P&ID disabled...")
pipeline._setup_output_dirs()
pipeline._cleanup_jsonl_files()

# Check if tags.jsonl still exists
if tags_file.exists():
    with open(tags_file, "r") as f:
        tags_after_count = sum(1 for line in f if line.strip())

    if tags_after_count == tags_before_count:
        print(f"✅ SUCCESS: Tags preserved! Count: {tags_after_count}")
        sys.exit(0)
    else:
        print(
            f"❌ FAILED: Tag count changed from {tags_before_count} to {tags_after_count}"
        )
        sys.exit(1)
else:
    print("❌ FAILED: tags.jsonl was deleted")
    sys.exit(1)
