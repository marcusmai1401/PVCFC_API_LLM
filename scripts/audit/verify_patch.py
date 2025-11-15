"""Quick verification script to check patched chunks"""
import json
import random

chunks_file = "artifacts/ingestion/chunks/chunks.jsonl"

print("=" * 70)
print("VERIFYING PATCHED CHUNKS.JSONL")
print("=" * 70)

# Load all chunks
with open(chunks_file, "r", encoding="utf-8") as f:
    all_chunks = [json.loads(line) for line in f]

total = len(all_chunks)
print(f"\nTotal chunks: {total:,}")

# Check first 10
print("\n" + "=" * 70)
print("FIRST 10 CHUNKS")
print("=" * 70)
for i, chunk in enumerate(all_chunks[:10], 1):
    page_start = chunk.get("page_start")
    metadata_page = chunk.get("metadata", {}).get("page")
    match = "✅" if page_start == metadata_page else "❌"
    print(f"\nChunk {i}:")
    print(f"  chunk_id: {chunk.get('chunk_id')}")
    print(f"  page_start: {page_start}")
    print(f"  metadata.page: {metadata_page}")
    print(f"  Match: {match}")

# Check random 20
print("\n" + "=" * 70)
print("RANDOM 20 CHUNKS")
print("=" * 70)
random_samples = random.sample(all_chunks, min(20, total))
for i, chunk in enumerate(random_samples, 1):
    page_start = chunk.get("page_start")
    metadata_page = chunk.get("metadata", {}).get("page")
    match = "✅" if page_start == metadata_page else "❌"
    print(f"\nChunk {i}:")
    print(f"  chunk_id: {chunk.get('chunk_id')}")
    print(f"  page_start: {page_start}")
    print(f"  metadata.page: {metadata_page}")
    print(f"  Match: {match}")

# Check last 10
print("\n" + "=" * 70)
print("LAST 10 CHUNKS")
print("=" * 70)
for i, chunk in enumerate(all_chunks[-10:], 1):
    page_start = chunk.get("page_start")
    metadata_page = chunk.get("metadata", {}).get("page")
    match = "✅" if page_start == metadata_page else "❌"
    print(f"\nChunk {i}:")
    print(f"  chunk_id: {chunk.get('chunk_id')}")
    print(f"  page_start: {page_start}")
    print(f"  metadata.page: {metadata_page}")
    print(f"  Match: {match}")

# Statistics
print("\n" + "=" * 70)
print("STATISTICS")
print("=" * 70)
missing_metadata_page = 0
mismatch = 0
for chunk in all_chunks:
    metadata = chunk.get("metadata", {})
    if "page" not in metadata or metadata["page"] is None:
        missing_metadata_page += 1
    elif chunk.get("page_start") != metadata["page"]:
        mismatch += 1

print(f"\nTotal chunks: {total:,}")
print(
    f"Missing metadata.page: {missing_metadata_page:,} ({100*missing_metadata_page/total:.2f}%)"
)
print(f"Page mismatch: {mismatch:,} ({100*mismatch/total:.2f}%)")
print(
    f"Valid chunks: {total - missing_metadata_page - mismatch:,} ({100*(total - missing_metadata_page - mismatch)/total:.2f}%)"
)

if missing_metadata_page == 0 and mismatch == 0:
    print("\n✅ ALL CHUNKS ARE VALID!")
else:
    print(f"\n❌ FOUND ISSUES!")
