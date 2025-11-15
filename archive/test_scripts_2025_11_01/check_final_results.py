"""
Final comprehensive check of ingestion results
"""
import json
from pathlib import Path

print("=" * 80)
print("FINAL INGESTION RESULTS CHECK")
print("=" * 80)

# 1. Check chunks
chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")
if chunks_file.exists():
    chunks = [json.loads(line) for line in open(chunks_file, encoding="utf-8")]
    single = sum(1 for c in chunks if c.get("page_start") == c.get("page_end"))

    print(f"\n✅ CHUNKS")
    print(f"   Total: {len(chunks)}")
    print(f"   Single-page: {single} ({single/len(chunks)*100:.1f}%)")
    print(
        f"   Multi-page: {len(chunks)-single} ({(len(chunks)-single)/len(chunks)*100:.1f}%)"
    )
else:
    print("\n❌ chunks.jsonl not found")

# 2. Check tags
tags_file = Path("artifacts/ingestion_production/entities/tags.jsonl")
if tags_file.exists():
    tags = [json.loads(line) for line in open(tags_file, encoding="utf-8")]
    print(f"\n✅ TAGS")
    print(f"   Total tags: {len(tags)}")

    # Count unique documents
    unique_docs = set(t.get("document_id") for t in tags)
    print(f"   From documents: {len(unique_docs)}")

    # Sample tags
    print(f"\n   Sample tags:")
    for tag in tags[:5]:
        tag_id = tag.get("tag_id", "N/A")
        doc_id = tag.get("document_id", "N/A")[:40]
        page = tag.get("page_number", "N/A")
        print(f"      {tag_id} | doc: {doc_id} | page: {page}")
else:
    print(f"\n❌ tags.jsonl not found at {tags_file}")

# 3. Check P&ID Ammonia specifically
ammonia_chunks = [
    c for c in chunks if "Ammonia" in c.get("metadata", {}).get("file_name", "")
]
if ammonia_chunks:
    print(f"\n✅ P&ID AMMONIA")
    print(f"   Total chunks: {len(ammonia_chunks)}")

    # Check if has tags
    with_tags = sum(1 for c in ammonia_chunks if c.get("metadata", {}).get("tags"))
    print(f"   Chunks with tags: {with_tags}")

    # Check OCR usage
    ocr_chunks = [c for c in ammonia_chunks if "[OCR Text]" in c.get("text", "")]
    print(f"   Chunks with OCR text: {len(ocr_chunks)}")

    if ocr_chunks:
        sample = ocr_chunks[0]
        ocr_start = sample["text"].find("[OCR Text]")
        if ocr_start > 0:
            print(f"   ✓ Force OCR working! (Combined vector + OCR)")
else:
    print("\n⚠️  P&ID Ammonia chunks not found")

# 4. Check Ammonia tags specifically
if tags_file.exists():
    ammonia_tags = [t for t in tags if "Ammonia" in t.get("document_id", "")]
    if ammonia_tags:
        print(f"\n✅ P&ID AMMONIA TAGS")
        print(f"   Extracted tags: {len(ammonia_tags)}")
        print(f"   Sample:")
        for tag in ammonia_tags[:3]:
            print(f'      {tag.get("tag_id")} on page {tag.get("page_number")}')
    else:
        print(f"\n⚠️  No tags extracted from P&ID Ammonia")

# 5. Check .env loading
print(f"\n✅ ENVIRONMENT CHECK")
import os

enable_pid = os.environ.get("ENABLE_PID_TAGS", "not_set")
print(f"   ENABLE_PID_TAGS: {enable_pid}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("✓ Chunk file created")
print(f'✓ Tags file: {"YES" if tags_file.exists() else "NO"}')
print(f'✓ P&ID Ammonia processed: {"YES" if ammonia_chunks else "NO"}')
print(f'✓ Force OCR on CAD files: {"YES" if ocr_chunks else "NO"}')
print("=" * 80)
