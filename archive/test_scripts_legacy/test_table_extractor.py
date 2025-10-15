"""
Test script for TableExtractor module
Validates table extraction on page 15 of Installation Instruction PDF
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import fitz
from loguru import logger

from app.ingestion.table_extractor import TableData, TableExtractor

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_table_extractor_page15():
    """Test table extraction on page 15 (torque table)"""

    print("\n" + "=" * 80)
    print("TEST: Table Extractor - Page 15 Torque Table")
    print("=" * 80 + "\n")

    # Define paths - use available PDF with tables
    pdf_path = Path(
        "data/raw/phase1_pilot/092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf"
    )

    if not pdf_path.exists():
        print(f"❌ ERROR: PDF not found at {pdf_path}")
        print("Trying alternative paths...")
        # Try other PDFs
        alternatives = [
            Path(
                "data/raw/phase1_pilot/003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"
            ),
            Path("data/raw/samples/sample_datasheet.pdf"),
        ]
        for alt in alternatives:
            if alt.exists():
                pdf_path = alt
                print(f"✓ Using: {pdf_path}")
                break
        else:
            print("❌ No PDF found")
            return False

    print(f"📄 PDF: {pdf_path.name}")
    print(f"📍 Testing: First page with tables\n")

    try:
        # Initialize table extractor
        print("Initializing TableExtractor...")
        extractor = TableExtractor(
            min_rows=2,
            min_cols=2,
            snap_tolerance=3.0,
            join_tolerance=3.0,
        )
        print("✓ TableExtractor initialized\n")

        # Open PDF and scan for first page with tables
        doc = fitz.open(str(pdf_path))

        print(f"Scanning document for tables ({len(doc)} pages)...")

        tables = []
        test_page_num = None

        # Scan first 20 pages for tables
        for page_idx in range(min(20, len(doc))):
            page = doc[page_idx]
            page_tables = extractor.extract_tables_from_page(
                page, page_num=page_idx + 1
            )
            if page_tables:
                tables = page_tables
                test_page_num = page_idx + 1
                print(f"✓ Found {len(tables)} table(s) on page {test_page_num}")
                break

        if not test_page_num:
            print(f"❌ No tables found in first 20 pages")
            doc.close()
            return False

        page = doc[test_page_num - 1]
        print(f"Page dimensions: {page.rect.width} x {page.rect.height}\n")

        print(f"✓ Found {len(tables)} table(s)\n")

        if not tables:
            print("❌ FAIL: No tables detected on page 15")
            doc.close()
            return False

        # Analyze each table
        for i, table in enumerate(tables):
            print(f"\n{'─'*80}")
            print(f"TABLE {i+1} DETAILS")
            print(f"{'─'*80}")

            print(f"Page Number: {table.page_num}")
            print(f"Table Index: {table.table_index}")
            print(f"Dimensions: {table.row_count} rows × {table.col_count} columns")
            print(f"Bounding Box: {table.bbox}")
            print(f"Confidence: {table.confidence}")

            # Display cells
            print(f"\nCell Data ({len(table.cells)} rows):")
            for row_idx, row in enumerate(table.cells):
                print(f"  Row {row_idx}: {row}")

            # Display markdown
            print(f"\nMarkdown Representation:")
            print("┌" + "─" * 78 + "┐")
            for line in table.markdown.split("\n"):
                print(f"│ {line:<76} │")
            print("└" + "─" * 78 + "┘")

            # Verify key data points
            print(f"\n{'─'*80}")
            print("VERIFICATION: Table Content Sample")
            print(f"{'─'*80}")

            # Check for content characteristics
            has_numeric_data = False
            has_header_row = False

            for row_idx, row in enumerate(table.cells):
                row_text = " ".join(row).lower()

                # Check first row looks like header
                if row_idx == 0 and any(cell.strip() for cell in row):
                    has_header_row = True
                    print(f"✓ Header row: {row}")

                # Check for numeric content
                if any(char.isdigit() for char in row_text):
                    has_numeric_data = True
                    if row_idx <= 3 and row_idx > 0:  # Show first few data rows
                        print(f"✓ Data row {row_idx}: {row}")

            # Final validation
            print(f"\n{'─'*80}")
            print("TEST RESULTS")
            print(f"{'─'*80}")

            checks = {
                "Table detected": len(tables) > 0,
                "Minimum rows (≥2)": table.row_count >= 2,
                "Minimum cols (≥2)": table.col_count >= 2,
                "Has content": table.confidence > 0,
                "Has header row": has_header_row,
                "Has numeric data": has_numeric_data,
                "Markdown generated": bool(table.markdown),
                "Confidence > 0.3": table.confidence > 0.3,
            }

            all_passed = True
            for check_name, result in checks.items():
                status = "✓ PASS" if result else "✗ FAIL"
                print(f"{status}: {check_name}")
                if not result:
                    all_passed = False

            # Test formatted output for chunks
            print(f"\n{'─'*80}")
            print("FORMATTED OUTPUT FOR CHUNKS")
            print(f"{'─'*80}")

            formatted = extractor.format_table_for_chunk(table)
            print(formatted)

            doc.close()

            print(f"\n{'='*80}")
            if all_passed:
                print("✓ ALL TESTS PASSED")
            else:
                print("✗ SOME TESTS FAILED")
            print(f"{'='*80}\n")

            return all_passed

    except Exception as e:
        print(f"\n❌ ERROR during test: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_full_document_extraction():
    """Test extracting tables from entire document"""

    print("\n" + "=" * 80)
    print("TEST: Full Document Table Extraction")
    print("=" * 80 + "\n")

    pdf_path = Path(
        "data/raw/phase1_pilot/092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf"
    )

    if not pdf_path.exists():
        print(f"❌ ERROR: PDF not found at {pdf_path}")
        print("Trying alternative...")
        pdf_path = Path(
            "data/raw/phase1_pilot/003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf"
        )
        if not pdf_path.exists():
            print("❌ No PDF found for full document test")
            return False
        print(f"✓ Using: {pdf_path.name}")

    try:
        extractor = TableExtractor()

        print(f"Extracting tables from entire document: {pdf_path.name}")
        all_tables = extractor.extract_tables_from_document(str(pdf_path))

        print(f"\n✓ Extraction complete")
        print(f"Total pages with tables: {len(all_tables)}")

        total_tables = sum(len(tables) for tables in all_tables.values())
        print(f"Total tables found: {total_tables}\n")

        # Summary by page
        print("Tables by page:")
        for page_num in sorted(all_tables.keys()):
            tables = all_tables[page_num]
            print(f"  Page {page_num}: {len(tables)} table(s)")
            for table in tables:
                print(
                    f"    - {table.row_count}×{table.col_count}, confidence={table.confidence}"
                )

        print(f"\n{'='*80}")
        print("✓ FULL DOCUMENT TEST COMPLETE")
        print(f"{'='*80}\n")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "█" * 80)
    print("TABLE EXTRACTOR VALIDATION SUITE")
    print("█" * 80)

    # Test 1: Page 15 specific test
    test1_result = test_table_extractor_page15()

    # Test 2: Full document test
    test2_result = test_full_document_extraction()

    # Final summary
    print("\n" + "█" * 80)
    print("FINAL SUMMARY")
    print("█" * 80)
    print(f"Test 1 (Page 15): {'✓ PASSED' if test1_result else '✗ FAILED'}")
    print(f"Test 2 (Full Doc): {'✓ PASSED' if test2_result else '✗ FAILED'}")
    print("█" * 80 + "\n")

    # Exit with appropriate code
    sys.exit(0 if (test1_result and test2_result) else 1)
