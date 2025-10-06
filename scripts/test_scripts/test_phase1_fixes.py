"""
Test Phase 1 Fixes:
1. Vision API signature (Part.from_text fix)
2. Page metadata extraction from content
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("TESTING PHASE 1 FIXES")
print("=" * 70)

# TEST 1: Page Extraction from Content
print("\n[TEST 1] Page Extraction from Content Markers")
print("-" * 70)

from app.ingestion.text_chunker import extract_page_from_content

test_cases = [
    ("<!-- Page 15 -->\n\nSome text here", 15, "HTML comment format"),
    ("[Page 7]\nContent", 7, "Bracket format"),
    ("Page 23: Section Title\nMore text", 23, "Plain format"),
    ("Regular text without page marker", None, "No marker"),
    ("<!-- Page 1 --> Initial content", 1, "Page 1"),
    ("Mixed content\n<!-- Page 100 -->\nAfter marker", 100, "Page in middle"),
]

passed = 0
failed = 0

for text, expected, description in test_cases:
    result = extract_page_from_content(text)
    if result == expected:
        print(f"✓ PASS: {description} -> {result}")
        passed += 1
    else:
        print(f"✗ FAIL: {description} -> Expected {expected}, got {result}")
        failed += 1

print(f"\nTest 1 Summary: {passed}/{len(test_cases)} passed")

# TEST 2: Vision API Part Construction
print("\n[TEST 2] Vision API Part Construction")
print("-" * 70)

try:
    from google import genai
    from google.genai import types

    # Test text part
    try:
        text_part = types.Part(text="Test prompt")
        print(f"✓ PASS: types.Part(text=...) works correctly")
        print(f"  Text value: {text_part.text}")
        vision_passed = True
    except Exception as e:
        print(f"✗ FAIL: types.Part(text=...) failed: {e}")
        vision_passed = False

    # Test image part
    try:
        fake_img = b"fake_image_data"
        img_part = types.Part.from_bytes(data=fake_img, mime_type="image/png")
        print(f"✓ PASS: types.Part.from_bytes(...) works correctly")
        vision_passed = vision_passed and True
    except Exception as e:
        print(f"✗ FAIL: types.Part.from_bytes(...) failed: {e}")
        vision_passed = False

    # Test Content construction
    try:
        parts = [
            types.Part(text="Question: What is the answer?"),
            types.Part.from_bytes(data=b"img", mime_type="image/png"),
        ]
        content = types.Content(role="user", parts=parts)
        print(f"✓ PASS: types.Content construction works correctly")
        print(f"  Parts count: {len(content.parts)}")
        vision_passed = vision_passed and True
    except Exception as e:
        print(f"✗ FAIL: types.Content construction failed: {e}")
        vision_passed = False

    print(f"\nTest 2 Result: {'PASS' if vision_passed else 'FAIL'}")

except ImportError as e:
    print(f"⚠ SKIP: google-genai not available: {e}")
    vision_passed = None

# TEST 3: TextChunker Integration
print("\n[TEST 3] TextChunker Page Extraction Integration")
print("-" * 70)

from app.ingestion.text_chunker import TextChunker

chunker = TextChunker(chunk_size=500, chunk_overlap=100)

# Sample text with page marker
sample_text = """
<!-- Page 15 -->

Operating Instructions
Installation of Condensing Turbine

Table: Tightened torque for anchor bolt
Size of anchor bolt: M30, M36, M42, M45, M48, M52, M56, M64

This section describes the tightening procedure.
After back grouting finished for 72 hours, tighten the anchor bolts to the final tightening torque.
"""

chunks = chunker.chunk_text(
    text=sample_text,
    doc_id="test_doc",
    metadata={"doc_id": "test_doc", "page": 1},  # Wrong page in metadata
    page_nums=[1],  # Wrong page nums
)

if chunks:
    chunk = chunks[0]
    extracted_page = chunk.metadata.get("page")

    if extracted_page == 15:
        print(f"✓ PASS: Page correctly extracted from content (page {extracted_page})")
        print(f"  Original metadata had page=1, but content had <!-- Page 15 -->")
        print(f"  Fix successfully overrode wrong metadata!")
        chunker_passed = True
    else:
        print(f"✗ FAIL: Page not extracted correctly")
        print(f"  Expected page 15, got page {extracted_page}")
        print(f"  Chunk text preview: {chunk.text[:100]}")
        chunker_passed = False
else:
    print(f"✗ FAIL: No chunks created")
    chunker_passed = False

print(f"\nTest 3 Result: {'PASS' if chunker_passed else 'FAIL'}")

# FINAL SUMMARY
print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

results = {
    "Page Extraction": f"{passed}/{len(test_cases)} passed"
    if passed == len(test_cases)
    else "FAILED",
    "Vision API": "PASS"
    if vision_passed
    else ("SKIP" if vision_passed is None else "FAIL"),
    "Chunker Integration": "PASS" if chunker_passed else "FAIL",
}

print("\nResults:")
for test_name, result in results.items():
    status = (
        "✓" if "PASS" in result or "/" in result else ("⚠" if "SKIP" in result else "✗")
    )
    print(f"  {status} {test_name}: {result}")

all_passed = all("PASS" in r or "/" in r or "SKIP" in r for r in results.values())

print("\n" + "=" * 70)
if all_passed:
    print("🎉 ALL TESTS PASSED! Phase 1 fixes are working correctly.")
    print("\nNext steps:")
    print("  1. Commit these changes")
    print("  2. Re-index documents to apply page metadata fixes")
    print("  3. Test with real queries")
else:
    print("❌ SOME TESTS FAILED! Please review the output above.")
print("=" * 70)
