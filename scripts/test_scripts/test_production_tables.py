"""
Production PDF Table Extraction Test
Scans available PDFs and tests table extraction on real documents
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from app.ingestion.pdf_processor import PDFProcessor
from app.ingestion.text_chunker import TextChunker

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def scan_pdf_for_tables(pdf_path: Path, max_pages: int = 20):
    """Scan a PDF for tables and return results"""

    print(f"\n{'='*80}")
    print(f"Scanning: {pdf_path.name}")
    print(f"{'='*80}")

    # Process with table extraction
    processor = PDFProcessor(
        extract_tables=True,
        table_min_rows=2,
        table_min_cols=2,
    )

    try:
        pdf_doc = processor.process_pdf(pdf_path)

        print(f"✓ PDF processed successfully")
        print(f"  - Total pages: {len(pdf_doc.pages)}")
        print(f"  - Total words: {pdf_doc.total_words}")

        # Scan for tables
        tables_found = []
        pages_with_tables = 0

        for page in pdf_doc.pages[:max_pages]:  # Limit scan
            if page.tables:
                pages_with_tables += 1
                for table in page.tables:
                    tables_found.append(
                        {
                            "page": page.page_num,
                            "table": table,
                        }
                    )

                    print(f"\n✓ Page {page.page_num}: Found table")
                    print(f"  - Dimensions: {table['row_count']}×{table['col_count']}")
                    print(f"  - Confidence: {table['confidence']}")

                    # Show table preview
                    if table["markdown"]:
                        print(f"  - Preview:")
                        lines = table["markdown"].split("\n")
                        for line in lines[:6]:  # First 6 lines
                            print(f"    {line}")
                        if len(lines) > 6:
                            print(f"    ... ({len(lines)-6} more lines)")

        print(f"\n{'─'*80}")
        print(
            f"Summary: {len(tables_found)} table(s) found on {pages_with_tables} page(s)"
        )
        print(f"{'─'*80}")

        return {
            "pdf_path": pdf_path,
            "success": True,
            "pages_scanned": min(len(pdf_doc.pages), max_pages),
            "tables_found": len(tables_found),
            "pages_with_tables": pages_with_tables,
            "tables": tables_found,
        }

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return {
            "pdf_path": pdf_path,
            "success": False,
            "error": str(e),
        }


def test_chunking_with_tables(pdf_path: Path):
    """Test chunking with table integration"""

    print(f"\n{'='*80}")
    print(f"Testing Chunking: {pdf_path.name}")
    print(f"{'='*80}")

    # Process PDF
    processor = PDFProcessor(extract_tables=True)
    pdf_doc = processor.process_pdf(pdf_path)

    # Chunk document
    chunker = TextChunker(
        chunk_size=1000, chunk_overlap=200, chunking_strategy="semantic"
    )

    doc_dict = pdf_doc.to_dict()
    chunks = chunker.chunk_document(doc_dict, doc_id=pdf_path.stem)

    print(f"✓ Created {len(chunks)} chunks")

    # Analyze chunks with tables
    chunks_with_tables = [c for c in chunks if c.metadata.get("has_tables")]

    if chunks_with_tables:
        print(f"✓ Chunks with tables: {len(chunks_with_tables)}")

        for chunk in chunks_with_tables[:3]:  # Show first 3
            print(f"\n  Chunk {chunk.chunk_index}:")
            print(f"    - Page: {chunk.metadata.get('page')}")
            print(f"    - Size: {chunk.char_count} chars")
            print(f"    - Has markdown tables: {'|' in chunk.text}")

            # Find table section
            if "<!-- TABLE" in chunk.text:
                start = chunk.text.find("<!-- TABLE")
                end = chunk.text.find("<!-- END TABLE", start)
                if end > start:
                    table_section = chunk.text[start : end + 20]
                    lines = table_section.split("\n")[:8]
                    print(f"    - Table preview:")
                    for line in lines:
                        print(f"      {line}")
    else:
        print("  No chunks with tables found")

    return chunks


def main():
    """Main test function"""

    print("\n" + "█" * 80)
    print("PRODUCTION PDF TABLE EXTRACTION TEST")
    print("█" * 80)

    # Define PDFs to test
    test_pdfs = [
        Path(
            "data/raw/phase1_pilot/003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"
        ),
        Path(
            "data/raw/phase1_pilot/Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf"
        ),
        Path(
            "data/raw/phase1_pilot/092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf"
        ),
        Path("data/raw/samples/sample_datasheet.pdf"),
    ]

    # Filter to existing PDFs
    available_pdfs = [pdf for pdf in test_pdfs if pdf.exists()]

    if not available_pdfs:
        print("\n✗ ERROR: No test PDFs found!")
        print("Expected PDFs in data/raw/phase1_pilot/ or data/raw/samples/")
        return False

    print(f"\nFound {len(available_pdfs)} PDF(s) to test\n")

    # Scan all PDFs for tables
    all_results = []

    for pdf_path in available_pdfs:
        result = scan_pdf_for_tables(pdf_path, max_pages=20)
        all_results.append(result)

    # Summary
    print("\n" + "█" * 80)
    print("SCAN SUMMARY")
    print("█" * 80)

    total_tables = 0
    pdfs_with_tables = 0

    for result in all_results:
        if result["success"]:
            tables = result.get("tables_found", 0)
            total_tables += tables
            if tables > 0:
                pdfs_with_tables += 1

            status = "✓" if tables > 0 else "○"
            print(f"{status} {result['pdf_path'].name}")
            print(
                f"   Pages scanned: {result.get('pages_scanned', 0)}, Tables found: {tables}"
            )

    print(f"\n{'─'*80}")
    print(
        f"Total: {total_tables} tables found in {pdfs_with_tables}/{len(all_results)} PDFs"
    )
    print(f"{'─'*80}")

    # If tables found, test chunking on first PDF with tables
    pdf_with_tables = next(
        (r for r in all_results if r.get("tables_found", 0) > 0), None
    )

    if pdf_with_tables:
        print(f"\n{'='*80}")
        print("TESTING CHUNKING WITH TABLES")
        print(f"{'='*80}")

        chunks = test_chunking_with_tables(pdf_with_tables["pdf_path"])

        # Save output
        output_dir = Path("test_output/production")
        output_dir.mkdir(parents=True, exist_ok=True)

        chunker = TextChunker()
        output_file = output_dir / f"{pdf_with_tables['pdf_path'].stem}_chunks.json"
        chunker.save_chunks(chunks, output_file)

        print(f"\n✓ Saved chunks to: {output_file}")
    else:
        print("\n⚠ No tables found in any PDFs")
        print("This might be because:")
        print("  - PDFs don't contain bordered tables")
        print("  - Tables are text-based without visible borders")
        print("  - PyMuPDF couldn't detect table structures")

    # Final result
    print("\n" + "█" * 80)
    success = total_tables > 0
    print(f"RESULT: {'✓ TABLES FOUND' if success else '○ NO TABLES FOUND'}")
    print("█" * 80 + "\n")

    return success


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
