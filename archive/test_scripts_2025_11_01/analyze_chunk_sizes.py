import json
import statistics
from pathlib import Path

chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")
chunks = [json.loads(line) for line in open(chunks_file, encoding="utf-8")]

sizes = [c["char_count"] for c in chunks]

print("=" * 80)
print("PHÂN TÍCH CHUNK SIZE DISTRIBUTION")
print("=" * 80)

# Target range analysis
TARGET_MIN = 800
TARGET_MAX = 1500
in_range = sum(1 for s in sizes if TARGET_MIN <= s <= TARGET_MAX)
too_small = sum(1 for s in sizes if s < TARGET_MIN)
too_large = sum(1 for s in sizes if s > TARGET_MAX)

print(f"\nTarget range: {TARGET_MIN}-{TARGET_MAX} chars")
print(f"Total chunks: {len(chunks)}")
print(f"\n📊 Distribution:")
print(
    f"  ✓ In range ({TARGET_MIN}-{TARGET_MAX}):  {in_range:4d} ({in_range/len(chunks)*100:5.1f}%)"
)
print(
    f"  ⚠ Too small (<{TARGET_MIN}):       {too_small:4d} ({too_small/len(chunks)*100:5.1f}%)"
)
print(
    f"  ⚠ Too large (>{TARGET_MAX}):      {too_large:4d} ({too_large/len(chunks)*100:5.1f}%)"
)

print(f"\n📈 Statistics:")
print(f"  Mean:   {statistics.mean(sizes):,.0f} chars")
print(f"  Median: {statistics.median(sizes):,.0f} chars")
print(f"  Min:    {min(sizes):,} chars")
print(f"  Max:    {max(sizes):,} chars")
print(f"  StdDev: {statistics.stdev(sizes):,.0f} chars")

# Percentiles
sorted_sizes = sorted(sizes)
p10 = sorted_sizes[int(len(sorted_sizes) * 0.1)]
p25 = sorted_sizes[int(len(sorted_sizes) * 0.25)]
p75 = sorted_sizes[int(len(sorted_sizes) * 0.75)]
p90 = sorted_sizes[int(len(sorted_sizes) * 0.90)]

print(f"\n📊 Percentiles:")
print(f"  10th: {p10:,} chars")
print(f"  25th: {p25:,} chars")
print(f"  75th: {p75:,} chars")
print(f"  90th: {p90:,} chars")

# Sample of outliers
print(f"\n🔍 Sample too small chunks (<{TARGET_MIN}):")
small_chunks = [c for c in chunks if c["char_count"] < TARGET_MIN][:5]
for c in small_chunks:
    print(
        f'  {c["char_count"]:4d} chars | page {c["page_start"]} | {c["chunk_id"][:50]}'
    )

print(f"\n🔍 Sample too large chunks (>{TARGET_MAX}):")
large_chunks = [c for c in chunks if c["char_count"] > TARGET_MAX][:5]
for c in large_chunks:
    print(
        f'  {c["char_count"]:5d} chars | page {c["page_start"]} | {c["chunk_id"][:50]}'
    )

print("\n" + "=" * 80)
print("ĐÁNH GIÁ VÀ KHUYẾN NGHỊ")
print("=" * 80)

# Analysis
if in_range / len(chunks) > 0.6:
    print(
        "✅ Phần lớn chunks (~{:.0f}%) nằm trong target range".format(
            in_range / len(chunks) * 100
        )
    )
    print("   → KHÔNG CẦN FIX nếu RAG hoạt động tốt")
else:
    print(
        "⚠️  Chỉ {:.0f}% chunks trong target range".format(in_range / len(chunks) * 100)
    )
    print("   → CÓ THỂ CẦN điều chỉnh chunking strategy")

print("\n💡 Lý do chunk size không đồng đều:")
print("  1. PDF có cấu trúc khác nhau (technical docs, drawings, tables)")
print("  2. Page-aware chunking ưu tiên page boundaries > target size")
print("  3. Một số pages có ít text (drawings, diagrams)")
print("  4. Tables và structured content tạo chunks lớn/nhỏ bất thường")

print("\n🤔 CẦN FIX HAY KHÔNG?")
if too_small / len(chunks) > 0.3:
    print("  ⚠️  CÓ - Quá nhiều chunks nhỏ có thể làm giảm context quality")
    print("      → Xem xét merge small chunks với neighbors")
else:
    print("  ✅ KHÔNG CẦN - Chunk size variation là tự nhiên với heterogeneous PDFs")
    print("      → Chỉ fix nếu RAG performance không đạt yêu cầu")

print("=" * 80)
