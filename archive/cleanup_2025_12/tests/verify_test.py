"""Verify system after fix"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)
os.environ["ENABLE_PID_TAGS"] = "true"

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_config

config = get_config()

print("=" * 80)
print("SYSTEM VERIFICATION")
print("=" * 80)
print(f"ENABLE_PID_TAGS: {config.ENABLE_PID_TAGS}")
print(f"ARTIFACTS_DIR: {config.ARTIFACTS_DIR}")
print(f"ENTITIES_DIR: {config.ENTITIES_DIR}")
print(f"LAYOUT_DIR: {config.LAYOUT_DIR}")
print(f"CROPS_DIR: {config.CROPS_DIR}")
print(f"LOGS_DIR: {config.LOGS_DIR}")
print()

# Check directories exist
print("Directory Status:")
print(f"  ARTIFACTS_DIR exists: {config.ARTIFACTS_DIR.exists()}")
print(f"  ENTITIES_DIR exists: {config.ENTITIES_DIR.exists()}")
print(f"  LAYOUT_DIR exists: {config.LAYOUT_DIR.exists()}")
print(f"  CROPS_DIR exists: {config.CROPS_DIR.exists()}")
print(f"  LOGS_DIR exists: {config.LOGS_DIR.exists()}")
print()

# Create directories
print("Creating directories...")
config.ensure_pid_tags_dirs()
print("Done!")
print()

print("Directory Status After Creation:")
print(f"  ENTITIES_DIR exists: {config.ENTITIES_DIR.exists()}")
print(f"  LAYOUT_DIR exists: {config.LAYOUT_DIR.exists()}")
print(f"  CROPS_DIR exists: {config.CROPS_DIR.exists()}")
print(f"  LOGS_DIR exists: {config.LOGS_DIR.exists()}")
print()

# Check for artifacts from previous test
tags_file = config.ENTITIES_DIR / "tags.jsonl"
telemetry_file = config.LOGS_DIR / "tag_extraction_telemetry.jsonl"

print("Artifact Status:")
print(f"  tags.jsonl exists: {tags_file.exists()}")
if tags_file.exists():
    lines = sum(1 for _ in open(tags_file))
    size_kb = tags_file.stat().st_size / 1024
    print(f"    Lines: {lines}")
    print(f"    Size: {size_kb:.1f} KB")

print(f"  telemetry.jsonl exists: {telemetry_file.exists()}")
if telemetry_file.exists():
    lines = sum(1 for _ in open(telemetry_file))
    size_kb = telemetry_file.stat().st_size / 1024
    print(f"    Lines: {lines}")
    print(f"    Size: {size_kb:.1f} KB")

print()
print("=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
