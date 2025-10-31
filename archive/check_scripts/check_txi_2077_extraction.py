"""
Check if tag extractor can find 04 TXI 2077 from separate text spans
"""
import sys

sys.path.insert(0, "C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC")

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"
page_num = 17

print("=" * 80)
print("Extracting tags from page 17 looking for TXI 2077")
print("=" * 80)

# Build layout
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, page_num, "Ammonia")

print(f"\nTotal spans: {len(layout.spans)}")

# Find relevant spans
txi_span = None
span_2077 = None
span_04 = None

for span in layout.spans:
    if span.text == "TXI":
        txi_span = span
    if span.text == "2077":
        span_2077 = span
    if span.text == "04":
        span_04 = span

print("\nLooking for component spans:")
print(f"  '04' spans found: {sum(1 for s in layout.spans if s.text == '04')}")
print(f"  'TXI' spans found: {sum(1 for s in layout.spans if s.text == 'TXI')}")
print(f"  '2077' spans found: {sum(1 for s in layout.spans if s.text == '2077')}")

# Find TXI followed by 2077
print("\nSearching for TXI → 2077 pattern:")
for i, span in enumerate(layout.spans):
    if span.text == "TXI":
        # Check next few spans
        window = layout.spans[max(0, i - 3) : min(len(layout.spans), i + 4)]
        window_text = [s.text for s in window]
        print(f"\n  Found 'TXI' at span {i}, window: {window_text}")
        print(f"    TXI bbox: {span.bbox}")

        # Check if 2077 is nearby
        has_2077 = any(s.text == "2077" for s in window)
        has_04 = any(s.text == "04" for s in window)

        if has_2077 and has_04:
            print(f"    ★★★ COMPLETE MATCH: 04 + TXI + 2077 in proximity!")
            # Show all bboxes
            for j, s in enumerate(window):
                print(f"      [{j}] '{s.text}' bbox: {s.bbox}")

# Now run extractor
print("\n" + "=" * 80)
print("Running tag extractor...")
print("=" * 80)

extractor = TagExtractor()
tags = extractor.extract_tags(layout)

print(f"\nExtracted {len(tags)} total tags")

# Search for TXI 2077
found_txi_2077 = False
for tag in tags:
    tag_text = f"{tag.parts.unit} {tag.parts.prefix} {tag.parts.suffix}".strip()
    if "TXI" in tag_text and "2077" in tag_text:
        print(f"\n✓ FOUND: {tag_text}")
        print(f"  Confidence: {tag.confidence:.2f}")
        print(f"  BBox: {tag.bbox}")
        found_txi_2077 = True

if not found_txi_2077:
    print("\n✗ Tag '04 TXI 2077' NOT extracted")
    print("\nPossible reasons:")
    print("  1. Spatial distance between 04/TXI/2077 exceeds tolerance")
    print("  2. Tag grammar confidence threshold too high")
    print("  3. Vertical layout (stacked text) not handled")

    # Check config
    from pathlib import Path

    import yaml

    config_path = Path(
        "C:/Users/Admin/Desktop/Code - API_LLM_PVCFC/app/ingestion/tags/config/tag_grammar.yaml"
    )
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        print(f"\n  Current config:")
        print(f"    spatial_tolerance_mm: {cfg.get('spatial_tolerance_mm')}")
        print(f"    min_pass_threshold: {cfg.get('min_pass_threshold')}")
