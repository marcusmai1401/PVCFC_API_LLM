"""
Force OCR on page 103 and extract tags
"""
from pathlib import Path

import fitz
from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
doc_id = "test"

# Open page
doc = fitz.open(str(pdf_path))
page = doc[102]  # 0-based

# Force OCR
builder = PageLayoutBuilder()
logger.info("Running OCR on page 103...")
spans, ocr_conf = builder._ocr_fallback(page)
doc.close()

logger.info(f"OCR extracted {len(spans)} spans")
logger.info(f"OCR confidence: {ocr_conf}")

# Show some spans
logger.info("\nSample spans:")
for s in spans[:20]:
    logger.info(f"  '{s.text}' | bbox={s.bbox}")

# Search for FIC and 1134
fic_spans = [s for s in spans if "FIC" in s.text.upper()]
span_1134 = [s for s in spans if "1134" in s.text]

logger.info(f"\nFIC spans: {len(fic_spans)}")
for s in fic_spans:
    logger.info(f"  '{s.text}'")

logger.info(f"\n1134 spans: {len(span_1134)}")
for s in span_1134:
    logger.info(f"  '{s.text}'")

# Try extraction with OCR spans
from app.ingestion.layout.page_layout_builder import PageLayout

layout = PageLayout(
    doc_id=doc_id,
    page=103,
    page_width=1191.0,
    page_height=842.0,
    spans=spans,
    drawings=[],
    is_raster=True,
    ocr_confidence=ocr_conf,
)

extractor = TagExtractor()
tags = extractor.extract_tags(layout)

logger.info(f"\n{'='*60}")
logger.info(f"Extracted {len(tags)} tags:")
for tag in tags:
    logger.info(f"  {tag.tag}")
