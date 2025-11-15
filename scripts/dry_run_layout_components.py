#!/usr/bin/env python
"""
Dry run: build layout for Ammonia P&ID page 56 and extract components
(No code modification; diagnostics only)
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from loguru import logger

# Load env
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

from app.config import get_config

# Imports from project
from app.ingestion.layout.page_layout_builder import PageLayout, PageLayoutBuilder
from app.rag.spatial.component_extractor import SpatialComponentExtractor

# Target file and parameters
PDF_PATH = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
DOC_ID = "AMMONIA_04000_DRYRUN"
PAGE_NUM = 56  # 1-based

if not PDF_PATH.exists():
    logger.error(f"PDF not found: {PDF_PATH}")
    sys.exit(1)

logger.info("=" * 80)
logger.info("Dry Run: Build layout and extract components (single page)")
logger.info("=" * 80)
logger.info(f"PDF: {PDF_PATH}")
logger.info(f"Doc ID: {DOC_ID}")
logger.info(f"Page: {PAGE_NUM}")

# Build layout
builder = PageLayoutBuilder(enable_ocr=True, enable_drawings=True)
layout: PageLayout = builder.build_layout(PDF_PATH, PAGE_NUM, DOC_ID)

# Save layout to configured LAYOUT_DIR
config = get_config()
layout_dir = Path(config.LAYOUT_DIR)
layout_dir.mkdir(parents=True, exist_ok=True)
builder.save_layout(layout, layout_dir)

layout_file = layout_dir / f"page_{DOC_ID}_{PAGE_NUM}.json"
logger.info(f"Saved layout file: {layout_file}")

# Extract components
extractor = SpatialComponentExtractor()
components = extractor.extract_components(layout)

units = [c for c in components if c.component_type == "unit"]
prefixes = [c for c in components if c.component_type == "prefix"]
suffixes = [c for c in components if c.component_type == "suffix"]

logger.info(
    f"Total components: {len(components)} (units={len(units)}, prefixes={len(prefixes)}, suffixes={len(suffixes)})"
)

# Check target tokens
TARGETS = {"04": [], "PV": [], "5012": []}
for c in components:
    if c.text.upper() in TARGETS:
        TARGETS[c.text.upper()].append(c)

for key, hits in TARGETS.items():
    if hits:
        logger.success(f"Found '{key}' {len(hits)} time(s)")
        for h in hits[:3]:
            logger.info(f"  - {h.component_type} @ page {h.page}, bbox={h.bbox}")
    else:
        logger.warning(f"NOT found: '{key}' on page {PAGE_NUM}")

# Exit code: 0 if at least all three tokens are present
passed = all(len(hits) > 0 for hits in TARGETS.values())
logger.info("=" * 80)
logger.info(f"PASS CRITERIA: All tokens present -> {passed}")
logger.info("=" * 80)

sys.exit(0 if passed else 1)
