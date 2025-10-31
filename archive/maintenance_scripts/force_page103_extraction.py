"""
Force OCR on page 103 regardless of vector text, then extract tags
"""
from pathlib import Path

import fitz
from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayout, PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_896a8a91"

logger.info("Opening PDF and forcing OCR on page 103...")

# Open page directly
doc = fitz.open(str(pdf_path))
page = doc[102]  # 0-based

# Force OCR
builder = PageLayoutBuilder(enable_ocr=True)
spans, ocr_conf = builder._ocr_fallback(page)

logger.info(f"OCR extracted {len(spans)} spans")
logger.info(f"OCR confidence: {ocr_conf}")

# Check for target strings
fic_spans = [s for s in spans if "FIC" in s.text.upper()]
span_1134 = [s for s in spans if "1134" in s.text]
span_06 = [s for s in spans if s.text.strip() in ["06", "6"]]

logger.info(f"\nFIC spans: {len(fic_spans)}")
for s in fic_spans[:5]:
    logger.info(f"  '{s.text}'")

logger.info(f"\n1134 spans: {len(span_1134)}")
for s in span_1134[:5]:
    logger.info(f"  '{s.text}'")

logger.info(f"\n06 spans: {len(span_06)}")
for s in span_06[:5]:
    logger.info(f"  '{s.text}'")

# Create layout with OCR spans
layout = PageLayout(
    doc_id=doc_id,
    page=103,
    page_width=page.rect.width,
    page_height=page.rect.height,
    spans=spans,
    drawings=[],
    is_raster=True,
    ocr_confidence=ocr_conf,
)

doc.close()

# Extract tags
extractor = TagExtractor()
tags = extractor.extract_tags(layout)

logger.info(f"\n{'='*60}")
logger.info(f"Extracted {len(tags)} tags")

if tags:
    logger.info("\nTags extracted:")
    for tag in tags:
        logger.info(f"  {tag.tag} (page {tag.page})")

    # Save to file
    import json

    output_file = Path("page103_tags.jsonl")
    with open(output_file, "w", encoding="utf-8") as f:
        for tag in tags:
            f.write(tag.model_dump_json() + "\n")
    logger.success(f"Saved {len(tags)} tags to {output_file}")
else:
    logger.error("NO TAGS EXTRACTED!")
