#!/usr/bin/env python
"""
Deduplicate tags.jsonl by keeping last occurrence of each unique tag
Key: (doc_id, page, tag, unit, prefix, suffix)
"""
import json
from pathlib import Path


def deduplicate_tags(input_file: Path, output_file: Path):
    """Deduplicate tags by keeping last occurrence"""

    # Read all tags and track by unique key
    tags_dict = {}
    total = 0

    print(f"Reading tags from {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            tag_obj = json.loads(line)

            # Unique key: doc_id, page, tag string, and parts
            parts = tag_obj.get("parts", {})
            key = (
                tag_obj.get("doc_id"),
                tag_obj.get("page"),
                tag_obj.get("tag"),
                parts.get("unit"),
                parts.get("prefix"),
                parts.get("suffix"),
            )

            # Keep last occurrence (overwrite)
            tags_dict[key] = tag_obj

    unique_count = len(tags_dict)
    duplicates = total - unique_count

    print(f"Total tags read: {total}")
    print(f"Unique tags: {unique_count}")
    print(f"Duplicates removed: {duplicates} ({duplicates/total*100:.1f}%)")

    # Write deduplicated tags
    print(f"Writing deduplicated tags to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for tag_obj in tags_dict.values():
            f.write(json.dumps(tag_obj, ensure_ascii=False) + "\n")

    print(f"✅ Deduplication complete: {unique_count} unique tags written")
    return unique_count, duplicates


if __name__ == "__main__":
    tags_file = Path("artifacts/ingestion_production/entities/tags.jsonl")
    output_file = Path("artifacts/ingestion_production/entities/tags_deduped.jsonl")

    if not tags_file.exists():
        print(f"❌ File not found: {tags_file}")
        exit(1)

    deduplicate_tags(tags_file, output_file)
