"""
Simple test for page detection without external dependencies
"""
import re


def extract_all_pages_from_content(text: str):
    """
    Extract ALL page numbers from content markers.
    """
    if not text:
        return []

    pages = set()

    # Find all <!-- Page X --> markers
    for match in re.finditer(r"<!--\s*Page\s+(\d+)\s*-->", text, re.IGNORECASE):
        pages.add(int(match.group(1)))

    # Find all [Page X] markers
    for match in re.finditer(r"\[\s*Page\s+(\d+)\s*\]", text, re.IGNORECASE):
        pages.add(int(match.group(1)))

    # Find "Page X" at line starts
    for match in re.finditer(
        r"^\s*Page\s+(\d+)\s*[:\-]?", text, re.IGNORECASE | re.MULTILINE
    ):
        pages.add(int(match.group(1)))

    return sorted(list(pages))


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("PAGE DETECTION TEST")
    print("=" * 80 + "\n")

    # Test 1: Multiple page markers
    test_content1 = """
    <!-- Page 15 -->
    This is content from page 15.

    <!-- Page 16 -->
    This is content from page 16.

    <!-- Page 17 -->
    This is content from page 17.
    """

    pages = extract_all_pages_from_content(test_content1)
    print(f"Test 1 - Multiple pages: {pages}")
    assert pages == [15, 16, 17], f"Expected [15, 16, 17], got {pages}"
    print("✓ PASS\n")

    # Test 2: Single page
    test_content2 = """
    <!-- Page 42 -->
    Single page content
    """

    pages = extract_all_pages_from_content(test_content2)
    print(f"Test 2 - Single page: {pages}")
    assert pages == [42], f"Expected [42], got {pages}"
    print("✓ PASS\n")

    # Test 3: No pages
    test_content3 = """
    Content without page markers
    """

    pages = extract_all_pages_from_content(test_content3)
    print(f"Test 3 - No pages: {pages}")
    assert pages == [], f"Expected [], got {pages}"
    print("✓ PASS\n")

    # Test 4: Mixed formats
    test_content4 = """
    <!-- Page 10 -->
    [Page 11]
    Page 12: Some content
    <!-- Page 13 -->
    """

    pages = extract_all_pages_from_content(test_content4)
    print(f"Test 4 - Mixed formats: {pages}")
    assert pages == [10, 11, 12, 13], f"Expected [10, 11, 12, 13], got {pages}"
    print("✓ PASS\n")

    print("=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)
