"""
Test to reproduce and analyze the infinite recursion bug in HierarchicalChunker._split_content

Bug Report: Process hangs with repeated log messages:
"Content spans 2 pages, splitting by page boundaries"
"""
import re
import sys
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC")

from app.rag.chunkers.hierarchical_chunker import (
    HierarchicalChunker,
    extract_all_pages_from_content,
    extract_page_from_content,
)


def test_extract_all_pages():
    """Test page extraction function behavior."""
    print("=" * 60)
    print("TEST 1: extract_all_pages_from_content behavior")
    print("=" * 60)

    # Test case 1: Single page marker
    text1 = "<!-- Page 5 -->\nSome content here"
    pages1 = extract_all_pages_from_content(text1)
    print(f"Input: {repr(text1[:50])}")
    print(f"Detected pages: {pages1}")
    print(f"len(pages) > 1: {len(pages1) > 1}")
    print()

    # Test case 2: Two page markers
    text2 = "<!-- Page 1 -->\nContent 1\n<!-- Page 2 -->\nContent 2"
    pages2 = extract_all_pages_from_content(text2)
    print(f"Input: {repr(text2[:50])}")
    print(f"Detected pages: {pages2}")
    print(f"len(pages) > 1: {len(pages2) > 1}")
    print()

    # Test case 3: Same page marker twice
    text3 = "<!-- Page 1 -->\nContent\n<!-- Page 1 -->\nMore content"
    pages3 = extract_all_pages_from_content(text3)
    print(f"Input: {repr(text3[:50])}")
    print(f"Detected pages: {pages3}")
    print(f"len(pages) > 1: {len(pages3) > 1}")
    print()


def simulate_split_logic(
    content: str, recursion_depth: int = 0
) -> List[Dict[str, Any]]:
    """
    Simulate the _split_content logic to trace the bug.
    Returns list of page contents that would be recursively processed.
    """
    MAX_DEPTH = 10  # Safety limit
    indent = "  " * recursion_depth

    print(
        f"{indent}[DEPTH={recursion_depth}] Processing content ({len(content)} chars)"
    )
    print(f"{indent}  Content preview: {repr(content[:100])}...")

    # Step 1: Detect pages (same as line 532)
    all_pages = extract_all_pages_from_content(content)
    print(f"{indent}  Detected pages: {all_pages}")

    if len(all_pages) > 1:
        print(f"{indent}  -> MULTI-PAGE BRANCH: Content spans {len(all_pages)} pages")

        if recursion_depth >= MAX_DEPTH:
            print(f"{indent}  !! RECURSION LIMIT HIT - BUG CONFIRMED !!")
            return []

        # Split by page markers (same as lines 541-542)
        page_pattern = re.compile(r"(<!--\s*Page\s+\d+\s*-->)")
        parts = page_pattern.split(content)

        print(f"{indent}  Split into {len(parts)} parts")

        # Group by page (same as lines 544-564)
        page_contents = {}
        current_page = 0  # Simulating page_start
        current_text = []

        for i, part in enumerate(parts):
            page_match = re.match(r"<!--\s*Page\s+(\d+)\s*-->", part)
            if page_match:
                if current_text:
                    page_contents[current_page] = "\n".join(current_text)
                current_page = int(page_match.group(1))
                current_text = [part]  # LINE 558 - THE BUG!
                print(
                    f"{indent}  Part {i}: PAGE MARKER (page {current_page}), keeping marker in content"
                )
            else:
                current_text.append(part)
                print(f"{indent}  Part {i}: TEXT ({len(part)} chars)")

        if current_text:
            page_contents[current_page] = "\n".join(current_text)

        # Show what would be passed to recursive calls
        print(f"{indent}  Page contents to recurse:")
        results = []
        for page_num in sorted(page_contents.keys()):
            page_text = page_contents[page_num]
            print(f"{indent}    Page {page_num}: {len(page_text)} chars")
            print(f"{indent}      Preview: {repr(page_text[:80])}...")

            # Check if this would trigger multi-page again
            sub_pages = extract_all_pages_from_content(page_text)
            print(f"{indent}      Sub-pages detected: {sub_pages}")

            if len(sub_pages) > 1:
                print(f"{indent}      !! WILL TRIGGER RECURSION AGAIN !!")

            results.append(
                {
                    "page": page_num,
                    "content": page_text,
                    "sub_pages": sub_pages,
                    "will_recurse": len(sub_pages) > 1,
                }
            )

            # Recurse if needed
            if len(sub_pages) > 1:
                simulate_split_logic(page_text, recursion_depth + 1)

        return results
    else:
        print(f"{indent}  -> SINGLE-PAGE BRANCH: Proceed to paragraph splitting")
        return []


def test_bug_scenario_1():
    """Test: Content with two consecutive page markers."""
    print("\n" + "=" * 60)
    print("TEST 2: Two consecutive page markers")
    print("=" * 60)

    content = """<!-- Page 1 -->
This is content from page 1.
It has multiple paragraphs.

Some more text here.

<!-- Page 2 -->
This is content from page 2.
Also has multiple paragraphs.

Final text on page 2."""

    simulate_split_logic(content)


def test_bug_scenario_2():
    """Test: Content where page marker is kept and causes recursion."""
    print("\n" + "=" * 60)
    print("TEST 3: Pathological case - markers create loop")
    print("=" * 60)

    # This simulates what happens AFTER one split iteration
    # The page_text passed to recursive call still has its marker
    content = """<!-- Page 1 -->
Text for page 1

<!-- Page 2 -->
Text for page 2"""

    # After split, page 1 content would be:
    page1_content = """<!-- Page 1 -->
Text for page 1
"""

    # After split, page 2 content would be:
    page2_content = """<!-- Page 2 -->
Text for page 2"""

    print("After first split, page contents would be:")
    print(f"Page 1 content: {repr(page1_content)}")
    print(f"  Pages detected: {extract_all_pages_from_content(page1_content)}")
    print()
    print(f"Page 2 content: {repr(page2_content)}")
    print(f"  Pages detected: {extract_all_pages_from_content(page2_content)}")
    print()
    print("-> Each page content has ONLY ONE page marker, so NO infinite loop here")


def test_bug_scenario_3():
    """Test: What if there's trailing content from previous page?"""
    print("\n" + "=" * 60)
    print("TEST 4: Content bleeds across split boundary")
    print("=" * 60)

    # Hypothetical scenario: what if split doesn't cleanly separate?
    # Let's check if the join operation causes issues

    content = "Text before\n<!-- Page 5 -->\nText after\n<!-- Page 6 -->\nMore text"

    page_pattern = re.compile(r"(<!--\s*Page\s+\d+\s*-->)")
    parts = page_pattern.split(content)

    print(f"Original: {repr(content)}")
    print(f"Parts after split: {parts}")
    print()

    # Simulate the grouping logic
    page_contents = {}
    current_page = 1  # Assume page_start=1
    current_text = []

    for part in parts:
        page_match = re.match(r"<!--\s*Page\s+(\d+)\s*-->", part)
        if page_match:
            if current_text:
                page_contents[current_page] = "\n".join(current_text)
            current_page = int(page_match.group(1))
            current_text = [part]  # BUG LINE
        else:
            current_text.append(part)

    if current_text:
        page_contents[current_page] = "\n".join(current_text)

    print("Resulting page_contents:")
    for page_num, text in sorted(page_contents.items()):
        pages_in_text = extract_all_pages_from_content(text)
        print(f"  Page {page_num}: {repr(text[:60])}...")
        print(f"    Pages detected in this content: {pages_in_text}")
        print(f"    Would trigger multi-page branch: {len(pages_in_text) > 1}")


def test_bug_scenario_4():
    """Test: The ACTUAL bug - newlines in join create weird content."""
    print("\n" + "=" * 60)
    print("TEST 5: Checking join behavior with empty parts")
    print("=" * 60)

    # The split can produce empty strings
    content = "<!-- Page 1 -->Text1<!-- Page 2 -->Text2"

    page_pattern = re.compile(r"(<!--\s*Page\s+\d+\s*-->)")
    parts = page_pattern.split(content)

    print(f"Original: {repr(content)}")
    print(f"Parts: {parts}")

    # Process
    page_contents = {}
    current_page = 0
    current_text = []

    for part in parts:
        page_match = re.match(r"<!--\s*Page\s+(\d+)\s*-->", part)
        if page_match:
            if current_text:
                joined = "\n".join(current_text)
                page_contents[current_page] = joined
                print(f"  Saved page {current_page}: {repr(joined)}")
            current_page = int(page_match.group(1))
            current_text = [part]
        else:
            current_text.append(part)

    if current_text:
        joined = "\n".join(current_text)
        page_contents[current_page] = joined
        print(f"  Saved page {current_page}: {repr(joined)}")

    print("\nFinal page_contents:")
    for page_num, text in sorted(page_contents.items()):
        print(f"  {page_num}: {repr(text)}")


def test_real_recursion_bug():
    """
    Test the ACTUAL recursion behavior with a chunker instance.
    This will hit the recursion limit if bug exists.
    """
    print("\n" + "=" * 60)
    print("TEST 6: Real chunker test with recursion tracking")
    print("=" * 60)

    chunker = HierarchicalChunker(max_chunk_size=500, min_chunk_size=50)

    # Test content
    test_content = """# Test Section

<!-- Page 1 -->
This is page 1 content. It has some text that we want to chunk properly.
The chunker should handle this without infinite recursion.

<!-- Page 2 -->
This is page 2 content. More text here for the second page.
Additional paragraphs to make the content longer.

Some more content to ensure we have enough text to trigger splitting."""

    print("Testing with multi-page content...")
    chunks = chunker.chunk_markdown(test_content, "test_doc")
    print(f"Success! Created {len(chunks)} chunks")

    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: page={chunk.page_start}, chars={chunk.char_count}")


def test_fixed_mixed_format_bug():
    """
    Test that the fix prevents infinite recursion with mixed page marker formats.
    This was the EXACT bug scenario causing 36+ hour hangs.
    """
    print("\n" + "=" * 60)
    print("TEST 10: CRITICAL - Verify fix for mixed format bug")
    print("=" * 60)

    chunker = HierarchicalChunker(max_chunk_size=500, min_chunk_size=50)

    # This content has BOTH <!-- Page X --> AND "Page X:" line-start format
    # This was causing infinite recursion before the fix
    bug_content = """<!-- Page 1 -->
This is page 1.
Page 2: Some header that looks like a page marker.
More content on page 1 that mentions Page 3.

<!-- Page 4 -->
Actual page 4 content."""

    print("Testing with mixed page marker formats (previously caused infinite loop)...")
    try:
        chunks = chunker.chunk_markdown(bug_content, "test_doc")
        print(f"✓ SUCCESS! Created {len(chunks)} chunks without infinite loop")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i}: page={chunk.page_start}, chars={chunk.char_count}")
    except RecursionError as e:
        print(f"✗ FAILED - Still has infinite recursion: {e}")
    except Exception as e:
        print(f"✗ ERROR: {e}")


def test_strip_all_page_markers():
    """
    Test the new _strip_all_page_markers helper method.
    """
    print("\n" + "=" * 60)
    print("TEST 11: _strip_all_page_markers helper")
    print("=" * 60)

    chunker = HierarchicalChunker()

    test_cases = [
        ("<!-- Page 1 -->\nText", "\nText"),
        ("[Page 2]\nMore text", "\nMore text"),
        ("Page 3: Header\nContent", "Header\nContent"),
        ("Page 4- Item\nStuff", "Item\nStuff"),
        (
            "Some text mentioning Page 5 in middle",
            "Some text mentioning Page 5 in middle",
        ),  # Should NOT strip
        # Note: After stripping, the line-start pattern also consumes preceding line breaks
        ("<!-- Page 1 -->\n[Page 2]\nPage 3: Mixed\nContent", "Mixed\nContent"),
    ]

    all_passed = True
    for original, expected in test_cases:
        result = chunker._strip_all_page_markers(original)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"{status} Input: {repr(original[:50])}")
        print(f"  Expected: {repr(expected[:50])}")
        print(f"  Got:      {repr(result[:50])}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ All strip tests passed!")
    else:
        print("\n✗ Some strip tests failed!")


def test_bug_scenario_5_mixed_formats():
    """
    Test: Mixed page marker formats.

    extract_all_pages_from_content detects:
    - <!-- Page X -->
    - [Page X]
    - ^Page X: (line start)

    BUT the split only uses <!-- Page X --> pattern!
    This could cause content with mixed formats to NOT be split properly.
    """
    print("\n" + "=" * 60)
    print("TEST 7: Mixed page marker formats")
    print("=" * 60)

    # Content with both HTML comment AND bracket format for DIFFERENT pages
    content = """<!-- Page 1 -->
Content from page 1.
[Page 2]
Content from page 2 using bracket format.
<!-- Page 3 -->
Content from page 3."""

    print(f"Original content:\n{content}\n")

    all_pages = extract_all_pages_from_content(content)
    print(f"All pages detected: {all_pages}")

    # Split by HTML comment pattern only
    page_pattern = re.compile(r"(<!--\s*Page\s+\d+\s*-->)")
    parts = page_pattern.split(content)
    print(f"\nParts after split: {parts}")

    # Process (simulating the bug)
    page_contents = {}
    current_page = 0
    current_text = []

    for part in parts:
        page_match = re.match(r"<!--\s*Page\s+(\d+)\s*-->", part)
        if page_match:
            if current_text:
                page_contents[current_page] = "\n".join(current_text)
            current_page = int(page_match.group(1))
            current_text = [part]
        else:
            current_text.append(part)

    if current_text:
        page_contents[current_page] = "\n".join(current_text)

    print("\nResulting page_contents:")
    for page_num, text in sorted(page_contents.items()):
        pages_in_text = extract_all_pages_from_content(text)
        print(f"  Page {page_num}:")
        print(f"    Content: {repr(text[:80])}...")
        print(f"    Pages detected: {pages_in_text}")
        print(f"    WILL RECURSE (bug trigger): {len(pages_in_text) > 1}")


def test_bug_scenario_6_line_start_format():
    """
    Test: Line-start 'Page X:' format mixed with HTML comments.
    """
    print("\n" + "=" * 60)
    print("TEST 8: Line-start Page format")
    print("=" * 60)

    content = """<!-- Page 1 -->
Page 1: Introduction
Some content here.

Page 2: Methodology
More content.

<!-- Page 3 -->
Page 3: Results
Final content."""

    print(f"Original content:\n{content}\n")

    all_pages = extract_all_pages_from_content(content)
    print(f"All pages detected: {all_pages}")
    print(f"Would trigger multi-page branch: {len(all_pages) > 1}")

    # This is the real bug scenario!
    # The split only handles <!-- Page X --> but extract_all_pages finds more


def test_bug_scenario_7_reproduce_hang():
    """
    Attempt to reproduce the exact hang condition.
    """
    print("\n" + "=" * 60)
    print("TEST 9: Reproduce exact hang condition")
    print("=" * 60)

    # Create content where split doesn't separate what extract_all_pages finds
    content = """<!-- Page 1 -->
This is page 1.
Page 2: Some header that looks like a page marker.
More content on page 1 that mentions Page 3.

<!-- Page 4 -->
Actual page 4 content."""

    simulate_split_logic(content)


if __name__ == "__main__":
    # Run fix verification tests first
    print("\n" + "#" * 60)
    print("# VERIFYING FIX FOR INFINITE RECURSION BUG")
    print("#" * 60)

    test_strip_all_page_markers()
    test_fixed_mixed_format_bug()
    test_real_recursion_bug()

    # Run analysis tests
    print("\n" + "#" * 60)
    print("# BUG ANALYSIS TESTS (for documentation)")
    print("#" * 60)

    test_extract_all_pages()
    test_bug_scenario_1()
    test_bug_scenario_2()
    test_bug_scenario_3()
    test_bug_scenario_4()
    test_bug_scenario_5_mixed_formats()
    test_bug_scenario_6_line_start_format()
    test_bug_scenario_7_reproduce_hang()

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
