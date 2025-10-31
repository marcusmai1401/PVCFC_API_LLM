"""
Debug specific span IDs to understand "308" mystery
"""
from pathlib import Path

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder


def main():
    pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_896a8a91"

    builder = PageLayoutBuilder()

    logger.info("Building layout for page 58...")
    layout = builder.build_layout(pdf_path=pdf_path, page_num=58, doc_id=doc_id)

    # Check specific span IDs from the tag
    target_ids = [164, 163, 209, 172]

    logger.info(f"Checking span IDs: {target_ids}")
    logger.info("=" * 60)

    for sid in target_ids:
        span = next((s for s in layout.spans if s.span_id == sid), None)
        if span:
            logger.info(
                f"Span ID {sid}: '{span.text}' | bbox={span.bbox} | "
                f"font={span.font_size:.1f} | rotation={span.rotation_deg}"
            )
        else:
            logger.warning(f"Span ID {sid}: NOT FOUND")

    # Look for "308" pattern
    logger.info("\n" + "=" * 60)
    logger.info("Searching for '308' spans...")
    span_308 = [s for s in layout.spans if "308" in s.text]
    logger.info(f"Found {len(span_308)} spans containing '308':")
    for s in span_308[:10]:
        logger.info(
            f"  Span {s.span_id}: '{s.text}' | bbox={s.bbox} | "
            f"font={s.font_size:.1f} | rotation={s.rotation_deg}"
        )


if __name__ == "__main__":
    main()
