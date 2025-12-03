"""
Deduplicate tags.jsonl using composite key (doc_id, page, tag)
"""
import json
from collections import OrderedDict
from pathlib import Path


def dedupe_tags():
    # Read all tags, using composite key
    tags = OrderedDict()
    tags_file = Path("artifacts/ingestion_production/entities/tags.jsonl")

    if not tags_file.exists():
        print(f"❌ Error: {tags_file} does not exist")
        return

    print(f"📖 Reading {tags_file}...")
    with open(tags_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                tag = json.loads(line)
                # Use composite key to identify unique tags
                key = (tag["doc_id"], tag["page"], tag["tag"])
                tags[key] = tag  # Overwrites duplicates, keeps last
            except Exception as e:
                print(f"⚠️  Warning: Failed to parse line: {e}")
                continue

    # Write deduplicated tags
    output_file = tags_file.with_suffix(".clean.jsonl")
    print(f"✍️  Writing to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for tag in tags.values():
            f.write(json.dumps(tag, ensure_ascii=False) + "\n")

    # Stats
    original_count = sum(1 for _ in open(tags_file, encoding="utf-8"))
    deduplicated_count = len(tags)
    removed_count = original_count - deduplicated_count

    print(f"\n📊 Results:")
    print(f"  Original: {original_count:,} tags")
    print(f"  Deduplicated: {deduplicated_count:,} tags")
    print(
        f"  Removed: {removed_count:,} duplicates ({removed_count/original_count*100:.1f}%)"
    )

    # Verify
    print(f"\n🔍 Verifying clean file...")
    tag_keys = []
    for line in open(output_file, encoding="utf-8"):
        tag = json.loads(line)
        key = (tag["doc_id"], tag["page"], tag["tag"])
        tag_keys.append(key)

    unique_count = len(set(tag_keys))

    print(f"  Total in clean file: {len(tag_keys):,}")
    print(f"  Unique in clean file: {unique_count:,}")
    print(f"  Duplicates in clean file: {len(tag_keys) - unique_count}")

    if len(tag_keys) == unique_count:
        print(f"\n✅ SUCCESS: No duplicates in clean file!")
        print(f"\n💡 To apply changes, run:")
        print(f"   Move-Item '{output_file}' '{tags_file}' -Force")
    else:
        print(f"\n❌ ERROR: Still have duplicates in clean file!")


if __name__ == "__main__":
    dedupe_tags()
