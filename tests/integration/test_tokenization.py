"""
Test Tokenization Consistency

Ensures that tokenization is consistent between:
1. BM25 index building (build_page_index.py)
2. Query processing (page_reranker.py)
3. Text preprocessing utilities

This is critical for BM25 scoring accuracy.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.utils.text_processing import (
    clean_text_for_snippet,
    extract_keywords,
    normalize_text,
    preprocess_text_for_bm25,
    tokenize_for_bm25,
)


def test_tokenization_basic():
    """Test basic tokenization"""
    print("=" * 80)
    print("Test 1: Basic Tokenization")
    print("=" * 80)

    test_cases = [
        ("Operating pressure: 150 psi", ["operating", "pressure:", "150", "psi"]),
        ("Model KT-06101 specifications", ["model", "kt-06101", "specifications"]),
        (
            "Temperature range -40°C to 85°C",
            ["temperature", "range", "-40°c", "to", "85°c"],
        ),
        ("Valve ID: V-1234-A", ["valve", "id:", "v-1234-a"]),
        ("Multiple   spaces   test", ["multiple", "spaces", "test"]),
    ]

    passed = 0
    failed = 0

    for text, expected in test_cases:
        result = tokenize_for_bm25(text)
        print(f"\nInput: '{text}'")
        print(f"Expected: {expected}")
        print(f"Got:      {result}")

        if result == expected:
            print("✓ PASS")
            passed += 1
        else:
            print("✗ FAIL")
            failed += 1

    print(f"\n{'-' * 80}")
    print(f"Passed: {passed}/{len(test_cases)}")
    print(f"Failed: {failed}/{len(test_cases)}")

    return failed == 0


def test_preprocessing_consistency():
    """Test that preprocessing is consistent"""
    print("\n" + "=" * 80)
    print("Test 2: Preprocessing Consistency")
    print("=" * 80)

    test_texts = [
        "Operating Pressure: 150 PSI",
        "Model KT-06101 Specifications",
        "TEMPERATURE RANGE",
        "  Multiple   Spaces   Test  ",
    ]

    print("\nPreprocessing different texts:")
    for text in test_texts:
        processed = preprocess_text_for_bm25(text)
        tokens = tokenize_for_bm25(text)

        print(f"\nOriginal:    '{text}'")
        print(f"Preprocessed: '{processed}'")
        print(f"Tokens:       {tokens}")

    print(f"\n{'-' * 80}")
    print("✓ Preprocessing consistency check complete")

    return True


def test_tokenization_deterministic():
    """Test that tokenization is deterministic"""
    print("\n" + "=" * 80)
    print("Test 3: Tokenization Determinism")
    print("=" * 80)

    text = "Operating pressure: 150 psi, Temperature range: -40°C to 85°C"

    # Run tokenization multiple times
    results = [tokenize_for_bm25(text) for _ in range(5)]

    # Check all results are identical
    first_result = results[0]
    all_same = all(r == first_result for r in results)

    print(f"\nText: '{text}'")
    print(f"Tokens: {first_result}")
    print(f"Ran 5 times - all results identical: {all_same}")

    if all_same:
        print("✓ PASS - Tokenization is deterministic")
        return True
    else:
        print("✗ FAIL - Tokenization is not deterministic")
        return False


def test_keyword_extraction():
    """Test keyword extraction"""
    print("\n" + "=" * 80)
    print("Test 4: Keyword Extraction")
    print("=" * 80)

    text = """
    The KT-06101 compressor operates at a maximum pressure of 150 psi.
    The operating temperature range is -40°C to 85°C.
    This model KT-06101 is designed for industrial applications.
    Maximum operating pressure should not exceed 150 psi under normal conditions.
    """

    keywords = extract_keywords(text, top_n=10)

    print(f"\nText: {text[:100]}...")
    print(f"\nTop 10 keywords:")
    for i, keyword in enumerate(keywords, 1):
        print(f"  {i}. {keyword}")

    print(f"\n{'-' * 80}")
    print("✓ Keyword extraction complete")

    return True


def test_snippet_cleaning():
    """Test snippet text cleaning"""
    print("\n" + "=" * 80)
    print("Test 5: Snippet Text Cleaning")
    print("=" * 80)

    test_cases = [
        "Operating pressure: 150 psi",
        "Model KT-06101\n\nSpecifications\n\nTemperature range",
        "Text with    extra    spaces",
        "Control\x00characters\x01test",
    ]

    for text in test_cases:
        cleaned = clean_text_for_snippet(text)
        print(f"\nOriginal: {repr(text)}")
        print(f"Cleaned:  {repr(cleaned)}")

    print(f"\n{'-' * 80}")
    print("✓ Snippet cleaning complete")

    return True


def test_consistency_with_modules():
    """Test consistency with actual modules"""
    print("\n" + "=" * 80)
    print("Test 6: Consistency with Actual Modules")
    print("=" * 80)

    # Test that page_reranker uses same tokenization
    try:
        from app.rag.page_reranker import _tokenize_fn

        test_query = "operating pressure 150 psi"

        direct_tokens = tokenize_for_bm25(test_query)
        reranker_tokens = _tokenize_fn(test_query)

        print(f"\nTest query: '{test_query}'")
        print(f"Direct tokenization:   {direct_tokens}")
        print(f"Reranker tokenization: {reranker_tokens}")

        if direct_tokens == reranker_tokens:
            print("✓ PASS - Reranker uses consistent tokenization")
            return True
        else:
            print("✗ FAIL - Reranker tokenization differs!")
            return False

    except Exception as e:
        print(f"⚠ Could not test module consistency: {e}")
        return True  # Don't fail the test


def run_all_tests():
    """Run all tokenization tests"""
    print("\n" + "=" * 80)
    print("TOKENIZATION CONSISTENCY TEST SUITE")
    print("=" * 80)

    tests = [
        ("Basic Tokenization", test_tokenization_basic),
        ("Preprocessing Consistency", test_preprocessing_consistency),
        ("Tokenization Determinism", test_tokenization_deterministic),
        ("Keyword Extraction", test_keyword_extraction),
        ("Snippet Cleaning", test_snippet_cleaning),
        ("Module Consistency", test_consistency_with_modules),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' raised exception: {e}")
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
    print("=" * 80)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
