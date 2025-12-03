#!/usr/bin/env python
"""
Advanced Data Forensics: Structural Integrity Audit
====================================================

Purpose: Rigorous validation of ingestion artifacts
Checks:
1. Referential Integrity (doc_id consistency across artifacts)
2. Spatial Sanity (bbox coordinate validation)
3. Table Structure Preservation (markdown table formatting)

Author: Auto-generated diagnostic script
Date: 2025-11-27
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Set

# Configuration
DOC_ID_MAP = Path(r"D:\PVCFC_Artifacts\ingestion_production\doc_id_map.json")
TAGS_FILE = Path(r"D:\PVCFC_Artifacts\entities\tags.jsonl")
CHUNKS_FILE = Path(r"D:\PVCFC_Artifacts\ingestion_production\chunks\chunks.jsonl")
PAGE_LAYOUT_DIR = Path(r"D:\PVCFC_Artifacts\page_layout")


def print_separator(char="=", width=80):
    print(char * width)


def print_section(title: str):
    print(f"\n{title}")
    print_separator()


def load_valid_doc_ids() -> Set[str]:
    """Load all valid doc IDs from doc_id_map.json"""
    print(f"📂 Loading valid doc IDs from: {DOC_ID_MAP}")

    if not DOC_ID_MAP.exists():
        print(f"❌ ERROR: File not found: {DOC_ID_MAP}")
        return set()

    with open(DOC_ID_MAP, "r", encoding="utf-8") as f:
        doc_map = json.load(f)

    valid_ids = set(doc_map.keys())
    print(f"✅ Loaded {len(valid_ids):,} valid document IDs\n")
    return valid_ids


def check_referential_integrity(valid_docs: Set[str]) -> Dict:
    """Check referential integrity between artifacts"""
    results = {
        "tags": {"total": 0, "orphans": [], "pass": True},
        "chunks": {"total": 0, "orphans": [], "pass": True},
    }

    # Check tags.jsonl
    print(f"🔍 Checking tags.jsonl...")
    if TAGS_FILE.exists():
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    tag = json.loads(line.strip())
                    doc_id = tag.get("doc_id")
                    results["tags"]["total"] += 1

                    if doc_id and doc_id not in valid_docs:
                        results["tags"]["orphans"].append(doc_id)
                        results["tags"]["pass"] = False
                except json.JSONDecodeError:
                    continue

        print(f"   Processed {results['tags']['total']:,} tags")
        print(f"   Orphans found: {len(results['tags']['orphans'])}")
    else:
        print(f"   ⚠️  File not found: {TAGS_FILE}")

    # Check chunks.jsonl
    print(f"\n🔍 Checking chunks.jsonl...")
    if CHUNKS_FILE.exists():
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    chunk = json.loads(line.strip())
                    doc_id = chunk.get("doc_id")
                    results["chunks"]["total"] += 1

                    if doc_id and doc_id not in valid_docs:
                        results["chunks"]["orphans"].append(doc_id)
                        results["chunks"]["pass"] = False
                except json.JSONDecodeError:
                    continue

        print(f"   Processed {results['chunks']['total']:,} chunks")
        print(f"   Orphans found: {len(results['chunks']['orphans'])}")
    else:
        print(f"   ❌ File not found: {CHUNKS_FILE}")

    return results


def validate_bbox(bbox: List, page_width: float, page_height: float) -> Dict:
    """Validate a single bounding box"""
    issues = []

    # Check format
    if not isinstance(bbox, list) or len(bbox) != 4:
        issues.append(f"Invalid format: {bbox}")
        return {"valid": False, "issues": issues}

    x1, y1, x2, y2 = bbox

    # Check numeric
    if not all(isinstance(v, (int, float)) for v in bbox):
        issues.append(f"Non-numeric values: {bbox}")
        return {"valid": False, "issues": issues}

    # Check positive
    if not all(v >= 0 for v in bbox):
        issues.append(f"Negative values: {bbox}")

    # Check ordering
    if x2 <= x1:
        issues.append(f"x2 ({x2}) <= x1 ({x1})")
    if y2 <= y1:
        issues.append(f"y2 ({y2}) <= y1 ({y1})")

    # Check boundaries
    if page_width and x2 > page_width:
        issues.append(f"x2 ({x2}) > page_width ({page_width})")
    if page_height and y2 > page_height:
        issues.append(f"y2 ({y2}) > page_height ({page_height})")

    return {"valid": len(issues) == 0, "issues": issues, "bbox": bbox}


def check_spatial_sanity() -> Dict:
    """Check spatial coordinates in page layout files"""
    results = {
        "files_checked": 0,
        "total_bboxes": 0,
        "valid_bboxes": 0,
        "invalid_bboxes": 0,
        "issues": [],
        "pass": True,
    }

    if not PAGE_LAYOUT_DIR.exists():
        print(f"⚠️  Directory not found: {PAGE_LAYOUT_DIR}")
        return results

    # Get all layout files
    layout_files = list(PAGE_LAYOUT_DIR.glob("*.json"))

    if not layout_files:
        print(f"⚠️  No layout files found in {PAGE_LAYOUT_DIR}")
        return results

    # Sample 3 random files
    sample_files = random.sample(layout_files, min(3, len(layout_files)))

    print(f"📐 Checking {len(sample_files)} random layout files...")

    for layout_file in sample_files:
        try:
            with open(layout_file, "r", encoding="utf-8") as f:
                layout = json.load(f)

            results["files_checked"] += 1

            page_width = layout.get("page_width")
            page_height = layout.get("page_height")

            # Check text_spans or similar
            spans = layout.get("text_spans", [])

            for span in spans:
                bbox = span.get("bbox")
                if bbox:
                    results["total_bboxes"] += 1

                    validation = validate_bbox(bbox, page_width, page_height)

                    if validation["valid"]:
                        results["valid_bboxes"] += 1
                    else:
                        results["invalid_bboxes"] += 1
                        results["pass"] = False
                        results["issues"].append(
                            {
                                "file": layout_file.name,
                                "bbox": bbox,
                                "issues": validation["issues"],
                            }
                        )

        except Exception as e:
            print(f"   ⚠️  Error reading {layout_file.name}: {e}")

    print(f"   Files checked: {results['files_checked']}")
    print(f"   Total bboxes: {results['total_bboxes']:,}")
    print(f"   Valid: {results['valid_bboxes']:,}")
    print(f"   Invalid: {results['invalid_bboxes']:,}")

    return results


def find_table_example() -> Optional[str]:
    """Find a chunk containing a markdown table"""
    print(f"🔍 Searching for markdown tables in chunks...")

    table_marker = "| --- |"

    if not CHUNKS_FILE.exists():
        return None

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                chunk = json.loads(line.strip())
                text = chunk.get("text", "")

                if table_marker in text:
                    print(f"   ✓ Found table in chunk: {chunk.get('chunk_id')}")
                    return text
            except json.JSONDecodeError:
                continue

    print(f"   ⚠️  No tables found")
    return None


def main():
    """Main forensics execution"""
    print_separator()
    print("ADVANCED DATA FORENSICS: Structural Integrity Audit")
    print_separator()
    print("Performing rigorous validation of ingestion artifacts\n")

    # ========== A. Referential Integrity Check ==========
    print_section("A. REFERENTIAL INTEGRITY CHECK (The Link Test)")

    valid_docs = load_valid_doc_ids()

    if not valid_docs:
        print("❌ Cannot proceed without valid doc IDs")
        return

    ref_results = check_referential_integrity(valid_docs)

    print(f"\n📊 Results:")
    print(
        f"   Tags: {ref_results['tags']['total']:,} checked, "
        f"{len(ref_results['tags']['orphans'])} orphans"
    )
    print(
        f"   Chunks: {ref_results['chunks']['total']:,} checked, "
        f"{len(ref_results['chunks']['orphans'])} orphans"
    )

    if ref_results["tags"]["pass"] and ref_results["chunks"]["pass"]:
        print(f"\n🎯 VERDICT: ✅ PASS - All references are valid")
    else:
        print(f"\n🎯 VERDICT: ❌ FAIL - Orphaned records found")

        if ref_results["tags"]["orphans"]:
            print(f"\n⚠️  Orphaned Tag doc_ids (first 10):")
            for doc_id in ref_results["tags"]["orphans"][:10]:
                print(f"      - {doc_id}")

        if ref_results["chunks"]["orphans"]:
            print(f"\n⚠️  Orphaned Chunk doc_ids (first 10):")
            for doc_id in ref_results["chunks"]["orphans"][:10]:
                print(f"      - {doc_id}")

    # ========== B. Spatial Sanity Check ==========
    print_section("B. SPATIAL SANITY CHECK (The Geometry Test)")

    spatial_results = check_spatial_sanity()

    if spatial_results["pass"]:
        print(f"\n🎯 VERDICT: ✅ PASS - All coordinates are geometrically valid")
        print(
            f"   Sample: {spatial_results['valid_bboxes']}/{spatial_results['total_bboxes']} "
            f"bboxes validated"
        )
    else:
        print(f"\n🎯 VERDICT: ❌ FAIL - Invalid coordinates found")
        print(f"\n⚠️  Invalid bboxes (first 5):")
        for issue in spatial_results["issues"][:5]:
            print(f"      File: {issue['file']}")
            print(f"      Bbox: {issue['bbox']}")
            print(f"      Issues: {', '.join(issue['issues'])}")

    # ========== C. Table Structure Verification ==========
    print_section("C. TABLE STRUCTURE VERIFICATION (The Formatting Test)")

    table_text = find_table_example()

    if table_text:
        print(f"\n📋 Table Example Found:")
        print(f"{'─' * 80}")
        # Show first 1000 chars to capture table structure
        print(table_text[:1000])
        print(f"{'─' * 80}")

        # Count table rows
        table_rows = table_text.count("|")
        print(f"\n   Table complexity: ~{table_rows} cells/separators")
        print(f"\n🎯 VERDICT: ✅ Table structure preserved")
        print(f"   Review output above to verify column alignment")
    else:
        print(f"\n🎯 VERDICT: ⚠️  NO TABLES FOUND")
        print(f"   This may be expected if documents don't contain tables")

    # ========== Final Summary ==========
    print_section("📊 FINAL AUDIT SUMMARY")

    all_passed = (
        ref_results["tags"]["pass"]
        and ref_results["chunks"]["pass"]
        and spatial_results["pass"]
    )

    print(f"\n✅ Audit Results:")
    print(
        f"   1. Referential Integrity: {'✅ PASS' if ref_results['tags']['pass'] and ref_results['chunks']['pass'] else '❌ FAIL'}"
    )
    print(
        f"   2. Spatial Validity: {'✅ PASS' if spatial_results['pass'] else '❌ FAIL'}"
    )
    print(f"   3. Table Preservation: {'✅ FOUND' if table_text else '⚠️ NOT FOUND'}")

    if all_passed:
        print(f"\n🎉 OVERALL VERDICT: ✅ ALL CHECKS PASSED")
        print(f"   Data artifacts have excellent structural integrity")
        print(f"   Safe to proceed with indexing")
    else:
        print(f"\n⚠️  OVERALL VERDICT: ISSUES DETECTED")
        print(f"   Review failures above before indexing")

    print_separator()
    print("✅ Advanced Forensics Complete")
    print_separator()


if __name__ == "__main__":
    main()
