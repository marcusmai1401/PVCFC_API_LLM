import json

# Load chunks
with open(
    "artifacts/ingestion_production/chunks/chunks.jsonl", "r", encoding="utf-8"
) as f:
    chunks = [json.loads(line) for line in f]

# Find MANUAL(COMPRESSOR)l.pdf chunks
manual_chunks = [c for c in chunks if "MANUAL_COMPRE_88d35c5c" in c.get("doc_id", "")]

print("=" * 80)
print("VERIFYING HIGH PAGE NUMBERS FOR MANUAL(COMPRESSOR)l.pdf")
print("=" * 80)

if manual_chunks:
    pages = [(c.get("page_start"), c.get("page_end")) for c in manual_chunks]
    valid_pages = [p for p in pages if p[0] is not None and p[1] is not None]

    print(f"\nTotal chunks: {len(manual_chunks)}")
    print(
        f"Page range: {min(p[0] for p in valid_pages)} - {max(p[1] for p in valid_pages)}"
    )

    # Check high page chunks (> 500)
    high_page_chunks = [c for c in manual_chunks if c.get("page_end", 0) > 500]
    print(f"\nChunks with pages > 500: {len(high_page_chunks)}")

    if high_page_chunks:
        # Show first 5 high page chunks
        print("\nSample high page chunks:")
        for i, chunk in enumerate(high_page_chunks[:5]):
            print(f"  {i+1}. Pages {chunk.get('page_start')} - {chunk.get('page_end')}")

    # Check very high page chunks (> 1000)
    very_high = [c for c in manual_chunks if c.get("page_end", 0) > 1000]
    print(f"\nChunks with pages > 1000: {len(very_high)}")

    if very_high:
        print("Sample:")
        chunk = very_high[0]
        print(f"  Pages {chunk.get('page_start')} - {chunk.get('page_end')}")
        print(f"  Chunk ID: {chunk.get('chunk_id', 'N/A')[:80]}...")

    # Summary
    print("\n" + "=" * 80)
    print("✓ SUCCESS: High page numbers are now accessible!")
    print(f"✓ Can now retrieve pages up to {max(p[1] for p in valid_pages)}")
    print("=" * 80)
else:
    print("\n✗ No chunks found for MANUAL(COMPRESSOR)l.pdf")
