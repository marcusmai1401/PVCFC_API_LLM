"""
Debug alignment scoring step by step
"""
from pathlib import Path

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

pdf_path = Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf")
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, 17, "test")
extractor = TagExtractor()

valid_spans = extractor._filter_exclusion_zones(layout, layout.spans)

# Get TXI and closest 2077
txi = [s for s in valid_spans if s.text.strip() == "TXI"][0]
all_2077 = [s for s in valid_spans if s.text.strip() == "2077"]
# Sort by distance
txi_x = (txi.bbox[0] + txi.bbox[2]) / 2
txi_y = (txi.bbox[1] + txi.bbox[3]) / 2
all_2077_dist = [
    (
        s,
        (
            ((s.bbox[0] + s.bbox[2]) / 2 - txi_x) ** 2
            + ((s.bbox[1] + s.bbox[3]) / 2 - txi_y) ** 2
        )
        ** 0.5,
    )
    for s in all_2077
]
all_2077_dist.sort(key=lambda x: x[1])
suffix = all_2077_dist[0][0]

print(f"TXI: {txi.bbox}, rotation={txi.rotation_deg}, font={txi.font_size}")
print(f"2077: {suffix.bbox}, rotation={suffix.rotation_deg}, font={suffix.font_size}")
print(f"Distance: {all_2077_dist[0][1]:.2f}pt")

# Manual calculation
anchor_bbox = txi.bbox
cand_bbox = suffix.bbox

anchor_x_center = (anchor_bbox[0] + anchor_bbox[2]) / 2
cand_x_center = (cand_bbox[0] + cand_bbox[2]) / 2
anchor_y_center = (anchor_bbox[1] + anchor_bbox[3]) / 2
cand_y_center = (cand_bbox[1] + cand_bbox[3]) / 2

dx_raw = cand_x_center - anchor_x_center
dy_raw = cand_y_center - anchor_y_center

print(f"\nRaw deltas: dx={dx_raw:.2f}, dy={dy_raw:.2f}")

anchor_rot = txi.rotation_deg
delta_rot = (suffix.rotation_deg - anchor_rot) % 360
if delta_rot > 180:
    delta_rot -= 360

print(f"Anchor rotation: {anchor_rot}")
print(f"Delta rotation: {delta_rot}")

# Check vertical
rot_normalized = anchor_rot % 360
anchor_is_vertical = (75 <= rot_normalized <= 105) or (255 <= rot_normalized <= 285)
print(f"Anchor is vertical: {anchor_is_vertical}")
print(f"rot_normalized = {rot_normalized}")

if anchor_is_vertical or (75 <= abs(delta_rot) <= 105):
    x_delta = abs(dy_raw)
    y_delta = abs(dx_raw)
    print(f"SWAPPED axes: x_delta={x_delta:.2f}, y_delta={y_delta:.2f}")
else:
    x_delta = abs(dx_raw)
    y_delta = abs(dy_raw)
    print(f"Normal axes: x_delta={x_delta:.2f}, y_delta={y_delta:.2f}")

# X-tolerance check
anchor_width = anchor_bbox[2] - anchor_bbox[0]
cand_width = cand_bbox[2] - cand_bbox[0]
min_width = min(anchor_width, cand_width)
x_tolerance = extractor.x_tolerance_ratio * min_width

print(f"\nX-alignment check:")
print(f"  min_width={min_width:.2f}, x_tolerance={x_tolerance:.2f}")
print(f"  x_delta={x_delta:.2f}, PASS={x_delta <= x_tolerance}")

# Y-gap check
median_font = txi.font_size
y_min = extractor.y_gap_range[0] * median_font
y_max = extractor.y_gap_range[1] * median_font

print(f"\nY-gap check:")
print(f"  median_font={median_font:.2f}, y_min={y_min:.2f}, y_max={y_max:.2f}")
print(f"  y_delta={y_delta:.2f}, PASS={y_min <= y_delta <= y_max}")

# Font check
font_delta = abs(suffix.font_size - txi.font_size)
print(f"\nFont check:")
print(
    f"  font_delta={font_delta:.2f}, threshold={extractor.font_delta_pt}, PASS={font_delta <= extractor.font_delta_pt}"
)
