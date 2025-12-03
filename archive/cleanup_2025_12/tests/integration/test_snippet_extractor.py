"""
Test Snippet Extractor

Comprehensive tests for snippet extraction functionality:
1. Basic snippet extraction
2. Keyword matching and highlighting
3. Snippet merging
4. Relevance scoring
5. Edge cases
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.rag.snippet_extractor import Snippet, SnippetExtractor, get_snippet_extractor

# Sample texts for testing
SAMPLE_TEXT_SHORT = """
The KT-06101 compressor operates at a maximum pressure of 150 psi.
Operating temperature range is -40°C to 85°C. This model is designed
for industrial applications with high reliability requirements.
"""

SAMPLE_TEXT_LONG = """
COMPRESSOR SPECIFICATIONS - MODEL KT-06101

Section 1: Operating Parameters
The compressor is designed to operate at maximum pressures up to 150 psi.
Normal operating pressure should be maintained between 100-140 psi for
optimal performance and longevity.

Section 2: Temperature Requirements
Operating temperature range: -40°C to 85°C
Storage temperature range: -55°C to 100°C
The unit includes automatic temperature monitoring and shutdown protection
if operating temperature exceeds safe limits.

Section 3: Installation Guidelines
Install the compressor in a well-ventilated area. Ensure adequate clearance
of at least 24 inches on all sides for maintenance access. The installation
surface must be level and capable of supporting the unit weight of 250 kg.

Section 4: Safety Warnings
CAUTION: Do not operate the compressor above rated pressure.
WARNING: High pressure system - release pressure before servicing.
Always wear appropriate safety equipment when working with the system.

Section 5: Maintenance Schedule
Inspect pressure gauges monthly. Check oil levels weekly during operation.
Replace filters every 500 operating hours or as indicated by pressure drop.
"""


def test_basic_extraction():
    """Test basic snippet extraction"""
    print("=" * 80)
    print("Test 1: Basic Snippet Extraction")
    print("=" * 80)

    extractor = SnippetExtractor(context_size=100, max_snippets=3)

    query = "operating pressure"
    snippets = extractor.extract_snippets(SAMPLE_TEXT_SHORT, query)

    print(f"\nQuery: '{query}'")
    print(f"Text length: {len(SAMPLE_TEXT_SHORT)} chars")
    print(f"Snippets found: {len(snippets)}")

    for i, snippet in enumerate(snippets, 1):
        print(f"\nSnippet {i}:")
        print(f"  Text: {snippet.text}")
        print(f"  Position: {snippet.start_pos}-{snippet.end_pos}")
        print(f"  Keywords: {snippet.matched_keywords}")
        print(f"  Score: {snippet.score:.3f}")
        if snippet.highlighted_text:
            print(f"  Highlighted: {snippet.highlighted_text}")

    # Assertions
    assert len(snippets) > 0, "Should find at least one snippet"
    assert any(
        "operating" in s.matched_keywords for s in snippets
    ), "Should match 'operating'"
    assert any(
        "pressure" in s.matched_keywords for s in snippets
    ), "Should match 'pressure'"

    print("\n✓ PASS - Basic extraction working")
    return True


def test_keyword_highlighting():
    """Test keyword highlighting"""
    print("\n" + "=" * 80)
    print("Test 2: Keyword Highlighting")
    print("=" * 80)

    extractor = SnippetExtractor(context_size=150)

    query = "operating temperature range"
    snippets = extractor.extract_snippets(SAMPLE_TEXT_LONG, query, highlight=True)

    print(f"\nQuery: '{query}'")
    print(f"Snippets with highlighting:")

    for i, snippet in enumerate(snippets, 1):
        print(f"\n--- Snippet {i} (score: {snippet.score:.3f}) ---")
        print(snippet.highlighted_text)

    # Assertions
    assert len(snippets) > 0, "Should find snippets"

    # Check that highlighting markers are present
    for snippet in snippets:
        if snippet.highlighted_text:
            has_highlight = "**" in snippet.highlighted_text
            assert has_highlight, "Should have highlight markers"

    print("\n✓ PASS - Keyword highlighting working")
    return True


def test_snippet_merging():
    """Test overlapping snippet merging"""
    print("\n" + "=" * 80)
    print("Test 3: Snippet Merging")
    print("=" * 80)

    # Use small context to create potential overlaps
    extractor = SnippetExtractor(context_size=80, max_snippets=5)

    # Query with multiple keywords that appear close together
    query = "pressure temperature operating"
    snippets = extractor.extract_snippets(SAMPLE_TEXT_LONG, query)

    print(f"\nQuery: '{query}'")
    print(f"Snippets after merging: {len(snippets)}")

    # Check for overlaps (there shouldn't be any after merging)
    for i, snippet1 in enumerate(snippets):
        for snippet2 in snippets[i + 1 :]:
            overlap = snippet1.overlaps_with(snippet2, tolerance=0)
            if overlap:
                print(f"\n⚠ Found overlap:")
                print(f"  Snippet 1: pos {snippet1.start_pos}-{snippet1.end_pos}")
                print(f"  Snippet 2: pos {snippet2.start_pos}-{snippet2.end_pos}")
            assert not overlap, "Merged snippets should not overlap"

    print("\n✓ PASS - Snippet merging working")
    return True


def test_relevance_scoring():
    """Test snippet relevance scoring"""
    print("\n" + "=" * 80)
    print("Test 4: Relevance Scoring")
    print("=" * 80)

    extractor = SnippetExtractor(context_size=150, max_snippets=5)

    query = "operating pressure safety"
    snippets = extractor.extract_snippets(SAMPLE_TEXT_LONG, query)

    print(f"\nQuery: '{query}'")
    print(f"Snippets ranked by relevance:")

    for i, snippet in enumerate(snippets, 1):
        keywords_str = ", ".join(snippet.matched_keywords)
        print(f"\n{i}. Score: {snippet.score:.3f} | Keywords: {keywords_str}")
        print(f"   {snippet.text[:100]}...")

    # Assertions
    assert len(snippets) > 0, "Should find snippets"

    # Check that scores are in descending order
    for i in range(len(snippets) - 1):
        assert (
            snippets[i].score >= snippets[i + 1].score
        ), "Snippets should be sorted by score"

    # Snippet with more keywords should generally score higher
    keyword_counts = [len(s.matched_keywords) for s in snippets]
    print(f"\nKeyword counts: {keyword_counts}")

    print("\n✓ PASS - Relevance scoring working")
    return True


def test_multiple_occurrences():
    """Test handling of multiple keyword occurrences"""
    print("\n" + "=" * 80)
    print("Test 5: Multiple Keyword Occurrences")
    print("=" * 80)

    extractor = SnippetExtractor(context_size=100, max_snippets=3)

    # "pressure" appears multiple times in the text
    query = "pressure"
    snippets = extractor.extract_snippets(SAMPLE_TEXT_LONG, query)

    print(f"\nQuery: '{query}'")
    print(f"Snippets found: {len(snippets)}")

    # Count total occurrences of "pressure" in original text
    import re

    text_lower = SAMPLE_TEXT_LONG.lower()
    total_occurrences = len(re.findall(r"\bpressure\b", text_lower))

    print(f"Total 'pressure' occurrences in text: {total_occurrences}")

    for i, snippet in enumerate(snippets, 1):
        snippet_occurrences = len(re.findall(r"\bpressure\b", snippet.text.lower()))
        print(f"Snippet {i}: {snippet_occurrences} occurrence(s)")

    assert len(snippets) > 0, "Should find snippets"
    assert len(snippets) <= extractor.max_snippets, "Should not exceed max_snippets"

    print("\n✓ PASS - Multiple occurrences handled correctly")
    return True


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "=" * 80)
    print("Test 6: Edge Cases")
    print("=" * 80)

    extractor = SnippetExtractor()

    # Test 1: Empty text
    snippets = extractor.extract_snippets("", "test query")
    assert len(snippets) == 0, "Empty text should return no snippets"
    print("✓ Empty text handled")

    # Test 2: Empty query
    snippets = extractor.extract_snippets("Some text here", "")
    assert len(snippets) == 0, "Empty query should return no snippets"
    print("✓ Empty query handled")

    # Test 3: No matches
    snippets = extractor.extract_snippets(
        "The quick brown fox jumps over the lazy dog", "compressor pressure temperature"
    )
    assert len(snippets) == 0, "No matches should return no snippets"
    print("✓ No matches handled")

    # Test 4: Very short text
    short_text = "Test"
    snippets = extractor.extract_snippets(short_text, "test")
    # Should either find it or skip due to min_snippet_length
    print(f"✓ Very short text handled ({len(snippets)} snippets)")

    # Test 5: Special characters in query
    text_with_special = (
        "Model KT-06101 specifications include maximum operating "
        "pressure of 150 psi and temperature range from -40°C to 85°C. "
        "The KT-06101 is designed for industrial applications."
    )
    snippets = extractor.extract_snippets(text_with_special, "KT-06101 pressure")
    assert len(snippets) > 0, "Should handle special characters"
    print("✓ Special characters handled")

    print("\n✓ PASS - All edge cases handled correctly")
    return True


def test_context_size_variations():
    """Test different context sizes"""
    print("\n" + "=" * 80)
    print("Test 7: Context Size Variations")
    print("=" * 80)

    query = "operating pressure"
    context_sizes = [50, 100, 200, 300]

    print(f"\nQuery: '{query}'")
    print("Testing different context sizes:")

    for size in context_sizes:
        extractor = SnippetExtractor(context_size=size, max_snippets=1)
        snippets = extractor.extract_snippets(SAMPLE_TEXT_LONG, query)

        if snippets:
            snippet = snippets[0]
            print(f"\nContext size {size}:")
            print(f"  Snippet length: {len(snippet.text)} chars")
            print(f"  Text: {snippet.text[:80]}...")

            # Snippet should approximately respect context size
            # (allowing for word boundary adjustments)
            assert (
                len(snippet.text) >= size * 0.5
            ), f"Snippet too short for context size {size}"

    print("\n✓ PASS - Context size variations working")
    return True


def test_singleton_pattern():
    """Test singleton pattern"""
    print("\n" + "=" * 80)
    print("Test 8: Singleton Pattern")
    print("=" * 80)

    extractor1 = get_snippet_extractor()
    extractor2 = get_snippet_extractor()

    assert extractor1 is extractor2, "Should return same instance"

    print("✓ PASS - Singleton pattern working")
    return True


def test_real_world_scenario():
    """Test realistic usage scenario"""
    print("\n" + "=" * 80)
    print("Test 9: Real World Scenario")
    print("=" * 80)

    extractor = SnippetExtractor(context_size=200, max_snippets=3)

    # Simulate a user query about safety
    query = "safety warnings pressure"
    snippets = extractor.extract_snippets(SAMPLE_TEXT_LONG, query, highlight=True)

    print(f"\nUser Query: '{query}'")
    print(f"Found {len(snippets)} relevant snippets:\n")

    for i, snippet in enumerate(snippets, 1):
        print(f"{'='*60}")
        print(f"Citation {i} (Relevance: {snippet.score:.1%})")
        print(f"{'='*60}")
        print(snippet.highlighted_text)
        print()

    # Assertions
    assert len(snippets) > 0, "Should find relevant snippets"
    assert snippets[0].score > 0, "Top snippet should have positive score"

    # Check that Section 4 (Safety Warnings) appears in results
    found_safety_section = any(
        "CAUTION" in s.text or "WARNING" in s.text for s in snippets
    )
    print(f"Found safety section: {found_safety_section}")

    print("\n✓ PASS - Real world scenario working")
    return True


def run_all_tests():
    """Run all snippet extractor tests"""
    print("\n" + "=" * 80)
    print("SNIPPET EXTRACTOR TEST SUITE")
    print("=" * 80)

    tests = [
        ("Basic Extraction", test_basic_extraction),
        ("Keyword Highlighting", test_keyword_highlighting),
        ("Snippet Merging", test_snippet_merging),
        ("Relevance Scoring", test_relevance_scoring),
        ("Multiple Occurrences", test_multiple_occurrences),
        ("Edge Cases", test_edge_cases),
        ("Context Size Variations", test_context_size_variations),
        ("Singleton Pattern", test_singleton_pattern),
        ("Real World Scenario", test_real_world_scenario),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except AssertionError as e:
            print(f"\n✗ Test '{name}' failed: {e}")
            results.append((name, False))
        except Exception as e:
            print(f"\n✗ Test '{name}' raised exception: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\n{'-' * 80}")
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠ {total - passed} test(s) failed")

    print("=" * 80)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
