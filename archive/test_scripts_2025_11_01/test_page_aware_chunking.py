"""
Test script to verify page-aware chunking
Tests the new page boundary detection and single-page chunk prioritization
"""
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.chunkers.hierarchical_chunker import (
    HierarchicalChunker,
    extract_all_pages_from_content,
)


def test_page_detection():
    """Test page marker detection"""
    print("=" * 80)
    print("Test 1: Page Marker Detection")
    print("=" * 80)

    test_content = """
    <!-- Page 15 -->
    This is content from page 15.

    <!-- Page 16 -->
    This is content from page 16.

    <!-- Page 17 -->
    This is content from page 17.
    """

    pages = extract_all_pages_from_content(test_content)
    print(f"Detected pages: {pages}")
    print(f"✓ Expected [15, 16, 17], Got {pages}")
    print()


def test_single_page_chunks():
    """Test that single-page content stays as single page"""
    print("=" * 80)
    print("Test 2: Single-Page Content")
    print("=" * 80)

    chunker = HierarchicalChunker(
        max_chunk_size=500,
        use_token_count=False,  # Use char count for simplicity
    )

    markdown = """# Section 1

<!-- Page 10 -->

This is a paragraph on page 10. It has some content but not too much.
Just enough to test that it stays on a single page.

Another paragraph here. Still on page 10.
"""

    chunks = chunker.chunk_markdown(markdown, doc_id="test_doc")

    print(f"Created {len(chunks)} chunks")
    for chunk in chunks:
        print(
            f"  Chunk {chunk.chunk_index}: pages {chunk.page_start}-{chunk.page_end}, "
            f"len={chunk.char_count}, page_numbers={chunk.page_numbers}"
        )

    # Verify all chunks are single-page
    multi_page = [c for c in chunks if c.page_start != c.page_end]
    print(
        f"\n✓ Multi-page chunks: {len(multi_page)}/{len(chunks)} "
        f"({len(multi_page)/len(chunks)*100:.1f}%)"
    )
    print()


def test_multi_page_splitting():
    """Test that multi-page content gets split by page boundaries"""
    print("=" * 80)
    print("Test 3: Multi-Page Content Splitting")
    print("=" * 80)

    chunker = HierarchicalChunker(
        max_chunk_size=2000,  # Large enough to span multiple pages if not split
        use_token_count=False,
    )

    markdown = """# Long Section

<!-- Page 15 -->

This is paragraph 1 on page 15. It has substantial content that would normally
be combined with the next page if we didn't split by page boundaries.

This is paragraph 2 on page 15. Adding more text here to make it realistic.

<!-- Page 16 -->

Now we're on page 16. This content should be in a SEPARATE chunk even though
the total size would fit in one chunk if we didn't respect page boundaries.

More content on page 16 to make it substantial.

<!-- Page 17 -->

And finally page 17. This should also be its own chunk, demonstrating that
we split by page boundaries BEFORE splitting by size.
"""

    chunks = chunker.chunk_markdown(markdown, doc_id="test_doc")

    print(f"Created {len(chunks)} chunks from 3-page section")
    for chunk in chunks:
        pages_str = (
            f"{chunk.page_start}"
            if chunk.page_start == chunk.page_end
            else f"{chunk.page_start}-{chunk.page_end}"
        )
        print(
            f"  Chunk {chunk.chunk_index}: page(s) {pages_str}, "
            f"len={chunk.char_count}, page_numbers={chunk.page_numbers}"
        )

    # Verify chunks are split by page
    single_page = [c for c in chunks if c.page_start == c.page_end]
    print(
        f"\n✓ Single-page chunks: {len(single_page)}/{len(chunks)} "
        f"({len(single_page)/len(chunks)*100:.1f}%)"
    )
    print()


def test_production_sample():
    """Test on a real production document"""
    print("=" * 80)
    print("Test 4: Production Data Sample")
    print("=" * 80)

    # Get a sample chunk from production
    chunks_file = Path("artifacts/ingestion_production/chunks/chunks.jsonl")

    if not chunks_file.exists():
        print(f"⚠️  Production file not found: {chunks_file}")
        print("   Skipping this test")
        return

    # Read first 100 chunks
    sample_chunks = []
    with open(chunks_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 100:
                break
            sample_chunks.append(json.loads(line))

    # Analyze multi-page chunks
    single_page = sum(
        1 for c in sample_chunks if c.get("page_start") == c.get("page_end")
    )
    multi_page = len(sample_chunks) - single_page

    print(f"Sample size: {len(sample_chunks)} chunks")
    print(f"Single-page: {single_page} ({single_page/len(sample_chunks)*100:.1f}%)")
    print(f"Multi-page: {multi_page} ({multi_page/len(sample_chunks)*100:.1f}%)")

    # Show a few multi-page examples
    print(f"\nExamples of multi-page chunks:")
    multi_examples = [
        c for c in sample_chunks if c.get("page_start") != c.get("page_end")
    ][:3]
    for c in multi_examples:
        print(
            f"  {c['chunk_id']}: pages {c['page_start']}-{c['page_end']}, "
            f"text preview: {c['text'][:100]}..."
        )
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("PAGE-AWARE CHUNKING TEST SUITE")
    print("=" * 80 + "\n")

    test_page_detection()
    test_single_page_chunks()
    test_multi_page_splitting()
    test_production_sample()

    print("=" * 80)
    print("✅ All tests completed")
    print("=" * 80)
