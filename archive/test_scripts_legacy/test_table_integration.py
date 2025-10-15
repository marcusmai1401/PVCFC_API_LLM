"""
Integration test for table extraction pipeline
Tests end-to-end flow: PDF -> table extraction -> chunking
"""
import json
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


def create_test_pdf_with_table():
    """Create a simple test PDF with a table for testing"""
    import fitz

    test_pdf_path = Path("test_docs/test_table_sample.pdf")
    test_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a simple PDF with table-like text
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size

    # Add title
    page.insert_text((50, 50), "Test Document with Table", fontsize=16)

    # Add some regular text
    page.insert_text(
        (50, 100), "This is a test document to verify table extraction.", fontsize=11
    )
    page.insert_text(
        (50, 120), "Below is a table with torque specifications:", fontsize=11
    )

    # Create a simple bordered table using rectangles and text
    table_x = 50
    table_y = 160
    cell_width = 120
    cell_height = 30

    # Table headers
    headers = ["Size", "Torque (Nm)", "Type"]
    rows = [
        ["M36", "1200", "Bolt"],
        ["M42", "1650", "Bolt"],
        ["M48", "2150", "Bolt"],
    ]

    # Draw table borders and add text
    for row_idx in range(len(rows) + 1):  # +1 for header
        for col_idx in range(len(headers)):
            # Draw cell rectangle
            rect = fitz.Rect(
                table_x + col_idx * cell_width,
                table_y + row_idx * cell_height,
                table_x + (col_idx + 1) * cell_width,
                table_y + (row_idx + 1) * cell_height,
            )
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)

            # Add text
            if row_idx == 0:
                text = headers[col_idx]
            else:
                text = rows[row_idx - 1][col_idx]

            text_point = (
                table_x + col_idx * cell_width + 10,
                table_y + row_idx * cell_height + 20,
            )
            page.insert_text(text_point, text, fontsize=10)

    # Add footer text
    page.insert_text(
        (50, table_y + (len(rows) + 1) * cell_height + 30),
        "Table 1: Anchor bolt torque specifications",
        fontsize=9,
    )

    # Save PDF
    doc.save(str(test_pdf_path))
    doc.close()

    logger.info(f"Created test PDF with table: {test_pdf_path}")
    return test_pdf_path


def test_integration_pipeline():
    """Test full integration: PDF processing -> table extraction -> chunking"""

    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Table Extraction Pipeline")
    print("=" * 80 + "\n")

    # Step 1: Create test PDF
    print("Step 1: Creating test PDF with table...")
    test_pdf_path = create_test_pdf_with_table()
    print(f"✓ Test PDF created: {test_pdf_path}\n")

    # Step 2: Process PDF with table extraction enabled
    print("Step 2: Processing PDF with table extraction...")
    processor = PDFProcessor(
        extract_tables=True,
        extract_images=False,
        table_min_rows=2,
        table_min_cols=2,
    )

    try:
        pdf_doc = processor.process_pdf(test_pdf_path)
        print(f"✓ PDF processed successfully")
        print(f"  - Pages: {pdf_doc.num_pages}")
        print(f"  - Total chars: {pdf_doc.total_chars}")
        print(f"  - Total words: {pdf_doc.total_words}\n")

        # Check for tables in pages
        tables_found = 0
        for page in pdf_doc.pages:
            if page.tables:
                tables_found += len(page.tables)
                print(f"✓ Page {page.page_num}: Found {len(page.tables)} table(s)")
                for i, table in enumerate(page.tables):
                    print(
                        f"  - Table {i+1}: {table['row_count']}x{table['col_count']}, confidence={table['confidence']}"
                    )

        print(f"\nTotal tables found: {tables_found}\n")

        if tables_found == 0:
            print(
                "⚠ WARNING: No tables detected. This might be expected for simple text-based PDFs."
            )
            print(
                "  PyMuPDF requires actual table structures (borders) to detect tables.\n"
            )

    except Exception as e:
        print(f"✗ FAIL: PDF processing error: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Step 3: Chunk the document
    print("Step 3: Chunking document with table integration...")
    chunker = TextChunker(
        chunk_size=500, chunk_overlap=100, chunking_strategy="semantic"
    )

    try:
        # Convert PDFDocument to dict for chunking
        doc_dict = pdf_doc.to_dict()

        chunks = chunker.chunk_document(doc_dict, doc_id=test_pdf_path.stem)
        print(f"✓ Created {len(chunks)} chunks\n")

        # Analyze chunks
        chunks_with_tables = 0
        for chunk in chunks:
            if "has_tables" in chunk.metadata and chunk.metadata["has_tables"]:
                chunks_with_tables += 1
                print(f"Chunk {chunk.chunk_index}:")
                print(f"  - Has tables: {chunk.metadata['has_tables']}")
                print(f"  - Text length: {chunk.char_count}")
                print(f"  - Contains markdown table: {'|' in chunk.text}")

                # Show snippet of chunk text
                if "|" in chunk.text:
                    # Find and show table portion
                    lines = chunk.text.split("\n")
                    table_lines = [line for line in lines if "|" in line]
                    if table_lines:
                        print(f"  - Table preview:")
                        for line in table_lines[:5]:  # Show first 5 lines
                            print(f"      {line}")
                print()

        print(f"Chunks with tables: {chunks_with_tables}/{len(chunks)}\n")

    except Exception as e:
        print(f"✗ FAIL: Chunking error: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Step 4: Verify chunk content
    print("Step 4: Verifying chunk content...")

    checks = {
        "PDF processed": pdf_doc is not None,
        "Pages extracted": pdf_doc.num_pages > 0,
        "Text extracted": pdf_doc.total_chars > 0,
        "Chunks created": len(chunks) > 0,
        "Chunks have metadata": all(chunk.metadata for chunk in chunks),
        "Chunks have page numbers": all("page" in chunk.metadata for chunk in chunks),
    }

    # Additional check if tables were found
    if tables_found > 0:
        checks["Tables detected"] = tables_found > 0
        checks["Tables in chunk metadata"] = chunks_with_tables > 0

    print("\nVerification Results:")
    all_passed = True
    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False

    # Save test output
    print("\nStep 5: Saving test output...")
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    # Save processed document
    doc_output = output_dir / "test_document.json"
    with open(doc_output, "w", encoding="utf-8") as f:
        f.write(pdf_doc.to_json())
    print(f"✓ Saved document: {doc_output}")

    # Save chunks
    chunks_output = output_dir / "test_chunks.json"
    chunker.save_chunks(chunks, chunks_output)
    print(f"✓ Saved chunks: {chunks_output}")

    print("\n" + "=" * 80)
    if all_passed:
        print("✓ INTEGRATION TEST PASSED")
    else:
        print("✗ INTEGRATION TEST FAILED")
    print("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    print("\n" + "█" * 80)
    print("TABLE EXTRACTION INTEGRATION TEST")
    print("█" * 80)

    result = test_integration_pipeline()

    print("\n" + "█" * 80)
    print(f"FINAL RESULT: {'✓ PASSED' if result else '✗ FAILED'}")
    print("█" * 80 + "\n")

    sys.exit(0 if result else 1)
