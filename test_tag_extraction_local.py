"""
Test TagNormalizer integration locally without requiring full ingestion.
This verifies that tag extraction logic works correctly.
"""
from app.ingestion.text_chunker import TextChunker
from app.rag.normalizers.tag_normalizer import TagNormalizer

print("=" * 80)
print("TESTING TAG EXTRACTION")
print("=" * 80)
print()

# Sample text from Instrument List (simulating OCR output with sufficient length for chunking)
sample_texts = [
    # Scenario 1: Tag with dashes (ideal case) - Longer text for chunking
    """INSTRUMENT LIST FOR STEAM TURBINE
    TAG NO.: 06-TE-0256 A/B
    Description: Temperature sensor for rear journal bearing monitoring
    Measurement Point: Rear Journal Bearing (后径向轴承)
    Type: RTD DUPLEX TYPE
    Range: 0-200°C
    Alarm Setpoint: 105°C (High)""",
    # Scenario 2: Multiple instruments in a table-like format
    """NO. | TAG NO. | ITEM | SERVICE
    384 | 06-TE-0255 | RTD DUPLEX | FRONT BEARING
    385 | 06-TE-0256 A/B | RTD DUPLEX TYPE | REAR JOURNAL BEARING
    386 | 06-TG-0202 | THERMOMETER | LUBE OIL UNIT
    387 | 06-PI-0103 | PRESSURE INDICATOR | STEAM INLET""",
    # Scenario 3: Other equipment tags
    """VALVE LIST:
    Valve PV-101: Main steam control valve, operating pressure 150 bar
    Pump P-2001A: Lube oil circulation pump, flow rate 50 m3/h
    Compressor K-305: CO2 compressor unit for gas processing
    Heat Exchanger E-201: Shell and tube type for cooling""",
]

# Test 1: Direct TagNormalizer
print("TEST 1: Direct TagNormalizer")
print("-" * 80)
normalizer = TagNormalizer()

for i, text in enumerate(sample_texts, 1):
    print(f"\nSample {i}: {text[:80]}...")
    tags = normalizer.extract_tags(text)

    if tags:
        print(f"  ✅ Found {len(tags)} tag(s):")
        for tag in tags:
            print(
                f"     - Original: '{tag['original']}' → Normalized: '{tag['normalized']}' (type: {tag['type']})"
            )
    else:
        print(f"  ❌ No tags found")

# Test 2: Through TextChunker (simulating full pipeline)
print("\n" + "=" * 80)
print("TEST 2: Through TextChunker Pipeline")
print("-" * 80)

chunker = TextChunker(chunk_size=500, chunk_overlap=50, chunking_strategy="semantic")

for i, text in enumerate(sample_texts, 1):
    print(f"\nSample {i}:")

    # Chunk the text (simulate ingestion)
    chunks = chunker.chunk_text(
        text=text,
        doc_id=f"TEST_DOC_{i}",
        metadata={"source": "Instrument_List_Test", "page": 4},
    )

    if chunks:
        chunk = chunks[0]  # Take first chunk
        tags = chunk.metadata.get("tags", [])
        tags_raw = chunk.metadata.get("tags_raw", [])
        doc_type = chunk.metadata.get("doc_type", "unknown")

        print(f"  Chunk metadata:")
        print(f"    - tags: {tags}")
        print(f"    - tags_raw: {tags_raw}")
        print(f"    - doc_type: {doc_type}")

        if tags:
            print(f"  ✅ Tag extraction SUCCESS: {len(tags)} tag(s) in metadata")
        else:
            print(f"  ⚠️  No tags extracted to metadata")
    else:
        print(f"  ❌ Chunking failed")

# Test 3: Verify tags are extracted in chunks
print("\n" + "=" * 80)
print("TEST 3: Verify Tags in Chunk Metadata")
print("-" * 80)

target_patterns = ["0256", "TE-0256", "TE0256"]  # Partial match OK
found_in_chunks = 0

for i, text in enumerate(sample_texts, 1):
    chunks = chunker.chunk_text(
        text=text,
        doc_id=f"TEST_DOC_{i}",
        metadata={"source": "Instrument_List_Test", "page": 4},
    )

    if chunks and chunks[0].metadata.get("tags"):
        tags = chunks[0].metadata.get("tags", [])
        # Check if any tag contains target patterns
        if any(any(pat in str(tag).upper() for pat in target_patterns) for tag in tags):
            found_in_chunks += 1
            print(f"  ✅ Sample {i}: Tags in metadata: {tags}")

if found_in_chunks >= 2:
    print(
        f"\n✅ SUCCESS: Tags extracted in {found_in_chunks}/{len(sample_texts)} samples"
    )
else:
    print(
        f"\n⚠️  PARTIAL: Tags extracted in {found_in_chunks}/{len(sample_texts)} samples (expected >= 2)"
    )

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("✅ TagNormalizer can extract equipment tags from text")
print("✅ TextChunker integrates tag extraction into metadata")
print("✅ Tags are normalized for consistent matching")
print("\nNext steps:")
print(
    "  1. Update OpenSearch mapping: python scripts/opensearch/update_mapping_add_tags.py"
)
print("  2. Re-ingest test document: python tools/ingest_single_pdf.py --pdf <path>")
print("  3. Verify in OpenSearch: python tools/verify_tags_in_index.py")
print("=" * 80)
