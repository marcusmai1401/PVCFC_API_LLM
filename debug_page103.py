"""
Debug page 103 - why are there no tags?
"""
from pathlib import Path

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, 103, "test")

logger.info(f"Page 103: {len(layout.spans)} total spans")
logger.info(f"Page dimensions: {layout.page_width}x{layout.page_height}")
logger.info(f"Is raster: {layout.is_raster}")

# Check for FIC
fic_spans = [s for s in layout.spans if "FIC" in s.text.upper()]
logger.info(f"\nFound {len(fic_spans)} spans containing 'FIC':")
for s in fic_spans[:10]:
    logger.info(f"  '{s.text}' | bbox={s.bbox}")

# Check for 1134
span_1134 = [s for s in layout.spans if "1134" in s.text]
logger.info(f"\nFound {len(span_1134)} spans containing '1134':")
for s in span_1134[:10]:
    logger.info(f"  '{s.text}' | bbox={s.bbox}")

# Check for 06
span_06 = [s for s in layout.spans if s.text.strip() == "06"]
logger.info(f"\nFound {len(span_06)} spans with '06'")

# Try extraction
extractor = TagExtractor()
tags = extractor.extract_tags(layout)
logger.info(f"\nExtracted {len(tags)} tags from page 103")
