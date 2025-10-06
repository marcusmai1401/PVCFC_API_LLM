"""
Verify that the ingestion pipeline's OCR actually works on scanned PDFs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.ingestion.pdf_processor import PDFProcessor


def test_ingestion_ocr():
    print("=" * 80)
    print("TESTING INGESTION PIPELINE OCR")
    print("=" * 80)

    # Initialize PDF processor with OCR enabled (same as ingestion pipeline)
    processor = PDFProcessor(
        extract_tables=False,
        extract_images=False,
        min_text_length=10,  # Same as ingestion
        enable_ocr=True,
        ocr_language="eng",
        ocr_min_confidence=30.0,  # Same as ingestion
    )

    # Test on scanned PDF
    test_pdf = Path(
        r"D:\Data_Raw\003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"
    )

    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        return False

    print(f"\nProcessing: {test_pdf.name}")
    print()

    try:
        pdf_doc = processor.process_pdf(test_pdf)

        print(f"✅ Success!")
        print(f"   Pages processed: {pdf_doc.num_pages}")
        print(f"   Total chars: {pdf_doc.total_chars}")
        print(f"   Total words: {pdf_doc.total_words}")
        print(f"   Source format: {pdf_doc.source_format}")
        print()

        # Show first page
        if pdf_doc.pages:
            page1 = pdf_doc.pages[0]
            print(f"Page 1:")
            print(f"   Chars: {page1.char_count}")
            print(f"   Words: {page1.word_count}")
            print(f"   Text preview: {page1.text[:200]}...")
            print()

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ingestion_ocr()
    sys.exit(0 if success else 1)
