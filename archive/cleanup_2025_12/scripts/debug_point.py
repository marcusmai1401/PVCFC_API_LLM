"""Debug script to find Point objects in layout"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment
load_dotenv(override=True)
os.environ["ENABLE_PID_TAGS"] = "true"

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder

# Sample PDF
pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
doc_id = "test_debug"

print("Building layout for page 1...")
builder = PageLayoutBuilder()
layout = builder.build_layout(pdf_path, 1, doc_id)

print(f"\nPage dimensions: {layout.page_width}, {layout.page_height}")
print(f"Type of page_width: {type(layout.page_width)}")
print(f"Type of page_height: {type(layout.page_height)}")

print(f"\nNumber of spans: {len(layout.spans)}")
if layout.spans:
    s = layout.spans[0]
    print(f"First span: text='{s.text}'")
    print(f"  bbox: {s.bbox}")
    print(f"  bbox type: {type(s.bbox)}")
    if s.bbox:
        for i, coord in enumerate(s.bbox):
            print(
                f"    bbox[{i}]: {coord}, type={type(coord)}, class={coord.__class__.__name__}"
            )

print(f"\nNumber of drawings: {len(layout.drawings)}")
if layout.drawings:
    d = layout.drawings[0]
    print(f"First drawing: type={d.type}")
    print(f"  coords: {d.coords[:4] if d.coords else []}")
    print(f"  color: {d.color}, type={type(d.color)}")
    if d.color:
        print(f"    color class: {d.color.__class__.__name__}")
        for i, c in enumerate(d.color):
            print(
                f"      color[{i}]: {c}, type={type(c)}, class={c.__class__.__name__}"
            )
