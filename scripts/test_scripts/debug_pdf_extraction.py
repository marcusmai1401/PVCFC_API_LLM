"""
Debug PDF extraction to see what's happening
"""

from pathlib import Path

import fitz  # PyMuPDF


def debug_pdf(pdf_path: str):
    """Debug PDF extraction"""

    print(f"Debugging PDF: {pdf_path}")
    print(f"Exists: {Path(pdf_path).exists()}")
    print()

    try:
        doc = fitz.open(pdf_path)
        print(f"✅ Opened PDF: {len(doc)} pages")
        print()

        for page_num in range(min(3, len(doc))):  # First 3 pages
            page = doc[page_num]
            page_index = page_num + 1

            print(f"Page {page_index}:")

            # Extract text
            text = page.get_text("text")
            char_count = len(text)

            print(f"   Chars: {char_count}")
            print(f"   Text preview: {text[:200] if text else '(empty)'}...")
            print()

            # Blocks
            try:
                blocks = page.get_text("dict")["blocks"]
                print(f"   Blocks: {len(blocks)}")
            except:
                print(f"   Blocks: error")

            # Images
            try:
                images = page.get_images()
                print(f"   Images: {len(images)}")
            except:
                print(f"   Images: error")

            print()

        doc.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Test PDFs - use vector format ones for testing
    pdfs = [
        r"D:\Data_Raw\Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf",
        r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf",
    ]

    for pdf_path in pdfs:
        debug_pdf(pdf_path)
        print("=" * 80)
        print()
