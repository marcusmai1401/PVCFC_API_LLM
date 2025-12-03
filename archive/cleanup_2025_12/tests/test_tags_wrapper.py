#!/usr/bin/env python
"""Test Tag Extraction - Fixed version with dotenv"""
import sys
from pathlib import Path

from dotenv import load_dotenv

# Force reload .env BEFORE importing app modules
load_dotenv(override=True)

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Now run the original test
import subprocess

result = subprocess.run(
    [sys.executable, str(PROJECT_ROOT / "tools" / "test_tag_extraction_original.py")]
    + sys.argv[1:]
)
sys.exit(result.returncode)
