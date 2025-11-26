"""
🔬 EXECUTION PROOF: Page-Aware Chunking Fix Verification
=========================================================

This script proves that the index mapping fix works correctly by:
1. Simulating exact data flow from tools/ingest.py
2. Testing chunk assignment for content in the MIDDLE of Page 2
3. Asserting page metadata is correct (not page 1 or 3)

Test Case:
- 3-page document (Page 1, 2, 3)
- Page 2 has 1000 chars of content
- Chunk size = 100 chars
- Target: Chunk containing char 500 of Page 2 must show page=2
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker


def create_test_pages():
    """Create test pages simulating real PDF structure"""
    # Page 1: Short intro (50 chars)
    page1_text = "Introduction section with some basic content."

    # Page 2: Long content (1000 chars)
    # Generate content so char 500 is clearly in Page 2
    page2_text = "Content from page 2. " * 48  # ~1008 chars

    # Page 3: Short conclusion (50 chars)
    page3_text = "Conclusion section with final summary notes."

    return [
        (1, page1_text),
        (2, page2_text),
        (3, page3_text),
    ]


def main():
    print("\n" + "=" * 70)
    print("🔬 EXECUTION PROOF: Page-Aware Chunking Fix")
    print("=" * 70)

    # Step 1: Create chunker with same config as ingest.py
    print("\n📋 Step 1: Initialize chunker (matching ingest.py config)")
    chunker = HierarchicalChunker(
        max_chunk_size=100,  # Small size to force multiple chunks
        chunk_overlap=20,
        use_token_count=False,  # Char count for consistency
        chunking_strategy="small-to-big",  # Same as ingest.py default
    )
    print("✅ Chunker initialized: max_chunk_size=100, strategy=small-to-big")

    # Step 2: Create test pages
    print("\n📋 Step 2: Create test pages")
    pages = create_test_pages()

    for page_num, text in pages:
        print(f"  Page {page_num}: {len(text)} chars - '{text[:40]}...'")

    print(f"\n📊 Total pages: {len(pages)}")
    print(f"📊 Page 2 length: {len(pages[1][1])} chars")

    # Step 3: Call chunk_markdown_with_pages (same as ingest.py line 1439)
    print("\n📋 Step 3: Call chunk_markdown_with_pages() [SAME AS INGEST.PY]")
    print("  >>> chunks = chunker.chunk_markdown_with_pages(pages, 'test_doc')")

    chunks = chunker.chunk_markdown_with_pages(
        pages=pages, doc_id="test_doc", metadata={"test": "execution_proof"}
    )

    print(f"✅ Created {len(chunks)} chunks")

    # Step 4: Verify Page 2 chunks have correct page metadata
    print("\n📋 Step 4: Verify Page 2 content chunks show page=2")

    # Find chunks that contain Page 2 content (not just the marker)
    page2_content_start = "Content from page 2."
    page2_chunks = []

    for chunk in chunks:
        if page2_content_start in chunk.text:
            page2_chunks.append(chunk)
            print(f"  Found Page 2 chunk: {chunk.chunk_id}, page={chunk.page_start}")

    print(f"\n  Total chunks with Page 2 content: {len(page2_chunks)}")

    # Pick a chunk from middle of list (most likely to be mid-page)
    if page2_chunks:
        target_chunk = page2_chunks[len(page2_chunks) // 2]
        print(
            f"\n🎯 Selected target chunk (middle of Page 2 chunks): {target_chunk.chunk_id}"
        )
        print(f"   Text preview: '{target_chunk.text[:80]}...'")
    else:
        target_chunk = None
        print("\n⚠️  No Page 2 chunks found!")

    # Step 5: CRITICAL ASSERTION
    print("\n📋 Step 5: CRITICAL ASSERTION - Page Metadata Check")
    print("=" * 70)

    if target_chunk is None:
        print("❌ FAIL: Could not find Page 2 chunks")
        return False

    # THE CRITICAL CHECK
    assigned_page = target_chunk.page_start
    expected_page = 2

    print(f"\n🔍 Checking Page 2 content chunk: {target_chunk.chunk_id}")
    print(f"   Expected page: {expected_page}")
    print(f"   Assigned page: {assigned_page}")

    # Also check if ALL Page 2 chunks have correct page
    all_correct = all(c.page_start == 2 for c in page2_chunks)

    if assigned_page == expected_page and all_correct:
        print("\n✅ ✅ ✅ SUCCESS! Page metadata is CORRECT! ✅ ✅ ✅")
        print(f"   All {len(page2_chunks)} chunks from Page 2 correctly show page=2")
        print("\n🎉 INDEX MAPPING FIX IS WORKING!")
        success = True
    else:
        print(f"\n❌ ❌ ❌ FAILURE! Page metadata is WRONG! ❌ ❌ ❌")
        if not all_correct:
            wrong_pages = [
                f"{c.chunk_id}=page{c.page_start}"
                for c in page2_chunks
                if c.page_start != 2
            ]
            print(f"   Wrong pages: {wrong_pages}")
        print("\n⚠️  INDEX MAPPING FIX IS NOT WORKING!")
        success = False

    # Step 6: Additional verification - show all chunks
    print("\n📋 Step 6: Full chunk breakdown for transparency")
    print("=" * 70)

    for i, chunk in enumerate(chunks):
        is_target = "🎯 TARGET" if chunk == target_chunk else ""
        is_page2 = "📝 PAGE2" if chunk in page2_chunks else ""
        print(f"\nChunk {i}: {chunk.chunk_id} {is_target} {is_page2}")
        print(f"  Page: {chunk.page_start}")
        print(f"  Length: {len(chunk.text)} chars")
        print(f"  Text: '{chunk.text[:80]}...'")

    print("\n" + "=" * 70)
    if success:
        print("✅ EXECUTION PROOF COMPLETE - FIX IS WORKING")
    else:
        print("❌ EXECUTION PROOF FAILED - FIX HAS ISSUES")
    print("=" * 70 + "\n")

    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXECUTION PROOF CRASHED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
