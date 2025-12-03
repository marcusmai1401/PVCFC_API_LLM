"""
Deduplicate chunks.jsonl by keeping the last occurrence of each chunk_id
"""
import json
from collections import OrderedDict
from pathlib import Path


def dedupe_chunks():
    # Read all chunks, keeping last occurrence
    chunks = OrderedDict()
    chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")

    if not chunks_file.exists():
        print(f"❌ Error: {chunks_file} does not exist")
        return

    print(f"📖 Reading {chunks_file}...")
    with open(chunks_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                chunk = json.loads(line)
                chunk_id = chunk["chunk_id"]
                chunks[chunk_id] = chunk  # Overwrites duplicates, keeps last
            except Exception as e:
                print(f"⚠️  Warning: Failed to parse line: {e}")
                continue

    # Write deduplicated chunks
    output_file = chunks_file.with_suffix(".clean.jsonl")
    print(f"✍️  Writing to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for chunk in chunks.values():
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Stats
    original_count = sum(1 for _ in open(chunks_file, encoding="utf-8"))
    deduplicated_count = len(chunks)
    removed_count = original_count - deduplicated_count

    print(f"\n📊 Results:")
    print(f"  Original: {original_count:,} chunks")
    print(f"  Deduplicated: {deduplicated_count:,} chunks")
    print(
        f"  Removed: {removed_count:,} duplicates ({removed_count/original_count*100:.1f}%)"
    )

    # Verify
    print(f"\n🔍 Verifying clean file...")
    chunk_ids_clean = [
        json.loads(line)["chunk_id"] for line in open(output_file, encoding="utf-8")
    ]
    unique_count = len(set(chunk_ids_clean))

    print(f"  Total in clean file: {len(chunk_ids_clean):,}")
    print(f"  Unique in clean file: {unique_count:,}")
    print(f"  Duplicates in clean file: {len(chunk_ids_clean) - unique_count}")

    if len(chunk_ids_clean) == unique_count:
        print(f"\n✅ SUCCESS: No duplicates in clean file!")
        print(f"\n💡 To apply changes, run:")
        print(f"   Move-Item '{output_file}' '{chunks_file}' -Force")
    else:
        print(f"\n❌ ERROR: Still have duplicates in clean file!")


if __name__ == "__main__":
    dedupe_chunks()
