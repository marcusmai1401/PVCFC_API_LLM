"""
Deep debug for TXI 2077 - trace through entire assembly process
"""
from pathlib import Path

from loguru import logger

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor


def main():
    pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
    doc_id = "test"

    builder = PageLayoutBuilder()
    layout = builder.build_layout(pdf_path, 17, doc_id)

    extractor = TagExtractor()

    # Get valid spans after exclusion
    valid_spans = extractor._filter_exclusion_zones(layout, layout.spans)

    # Find TXI and 2077
    txi_spans = [s for s in valid_spans if s.text.strip() == "TXI"]
    span_2077 = [
        s for s in valid_spans if "2077" in s.text and s.text.strip() == "2077"
    ]
    span_04 = [s for s in valid_spans if s.text.strip() == "04"]

    logger.info(f"Valid spans: {len(valid_spans)}")
    logger.info(f"TXI spans after filter: {len(txi_spans)}")
    logger.info(f"2077 spans (exact): {len(span_2077)}")
    logger.info(f"04 spans: {len(span_04)}")

    if not txi_spans:
        logger.error("No TXI spans found!")
        return

    if not span_2077:
        logger.error("No exact 2077 spans found!")
        logger.info("Spans containing 2077:")
        for s in valid_spans:
            if "2077" in s.text:
                logger.info(f"  '{s.text}' | bbox={s.bbox} | rotation={s.rotation_deg}")
        return

    txi = txi_spans[0]
    suffix = span_2077[0]

    logger.info(
        f"\nTXI: bbox={txi.bbox}, rotation={txi.rotation_deg}, font={txi.font_size}"
    )
    logger.info(
        f"2077: bbox={suffix.bbox}, rotation={suffix.rotation_deg}, font={suffix.font_size}"
    )

    # Check if TXI is in prefix anchors
    prefix_anchors = [s for s in valid_spans if s.text in extractor.prefix_whitelist]
    logger.info(f"\nTotal PREFIX anchors: {len(prefix_anchors)}")
    logger.info(f"TXI in anchors: {txi in prefix_anchors}")

    if txi not in prefix_anchors:
        logger.error("TXI NOT in prefix anchors!")
        logger.info(
            f"TXI text: '{txi.text}' | In whitelist: {txi.text in extractor.prefix_whitelist}"
        )
        return

    # Now manually try to assemble triplet with TXI as anchor
    logger.info("\n" + "=" * 60)
    logger.info("Attempting triplet assembly with TXI anchor...")

    triplet = extractor._assemble_triplet(txi, valid_spans, layout)

    if triplet:
        logger.success(
            f"✓ Triplet assembled: {triplet['unit_span'].text if triplet['unit_span'] else ''} TXI {triplet['suffix_span'].text}"
        )
        logger.info(f"  Score: {triplet['score']}")
    else:
        logger.error("✗ Triplet assembly FAILED")

        # Debug why
        logger.info("\nChecking unit candidates near TXI...")
        txi_x = (txi.bbox[0] + txi.bbox[2]) / 2
        txi_y = (txi.bbox[1] + txi.bbox[3]) / 2
        search_radius = max(100, 20 * txi.font_size)

        unit_candidates = []
        for s in valid_spans:
            if s.span_id == txi.span_id or not extractor.unit_regex.match(s.text):
                continue
            s_x = (s.bbox[0] + s.bbox[2]) / 2
            s_y = (s.bbox[1] + s.bbox[3]) / 2
            dist = ((s_x - txi_x) ** 2 + (s_y - txi_y) ** 2) ** 0.5
            if dist <= search_radius:
                unit_candidates.append((s, dist))

        unit_candidates.sort(key=lambda x: x[1])
        logger.info(
            f"Found {len(unit_candidates)} UNIT candidates within {search_radius:.0f}pt:"
        )
        for s, dist in unit_candidates[:10]:
            logger.info(f"  '{s.text}': dist={dist:.1f}pt, bbox={s.bbox}")

        logger.info("\nChecking suffix candidates near TXI...")
        suffix_candidates = []
        for s in valid_spans:
            if s.span_id == txi.span_id or not extractor.suffix_regex.match(s.text):
                continue
            s_x = (s.bbox[0] + s.bbox[2]) / 2
            s_y = (s.bbox[1] + s.bbox[3]) / 2
            dist = ((s_x - txi_x) ** 2 + (s_y - txi_y) ** 2) ** 0.5
            if dist <= search_radius:
                suffix_candidates.append((s, dist))

        suffix_candidates.sort(key=lambda x: x[1])
        logger.info(
            f"Found {len(suffix_candidates)} SUFFIX candidates within {search_radius:.0f}pt:"
        )
        for s, dist in suffix_candidates[:10]:
            logger.info(
                f"  '{s.text}': dist={dist:.1f}pt, bbox={s.bbox}, rotation={s.rotation_deg}"
            )

        # Check alignment score for closest 2077
        if suffix_candidates:
            closest_2077 = [s for s, d in suffix_candidates if s.text == "2077"]
            if closest_2077:
                score = extractor._score_alignment(
                    txi, closest_2077[0], "near", txi.font_size
                )
                logger.info(f"\nAlignment score (TXI + 2077): {score}")
                if score <= 0:
                    logger.warning("Score is 0 - alignment check failed!")
                    logger.info(f"  TXI rotation: {txi.rotation_deg}")
                    logger.info(f"  2077 rotation: {closest_2077[0].rotation_deg}")
                    logger.info(
                        f"  Rotation delta: {abs(txi.rotation_deg - closest_2077[0].rotation_deg)}"
                    )


if __name__ == "__main__":
    main()
