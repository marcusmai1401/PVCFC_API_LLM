"""
Diagnostic script to analyze page count mismatches between doc_id_map and actual PDFs
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    import pymupdf as fitz


def get_pdf_page_count(pdf_path: str) -> int:
    """Get actual page count from PDF file"""
    try:
        with fitz.open(pdf_path) as doc:
            return doc.page_count
    except Exception as e:
        return -1


def analyze_doc_id_map():
    """Analyze doc_id_map.json and compare with actual PDF files"""

    # Load doc_id_map
    doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
    if not doc_id_map_path.exists():
        print(f"ERROR: {doc_id_map_path} not found")
        return

    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print(f"Loaded doc_id_map with {len(doc_id_map)} entries")
    print("=" * 100)

    # Track statistics
    total_docs = len(doc_id_map)
    missing_pdfs = 0
    page_mismatches = []
    valid_docs = 0

    # Analyze each document
    for doc_id, doc_info in doc_id_map.items():
        if not isinstance(doc_info, dict):
            continue

        pdf_path = doc_info.get("pdf_path")
        expected_pages = doc_info.get("total_pages", 0)
        file_name = doc_info.get("file_name", "unknown")

        if not pdf_path:
            print(f"⚠ {doc_id}: No pdf_path in metadata")
            continue

        # Check if PDF exists
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            missing_pdfs += 1
            print(f"❌ MISSING: {file_name}")
            print(f"   Path: {pdf_path}")
            print(f"   Expected pages: {expected_pages}")
            print()
            continue

        # Get actual page count
        actual_pages = get_pdf_page_count(pdf_path)

        if actual_pages < 0:
            print(f"⚠ ERROR reading: {file_name}")
            print(f"   Path: {pdf_path}")
            print()
            continue

        # Compare page counts
        if actual_pages != expected_pages:
            mismatch_info = {
                "doc_id": doc_id,
                "file_name": file_name,
                "pdf_path": pdf_path,
                "expected_pages": expected_pages,
                "actual_pages": actual_pages,
                "difference": actual_pages - expected_pages,
            }
            page_mismatches.append(mismatch_info)

            print(f"🔴 MISMATCH: {file_name}")
            print(f"   Doc ID: {doc_id[:60]}...")
            print(f"   Expected pages: {expected_pages}")
            print(f"   Actual pages: {actual_pages}")
            print(f"   Difference: {actual_pages - expected_pages:+d}")
            print()
        else:
            valid_docs += 1

    # Print summary
    print("=" * 100)
    print("SUMMARY:")
    print(f"  Total documents: {total_docs}")
    print(f"  Valid documents: {valid_docs}")
    print(f"  Missing PDFs: {missing_pdfs}")
    print(f"  Page count mismatches: {len(page_mismatches)}")
    print()

    if page_mismatches:
        print("=" * 100)
        print("DETAILED MISMATCH REPORT:")
        print()
        for i, mismatch in enumerate(page_mismatches, 1):
            print(f"{i}. {mismatch['file_name']}")
            print(f"   Doc ID: {mismatch['doc_id'][:60]}...")
            print(f"   Expected: {mismatch['expected_pages']} pages")
            print(f"   Actual:   {mismatch['actual_pages']} pages")
            print(f"   Diff:     {mismatch['difference']:+d} pages")
            print()

    # Save mismatch report
    if page_mismatches:
        report_file = Path("artifacts/page_mismatch_report.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": "2025-10-09T09:43:17Z",
                    "summary": {
                        "total_docs": total_docs,
                        "valid_docs": valid_docs,
                        "missing_pdfs": missing_pdfs,
                        "page_mismatches": len(page_mismatches),
                    },
                    "mismatches": page_mismatches,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"✅ Mismatch report saved to: {report_file}")

    return page_mismatches, missing_pdfs


if __name__ == "__main__":
    print("PDF Page Count Diagnostic Tool")
    print("=" * 100)
    print()

    try:
        mismatches, missing = analyze_doc_id_map()

        if not mismatches and missing == 0:
            print("✅ All documents have correct page counts!")
            sys.exit(0)
        else:
            print(
                f"⚠ Found {len(mismatches) if mismatches else 0} page mismatches and {missing} missing PDFs"
            )
            sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(2)
