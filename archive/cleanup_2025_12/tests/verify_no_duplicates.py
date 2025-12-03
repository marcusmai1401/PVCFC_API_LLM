"""
Verify no duplicates exist in chunks.jsonl and tags.jsonl
"""
import json
import sys
from pathlib import Path


def check_duplicates(file_path, id_field="chunk_id", composite_key=None):
    """
    Check for duplicates in JSONL file

    Args:
        file_path: Path to JSONL file
        id_field: Field name to use as unique key (if composite_key is None)
        composite_key: Function to extract composite key from object

    Returns:
        bool: True if no duplicates, False otherwise
    """
    if not file_path.exists():
        print(f"⚠️  Warning: {file_path} does not exist")
        return True  # No file means no duplicates

    ids = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if composite_key:
                    key = composite_key(obj)
                else:
                    key = obj[id_field]
                ids.append(key)
            except Exception as e:
                print(f"⚠️  Warning: Failed to parse line in {file_path.name}: {e}")
                continue

    total = len(ids)
    unique = len(set(ids))
    duplicates = total - unique
    dup_rate = (duplicates / total * 100) if total > 0 else 0

    print(f"\n{file_path.name}:")
    print(f"  Total: {total:,}")
    print(f"  Unique: {unique:,}")
    print(f"  Duplicates: {duplicates:,}")
    print(f"  Duplicate rate: {dup_rate:.1f}%")

    return dup_rate == 0


def main(output_dir="artifacts/test_ingestion"):
    """Main verification function"""
    output_path = Path(output_dir)

    print("=" * 60)
    print("DUPLICATE VERIFICATION")
    print("=" * 60)
    print(f"\nChecking: {output_path}")

    # Check chunks
    chunks_ok = check_duplicates(
        output_path / "chunks" / "chunks.jsonl", id_field="chunk_id"
    )

    # Check tags (using composite key)
    def tag_key(obj):
        return (obj["doc_id"], obj["page"], obj["tag"])

    tags_file = output_path / "entities" / "tags.jsonl"
    tags_ok = check_duplicates(tags_file, composite_key=tag_key)

    print("\n" + "=" * 60)
    if chunks_ok and tags_ok:
        print("✅ PASS: No duplicates found")
        print("=" * 60)
        return 0
    else:
        print("❌ FAIL: Duplicates detected")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    # Allow custom output directory from command line
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "artifacts/test_ingestion"
    sys.exit(main(output_dir))
