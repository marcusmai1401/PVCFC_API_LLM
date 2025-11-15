import json
from pathlib import Path

print("=" * 80)
print("KIỂM TRA KẾT QUẢ INGESTION PRODUCTION")
print("=" * 80)

# Check chunks
chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")
if chunks_file.exists():
    chunks = [json.loads(line) for line in open(chunks_file, encoding="utf-8")]
    single = sum(1 for c in chunks if c.get("page_start") == c.get("page_end"))
    multi = len(chunks) - single

    print(f"\n✅ chunks.jsonl: {len(chunks)} chunks")
    print(f"   - Single-page: {single} ({single/len(chunks)*100:.1f}%)")
    print(f"   - Multi-page: {multi} ({multi/len(chunks)*100:.1f}%)")

    # Check page_numbers field
    with_page_nums = sum(1 for c in chunks if c.get("page_numbers"))
    print(f"   - Có page_numbers field: {with_page_nums}")

    # Sample chunks
    print("\n   📄 Sample chunks:")
    for c in chunks[:3]:
        doc_id = c.get("document_id", "N/A")[:40]
        pages = f"{c.get('page_start')}-{c.get('page_end')}"
        page_nums = c.get("page_numbers", [])
        char_count = c.get("char_count", 0)
        print(
            f"      {doc_id} | pages:{pages} | page_nums:{page_nums} | chars:{char_count}"
        )
else:
    print("\n❌ chunks.jsonl không tồn tại!")

# Check tags
tags_file = Path("artifacts/ingestion_production/entities/tags.jsonl")
if tags_file.exists():
    tags = [json.loads(line) for line in open(tags_file, encoding="utf-8")]
    print(f"\n✅ tags.jsonl: {len(tags)} tags")

    # Sample tags
    print("\n   🏷️  Sample tags:")
    for tag in tags[:5]:
        tag_id = tag.get("tag_id", "N/A")
        doc_id = tag.get("document_id", "N/A")[:30]
        print(f"      {tag_id} | doc: {doc_id}")
else:
    print("\n⚠️  tags.jsonl không tồn tại hoặc chưa tạo")

print("\n" + "=" * 80)
