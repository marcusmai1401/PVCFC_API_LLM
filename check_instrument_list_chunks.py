"""
Check if Tag number 06-TE-0256 appears in indexed chunks from Instrument List
"""
import json
from pathlib import Path

# Load doc_id_map
doc_id_map_path = Path("artifacts/ingestion_production/doc_id_map.json")
with open(doc_id_map_path, encoding="utf-8") as f:
    doc_id_map = json.load(f)

# Find Instrument List doc_id
instrument_doc_id = None
for doc_id, info in doc_id_map.items():
    if "Instrument_116_3N4-S4275354" in doc_id:
        instrument_doc_id = doc_id
        print(f"Found Instrument List doc_id: {doc_id}")
        print(f"PDF path: {info.get('pdf_path') if isinstance(info, dict) else info}")
        break

if not instrument_doc_id:
    print("❌ Instrument List not found in doc_id_map!")
    exit(1)

print("\n" + "=" * 80)
print("CHECKING INDEXED CHUNKS")
print("=" * 80)

# Try to find chunks in ingestion metadata
chunks_metadata_path = Path("artifacts/ingestion_production/metadata.json")
if chunks_metadata_path.exists():
    with open(chunks_metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)

    # Look for chunks from Instrument List
    instrument_chunks = [
        chunk
        for chunk in metadata.get("chunks", [])
        if chunk.get("doc_id") == instrument_doc_id
    ]

    print(f"\nFound {len(instrument_chunks)} chunks for Instrument List")

    # Check if Tag number appears in any chunk
    tag_patterns = ["06-TE-0256", "06 TE 0256", "06TE0256", "0256A/B", "0256 A/B"]

    found_tag = False
    for i, chunk in enumerate(instrument_chunks, 1):
        text = chunk.get("text", "")
        page = chunk.get("page", "?")

        for pattern in tag_patterns:
            if pattern in text.upper().replace("-", " ").replace("_", " "):
                found_tag = True
                print(f"\n✅ FOUND Tag pattern '{pattern}' in chunk #{i} (page {page})")
                print(f"   Text preview: {text[:300]}...")
                break

        # Also check for pages 4-6
        if page in [4, 5, 6]:
            print(f"\n📄 Chunk #{i} from page {page}:")
            print(f"   Length: {len(text)} chars")
            print(f"   Preview: {text[:200]}...")

    if not found_tag:
        print("\n❌ Tag number '06-TE-0256' NOT FOUND in any chunk!")
        print("\nPossible issues:")
        print("  1. OCR failed on pages 4-6")
        print("  2. Table structure confused OCR (vertical text, merged cells)")
        print("  3. Chunks were split in a way that broke the Tag number")
        print("  4. Pages 4-6 were not processed during ingestion")
else:
    print(f"❌ Metadata file not found at {chunks_metadata_path}")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("\nTo fix this issue:")
print("  1. Re-run ingestion with better OCR settings")
print("  2. Use table-aware OCR (like Azure Document Intelligence)")
print("  3. Pre-process PDF to flatten tables before OCR")
print("  4. Add Tag number normalization (06-TE-0256 → 06 TE 0256)")
print("  5. Or manually add Tag numbers to chunk metadata during ingestion")
print("=" * 80)
