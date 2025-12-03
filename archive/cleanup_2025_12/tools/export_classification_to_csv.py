#!/usr/bin/env python
"""
Export Classification Results to CSV
=====================================

Converts document_types_12.jsonl to CSV format for easy viewing/analysis
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.classification.document_type_12 import get_doc_type_display_name
from tools.extract_metadata import extract_equipment_id, extract_vendor


def export_to_csv(
    jsonl_path: Path,
    csv_path: Path,
):
    """
    Export JSONL classification results to CSV

    Args:
        jsonl_path: Path to document_types_12.jsonl
        csv_path: Path to output CSV file
    """
    print(f"Reading from: {jsonl_path}")

    # Read JSONL
    results = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                result = json.loads(line)
                results.append(result)

    print(f"Loaded {len(results)} classification results")

    # Prepare CSV data with enriched fields
    csv_data = []
    for result in results:
        pdf_path = result.get("pdf_path", "")
        filename = Path(pdf_path).name if pdf_path else ""

        # Extract metadata from path
        equipment_id = extract_equipment_id(pdf_path) if pdf_path else ""
        vendor = extract_vendor(pdf_path) if pdf_path else ""

        # Get display name
        doc_type_code = result.get("doc_type_12", "")
        doc_type_display = get_doc_type_display_name(doc_type_code)

        # Get parent and sub-category
        parent_category = result.get("parent_category", "")
        sub_category = result.get("sub_category", "")

        row = {
            "doc_id": result.get("doc_id", ""),
            "filename": filename,
            "parent_category": parent_category,
            "sub_category": sub_category or "",
            "doc_type_code": doc_type_code,
            "doc_type_name": doc_type_display,
            "confidence": result.get("confidence", 0.0),
            "method": result.get("method", ""),
            "equipment_id": equipment_id or "",
            "vendor": vendor or "",
            "pdf_path": pdf_path,
            "reasoning": result.get("reasoning", ""),
            "timestamp": result.get("timestamp", ""),
        }
        csv_data.append(row)

    # Write CSV
    print(f"Writing to: {csv_path}")

    fieldnames = [
        "doc_id",
        "filename",
        "parent_category",
        "sub_category",
        "doc_type_code",
        "doc_type_name",
        "confidence",
        "method",
        "equipment_id",
        "vendor",
        "pdf_path",
        "reasoning",
        "timestamp",
    ]

    with open(
        csv_path, "w", newline="", encoding="utf-8-sig"
    ) as f:  # utf-8-sig for Excel compatibility
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"✅ Exported {len(csv_data)} rows to CSV")

    # Print summary statistics
    print("\n" + "=" * 80)
    print("Classification Summary:")
    print("=" * 80)

    # Count by document type
    from collections import Counter

    type_counts = Counter(row["doc_type_name"] for row in csv_data)

    for doc_type, count in sorted(
        type_counts.items(), key=lambda x: x[1], reverse=True
    ):
        percentage = (count / len(csv_data) * 100) if csv_data else 0
        print(f"{doc_type:30s} : {count:3d} ({percentage:5.1f}%)")

    print("\n" + "=" * 80)
    print(f"Total: {len(csv_data)} documents")
    print("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Export classification results to CSV")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("artifacts/classification/document_types_12.jsonl"),
        help="Input JSONL file (default: artifacts/classification/document_types_12.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/classification/document_types_12.csv"),
        help="Output CSV file (default: artifacts/classification/document_types_12.csv)",
    )

    args = parser.parse_args()

    # Check input file exists
    if not args.input.exists():
        print(f"❌ Error: Input file not found: {args.input}")
        sys.exit(1)

    # Export
    export_to_csv(args.input, args.output)

    print(f"\n✅ Success! CSV file saved to: {args.output}")
    print(f"   You can open it in Excel or any spreadsheet application.")


if __name__ == "__main__":
    main()
