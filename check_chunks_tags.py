"""Quick check for tags in ingested chunks"""
import json
from pathlib import Path

chunks_file = Path("artifacts/ingestion_test/chunks/chunks.jsonl")
lines = chunks_file.read_text(encoding="utf-8").strip().split("\n")

print(f"✅ Total chunks: {len(lines)}\n")

# Find chunks containing "0256" or "TE"
found = []
for i, line in enumerate(lines, 1):
    chunk = json.loads(line)
    text = chunk.get("text", "").upper()
    tags = chunk.get("metadata", {}).get("tags", [])
    tags_str = " ".join(str(t).upper() for t in tags)

    if "0256" in text or "0256" in tags_str:
        found.append((i, chunk))

print(f"📌 Chunks containing '0256': {len(found)}\n")

# Show first 3 matches
for i, chunk in found[:5]:
    meta = chunk.get("metadata", {})
    print(f"Chunk {i}:")
    print(f"  📄 Page: {meta.get('page', 'N/A')}")
    print(f"  🏷️  Tags: {meta.get('tags', [])}")
    print(f"  📝 Text preview: {chunk.get('text', '')[:200]}...")
    print()

# Also check all tags across all chunks
all_tags = set()
for line in lines:
    chunk = json.loads(line)
    tags = chunk.get("metadata", {}).get("tags", [])
    all_tags.update(tags)

print(f"\n📊 All unique tags found ({len(all_tags)}):")
print(sorted(all_tags)[:20])  # Show first 20 tags
