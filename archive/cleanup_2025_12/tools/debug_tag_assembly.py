#!/usr/bin/env python
"""Debug tag assembly on specific page"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force fresh import
import importlib
import sys

if "app.ingestion.tags.tag_extractor" in sys.modules:
    importlib.reload(sys.modules["app.config.pipeline_config"])
    importlib.reload(sys.modules["app.ingestion.tags.tag_extractor"])

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

# Configure verbose logging
logger.remove()
logger.add(sys.stderr, level="DEBUG")


def main():
    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
    page_num = 13  # Page with "04 PU 2049"

    print(f"\n{'='*80}")
    print(f"DEBUG TAG ASSEMBLY - Page {page_num}")
    print(f"{'='*80}\n")

    # Build layout
    print("Building page layout...")
    layout_builder = PageLayoutBuilder()
    layout = layout_builder.build_layout(pdf_path, page_num, doc_id="debug")

    print(f"Total spans: {len(layout.spans)}")
    print(f"Page dimensions: {layout.page_width} x {layout.page_height}")

    # Extract tags with verbose logging
    print("\nInitializing tag extractor...")
    extractor = TagExtractor()

    # Calculate footer threshold from extractor config
    footer_margin = extractor.filters["exclude_layout"]["header_footer_margin_ratio"]
    footer_y = layout.page_height * (1 - footer_margin)
    print(f"Footer threshold: y >= {footer_y:.1f} (margin={footer_margin*100:.1f}%)")

    # Get roles
    roles = extractor._classify_token_roles(layout.spans)

    # Count by role
    role_counts = {}
    for role in roles.values():
        role_counts[role] = role_counts.get(role, 0) + 1

    print("\nToken role counts:")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")

    # Check PU before filtering
    print("\nBefore exclusion filter:")
    merged_spans_pre = extractor._classify_token_roles(layout.spans)
    pu_before = [s for s in layout.spans if s.text == "PU"]
    print(f"  PU spans found: {len(pu_before)}")
    for s in pu_before[:3]:
        print(f"    '{s.text}' at bbox {s.bbox}")

    # Filter exclusions
    valid_spans = extractor._filter_exclusion_zones(layout, layout.spans)
    print(f"\nAfter exclusion filter: {len(valid_spans)} spans")

    # Check PU after filtering
    pu_after = [s for s in valid_spans if s.text == "PU"]
    print(f"  PU spans remaining: {len(pu_after)}")

    # Find CODE anchors
    code_anchors = [s for s in valid_spans if s.text in extractor.code_whitelist]
    print(f"CODE anchors: {len(code_anchors)}")

    # Debug: Show ALL spans with digits
    print("\nAll digit-containing spans (first 20):")
    digit_spans = [s for s in valid_spans if any(c.isdigit() for c in s.text)]
    for i, span in enumerate(digit_spans[:20], 1):
        print(f"  {i}. '{span.text}'")

    # Search for "04 PU 2049" components WITH ROTATION INFO
    print("\n" + "=" * 60)
    print("SEARCHING FOR TAG COMPONENTS: 04 PU 2049 (with rotation check)")
    print("=" * 60)

    # Search PU first (anchor)
    print("\n[CODE] Searching for 'PU'...")
    code_pu = [s for s in valid_spans if s.text == "PU"]
    print(f"  Found {len(code_pu)} instances")
    for i, span in enumerate(code_pu[:5], 1):
        sx = (span.bbox[0] + span.bbox[2]) / 2
        sy = (span.bbox[1] + span.bbox[3]) / 2
        rot = span.rotation_deg
        print(
            f"    {i}. 'PU' at ({sx:.1f}, {sy:.1f}), rotation={rot}deg, bbox={span.bbox}"
        )

    if code_pu:
        pu = code_pu[0]
        pu_x = (pu.bbox[0] + pu.bbox[2]) / 2
        pu_y = (pu.bbox[1] + pu.bbox[3]) / 2

        # Find ALL spans within 50px of PU
        print(f"\nAll spans within 50px of PU (x={pu_x:.1f}, y={pu_y:.1f}):")
        nearby = []
        for s in valid_spans:
            if s.span_id == pu.span_id:
                continue
            sx = (s.bbox[0] + s.bbox[2]) / 2
            sy = (s.bbox[1] + s.bbox[3]) / 2
            dist = ((sx - pu_x) ** 2 + (sy - pu_y) ** 2) ** 0.5
            if dist <= 50:
                nearby.append((s, sx, sy, dist))

        nearby.sort(key=lambda x: x[3])

        for s, sx, sy, dist in nearby[:15]:
            dx = sx - pu_x
            dy = sy - pu_y
            direction = ""
            if abs(dy) > abs(dx):
                direction = "[below]" if dy > 0 else "[above]"
            else:
                direction = "[right]" if dx > 0 else "[left]"
            print(
                f"  '{s.text}' at ({sx:.1f}, {sy:.1f}), dy={dy:+.1f}, dist={dist:.1f} {direction}, rot={s.rotation_deg}deg"
            )

    print("\n" + "=" * 60)

    # Find PU CODE instances
    print("\nSearching for 'PU' CODE spans...")
    pu_spans = [s for s in valid_spans if s.text == "PU"]
    if pu_spans:
        for pu in pu_spans[:3]:
            pu_x = (pu.bbox[0] + pu.bbox[2]) / 2
            pu_y = (pu.bbox[1] + pu.bbox[3]) / 2
            print(f"\nPU at ({pu_x:.1f}, {pu_y:.1f}):")

            # Find nearby spans within 50px
            nearby = [
                (
                    s,
                    ((s.bbox[0] + s.bbox[2]) / 2 - pu_x) ** 2
                    + ((s.bbox[1] + s.bbox[3]) / 2 - pu_y) ** 2,
                )
                for s in valid_spans
                if s.span_id != pu.span_id
            ]
            nearby.sort(key=lambda x: x[1])

            print("  Nearest 10 spans:")
            for s, dist in nearby[:10]:
                sx = (s.bbox[0] + s.bbox[2]) / 2
                sy = (s.bbox[1] + s.bbox[3]) / 2
                print(f"    '{s.text}' at ({sx:.1f}, {sy:.1f}), dist={dist**0.5:.1f}")

    # Priority: test PU first if available
    pu_code_anchors = [s for s in code_anchors if s.text == "PU"]
    if pu_code_anchors:
        code_span = pu_code_anchors[0]
        print(f"\n>>> Testing PU CODE anchor <<<")
    elif code_anchors:
        code_span = code_anchors[0]
        print(f"\nAnalyzing CODE anchor: '{code_span.text}'")
    else:
        code_span = None

    if code_span:
        print(f"Code: '{code_span.text}'")
        print(f"  Bbox: {code_span.bbox}")
        print(f"  Font size: {code_span.font_size}")

        code_x = (code_span.bbox[0] + code_span.bbox[2]) / 2
        code_y = (code_span.bbox[1] + code_span.bbox[3]) / 2
        print(f"  Center: ({code_x:.1f}, {code_y:.1f})")

        # Find nearby AREA and NUM spans
        print("\nNearby AREA candidates:")

        # Check if nearby 04s are in valid_spans
        nearby_04s = [s for s in valid_spans if s.text == "04"]
        print(f"  Total '04' in valid_spans: {len(nearby_04s)}")

        # Check area_regex
        area_regex_matches = [
            s for s in nearby_04s if extractor.area_regex.match(s.text)
        ]
        print(f"  '04' matching area_regex: {len(area_regex_matches)}")

        area_candidates = [
            s
            for s in valid_spans
            if s.span_id != code_span.span_id and extractor.area_regex.match(s.text)
        ]
        for i, area in enumerate(area_candidates[:5], 1):
            area_x = (area.bbox[0] + area.bbox[2]) / 2
            area_y = (area.bbox[1] + area.bbox[3]) / 2
            dist = ((area_x - code_x) ** 2 + (area_y - code_y) ** 2) ** 0.5
            print(
                f"  {i}. '{area.text}' at ({area_x:.1f}, {area_y:.1f}), dist={dist:.1f}"
            )

            # Try scoring
            score = extractor._score_alignment(
                code_span, area, "near", code_span.font_size
            )
            print(f"     Alignment score: {score:.3f}")

        print("\nNearby NUM candidates:")
        num_candidates = [
            s
            for s in valid_spans
            if s.span_id != code_span.span_id and extractor.num_regex.match(s.text)
        ]

        # Check if 2049 is in the list
        num_2049_in_list = [s for s in num_candidates if "2049" in s.text]
        if num_2049_in_list:
            print(f"  *** Found {len(num_2049_in_list)} '2049' NUM candidate(s) ***")
        else:
            print(f"  !!! '2049' NOT in NUM candidates list !!!")

        # Sort by distance to PU
        num_with_dist = []
        for num in num_candidates:
            num_x = (num.bbox[0] + num.bbox[2]) / 2
            num_y = (num.bbox[1] + num.bbox[3]) / 2
            dist = ((num_x - code_x) ** 2 + (num_y - code_y) ** 2) ** 0.5
            num_with_dist.append((num, dist, num_x, num_y))

        num_with_dist.sort(key=lambda x: x[1])

        for i, (num, dist, num_x, num_y) in enumerate(num_with_dist[:10], 1):
            print(f"  {i}. '{num.text}' at ({num_x:.1f}, {num_y:.1f}), dist={dist:.1f}")

            # Try scoring
            score = extractor._score_alignment(
                code_span, num, "near", code_span.font_size
            )
            print(f"     Alignment score: {score:.3f}")

        # Try assembly
        print("\nAttempting triplet assembly...")
        triplet = extractor._assemble_triplet(code_span, valid_spans, layout)

        if triplet:
            print(f"[SUCCESS] Triplet score: {triplet['score']:.2f}")
            print(
                f"  AREA: {triplet['area_span'].text if triplet['area_span'] else 'None'}"
            )
            print(f"  CODE: {triplet['code_span'].text}")
            print(f"  NUM: {triplet['num_span'].text}")
        else:
            print("[FAILED] Assembly failed - no valid triplet found")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
