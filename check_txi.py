from pathlib import Path

from app.ingestion.layout.page_layout_builder import PageLayoutBuilder
from app.ingestion.tags.tag_extractor import TagExtractor

builder = PageLayoutBuilder()
layout = builder.build_layout(
    Path("D:/Data_Raw/01. P&ID Ammonia Unit Rev12 (04000).pdf"), 17, "test"
)
extractor = TagExtractor()

txi_spans = [s for s in layout.spans if "TXI" in s.text.upper()]
print(f"TXI spans: {len(txi_spans)}")
for s in txi_spans:
    print(
        f"  Text: '{s.text}' | Stripped: '{s.text.strip()}' | In whitelist: {s.text.strip() in extractor.prefix_whitelist}"
    )

print(f"\nWhitelist sample: {list(extractor.prefix_whitelist)[:10]}")
print(f"'TXI' in whitelist: {'TXI' in extractor.prefix_whitelist}")
