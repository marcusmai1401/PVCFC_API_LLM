"""
Debug page 17 to find missing tag 04 TXI 2077
"""
from pathlib import Path

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor


def main():
    pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_896a8a91"

    builder = PageLayoutBuilder()
    extractor = TagExtractor()

    logger.info("Building layout for page 17...")
    layout = builder.build_layout(pdf_path=pdf_path, page_num=17, doc_id=doc_id)

    logger.info(f"Page 17: {len(layout.spans)} spans")

    # Search for TXI prefix
    txi_spans = [s for s in layout.spans if s.text.strip() == "TXI"]
    logger.info(f"Found {len(txi_spans)} 'TXI' spans:")
    for s in txi_spans:
        logger.info(f"  Span {s.span_id}: bbox={s.bbox}, rotation={s.rotation_deg}")

    # Search for 2077
    span_2077 = [s for s in layout.spans if "2077" in s.text]
    logger.info(f"\nFound {len(span_2077)} spans containing '2077':")
    for s in span_2077:
        logger.info(
            f"  Span {s.span_id}: '{s.text}' | bbox={s.bbox} | rotation={s.rotation_deg}"
        )

    # Search for 04
    span_04 = [s for s in layout.spans if s.text.strip() == "04"]
    logger.info(f"\nFound {len(span_04)} spans with '04'")

    # Try extracting tags
    logger.info("\n" + "=" * 60)
    logger.info("Extracting tags...")
    tags = extractor.extract_tags(layout)

    logger.info(f"Extracted {len(tags)} tags:")
    for tag in tags:
        logger.info(f"  {tag.tag}")

    # Check if TXI is in prefix whitelist
    logger.info("\n" + "=" * 60)
    if "TXI" in extractor.prefix_whitelist:
        logger.info("✓ TXI is in prefix whitelist")
    else:
        logger.error("✗ TXI is NOT in prefix whitelist!")
        logger.info(f"Whitelist has {len(extractor.prefix_whitelist)} prefixes")


if __name__ == "__main__":
    main()
