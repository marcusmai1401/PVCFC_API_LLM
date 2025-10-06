"""
Test page extraction tool on a small subset of PDFs
Verifies extraction works before running on full dataset
"""

import json

# Add parent to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.build_page_index import PageIndexBuilder


def test_extraction():
    """Test page extraction on 2-3 PDFs"""

    print("=" * 80)
    print("TEST: Page Extraction Tool")
    print("=" * 80)
    print()

    # Load doc_id_map
    doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")

    if not doc_id_map_path.exists():
        print(f"❌ doc_id_map not found: {doc_id_map_path}")
        return False

    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print(f"✅ Loaded doc_id_map with {len(doc_id_map)} documents")
    print()

    # Select first 2 documents with existing PDFs
    test_docs = {}
    count = 0

    for doc_id, doc_info in doc_id_map.items():
        pdf_path = doc_info.get("pdf_path")

        if not pdf_path:
            continue

        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print(f"⚠️  PDF not found: {pdf_path}")
            continue

        test_docs[doc_id] = doc_info
        count += 1

        if count >= 2:
            break

    if not test_docs:
        print("❌ No valid PDFs found for testing")
        return False

    print(f"📄 Testing with {len(test_docs)} documents:")
    for i, (doc_id, info) in enumerate(test_docs.items(), 1):
        print(f"   {i}. {info['file_name']}")
        print(f"      Pages: {info['total_pages']}, Chunks: {info['total_chunks']}")
    print()

    # Create test builder
    output_dir = Path("artifacts/test_page_index")
    output_dir.mkdir(parents=True, exist_ok=True)

    builder = PageIndexBuilder(
        doc_id_map_path=str(doc_id_map_path),
        output_dir=str(output_dir),
    )

    # Override doc_id_map to test subset
    builder.stats["total_docs"] = len(test_docs)

    # Test extraction
    print("🔍 Extracting page text...")

    import jsonlines

    total_pages = 0

    with jsonlines.open(builder.text_by_page_path, mode="w") as writer:
        for doc_id, doc_info in test_docs.items():
            pdf_path = Path(doc_info["pdf_path"])

            pages_data = builder.extract_page_text(pdf_path, doc_id)

            for page_data in pages_data:
                writer.write(page_data)
                total_pages += 1

    print(f"✅ Extracted {total_pages} pages")
    print()

    # Verify output
    print("📊 Verifying output...")

    if not builder.text_by_page_path.exists():
        print(f"❌ Output file not created: {builder.text_by_page_path}")
        return False

    # Read and analyze
    pages = []
    with jsonlines.open(builder.text_by_page_path) as reader:
        for obj in reader:
            pages.append(obj)

    print(f"✅ Read {len(pages)} pages from output")
    print()

    # Show sample
    if pages:
        print("📄 Sample page data:")
        sample = pages[0]
        print(f"   Doc ID: {sample['doc_id'][:60]}...")
        print(f"   Page: {sample['page']}")
        print(f"   Chars: {sample['char_count']}, Words: {sample['word_count']}")
        print(
            f"   Has tables: {sample['has_tables']}, Has figures: {sample['has_figures']}"
        )
        print(f"   Text preview: {sample['text'][:100]}...")
        print()

    # Stats
    doc_pages = {}
    for page in pages:
        doc_id = page["doc_id"]
        doc_pages[doc_id] = doc_pages.get(doc_id, 0) + 1

    print("📈 Page counts by document:")
    for doc_id, count in doc_pages.items():
        doc_name = test_docs[doc_id]["file_name"]
        print(f"   • {doc_name}: {count} pages")
    print()

    print("=" * 80)
    print("✅ TEST PASSED - Extraction works correctly!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("   1. Run full build: python tools/build_page_index.py build")
    print("   2. This will process all PDFs and create page indices")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_extraction()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
