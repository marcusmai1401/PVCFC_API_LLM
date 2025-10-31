"""
Test OCR and tag extraction for page 103 specifically
"""
from pathlib import Path

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_896a8a91"

logger.info("Testing page 103 with OCR enabled...")

# Build layout WITH OCR
builder = PageLayoutBuilder(enable_ocr=True)
layout = builder.build_layout(pdf_path, 103, doc_id)

logger.info(f"Page 103 layout:")
logger.info(f"  Total spans: {len(layout.spans)}")
logger.info(f"  Is raster: {layout.is_raster}")
logger.info(f"  OCR confidence: {layout.ocr_confidence}")
logger.info(f"  Page dimensions: {layout.page_width}x{layout.page_height}")

# Check for FIC and 1134
fic_spans = [s for s in layout.spans if "FIC" in s.text.upper()]
span_1134 = [s for s in layout.spans if "1134" in s.text]
span_06 = [s for s in layout.spans if s.text.strip() == "06"]

logger.info(f"\nFound {len(fic_spans)} FIC spans")
logger.info(f"Found {len(span_1134)} '1134' spans")
logger.info(f"Found {len(span_06)} '06' spans")

if fic_spans:
    logger.info("\nFIC spans:")
    for s in fic_spans[:5]:
        logger.info(f"  '{s.text}' @ {s.bbox}")

if span_1134:
    logger.info("\n1134 spans:")
    for s in span_1134[:5]:
        logger.info(f"  '{s.text}' @ {s.bbox}")

# Try tag extraction
extractor = TagExtractor()
tags = extractor.extract_tags(layout)

logger.info(f"\n{'='*60}")
logger.info(f"Extracted {len(tags)} tags from page 103")

if tags:
    logger.info("Tags:")
    for tag in tags:
        logger.info(f"  {tag.tag}")
else:
    logger.warning("NO TAGS EXTRACTED!")
