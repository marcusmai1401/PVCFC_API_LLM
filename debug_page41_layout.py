"""
Debug script to inspect page 41 layout and spans to understand variant extraction issue
"""
import json
from pathlib import Path

from loguru import logger

from app.config import get_config
from app.ingestion.layout.page_layout_builder import PageLayoutBuilder


def main():
    config = get_config()

    # PDF path
    pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return

    # Build layout for page 41 (0-indexed: page 40)
    builder = PageLayoutBuilder()
    doc_id = "DOCID_01._P_ID_Ammonia_Unit_Rev12_04000_896a8a91"

    logger.info(f"Processing page 41 from {pdf_path}")
    layout = builder.build_layout(
        pdf_path=pdf_path, page_num=41, doc_id=doc_id  # 1-based
    )

    logger.info(
        f"Page 41 layout: {len(layout.spans)} spans, {len(layout.drawings)} drawings"
    )

    # Filter spans near "PSV" and "3926"
    psv_spans = [s for s in layout.spans if "PSV" in s.text.upper()]
    num_3926_spans = [s for s in layout.spans if "3926" in s.text]

    logger.info(f"Found {len(psv_spans)} spans containing 'PSV'")
    logger.info(f"Found {len(num_3926_spans)} spans containing '3926'")

    # Find the specific tag region
    target_spans = []
    for s in layout.spans:
        text = s.text.strip()
        if text in ["04", "PSV", "3926", "3926I", "I"]:
            target_spans.append(s)
            logger.info(
                f"Span: '{text}' | bbox: {s.bbox} | font: {s.font_size:.1f} | "
                f"rotation: {s.rotation_deg:.1f}° | span_id: {s.span_id}"
            )

    # Check for single-letter spans near the target region
    # Find PSV span first
    psv_span = None
    for s in psv_spans:
        if s.text.strip() == "PSV":
            psv_span = s
            break

    if psv_span:
        psv_bbox = psv_span.bbox
        psv_x = (psv_bbox[0] + psv_bbox[2]) / 2
        psv_y = (psv_bbox[1] + psv_bbox[3]) / 2

        # Find all single-letter spans within 100pt radius
        radius = 100
        nearby_letters = []
        for s in layout.spans:
            if len(s.text.strip()) == 1 and s.text.strip().isalpha():
                s_x = (s.bbox[0] + s.bbox[2]) / 2
                s_y = (s.bbox[1] + s.bbox[3]) / 2
                dist = ((s_x - psv_x) ** 2 + (s_y - psv_y) ** 2) ** 0.5
                if dist < radius:
                    nearby_letters.append((s, dist))

        nearby_letters.sort(key=lambda x: x[1])

        logger.info(f"\n{'='*60}")
        logger.info(f"Single-letter spans near PSV (within {radius}pt):")
        for s, dist in nearby_letters[:10]:
            logger.info(
                f"  Letter: '{s.text}' | distance: {dist:.1f}pt | "
                f"bbox: {s.bbox} | font: {s.font_size:.1f}"
            )

    # Save detailed layout to file for inspection
    output = {
        "doc_id": layout.doc_id,
        "page": layout.page,
        "page_width": layout.page_width,
        "page_height": layout.page_height,
        "total_spans": len(layout.spans),
        "target_spans": [
            {
                "text": s.text,
                "bbox": s.bbox,
                "font_size": s.font_size,
                "rotation_deg": s.rotation_deg,
                "span_id": s.span_id,
            }
            for s in target_spans
        ],
        "nearby_single_letters": [
            {
                "text": s.text,
                "bbox": s.bbox,
                "font_size": s.font_size,
                "distance_from_psv": dist,
                "span_id": s.span_id,
            }
            for s, dist in (nearby_letters[:20] if psv_span else [])
        ],
    }

    output_file = Path("debug_page41_layout.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"\nLayout details saved to: {output_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
