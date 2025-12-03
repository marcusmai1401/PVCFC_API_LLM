#!/usr/bin/env python
"""
Deep Verification: Spatial Data (BBox) Integrity
=================================================

Purpose: Verify if valid bounding boxes exist in layout files and extracted tags
Context: Previous sampling found 0 bboxes - need to verify if this is data loss

Author: Auto-generated diagnostic script
Date: 2025-11-27
"""

import json
import random
from pathlib import Path
from typing import Dict, List

# Configuration
PAGE_LAYOUT_DIR = Path(r"D:\PVCFC_Artifacts\page_layout")
TAGS_FILE = Path(r"D:\PVCFC_Artifacts\entities\tags.jsonl")


def print_separator(char="=", width=80):
    print(char * width)


def analyze_layout_files(sample_size: int = 50) -> Dict:
    """Analyze layout files for bbox content"""
    print(f"📂 Analyzing layout files in: {PAGE_LAYOUT_DIR}\n")

    if not PAGE_LAYOUT_DIR.exists():
        print(f"❌ Directory not found: {PAGE_LAYOUT_DIR}")
        return {}

    # Get all layout files
    layout_files = list(PAGE_LAYOUT_DIR.glob("*.json"))
    print(f"✅ Found {len(layout_files)} layout files\n")

    if not layout_files:
        return {"total_files": 0, "files_checked": 0}

    # Sample files
    sample_files = random.sample(layout_files, min(sample_size, len(layout_files)))

    results = {
        "total_files": len(layout_files),
        "files_checked": len(sample_files),
        "files_with_spans": 0,
        "files_with_drawings": 0,
        "files_with_bboxes": 0,
        "empty_files": [],
        "total_spans": 0,
        "total_drawings": 0,
        "total_bboxes": 0,
        "example_layouts": [],
    }

    print(f"🔍 Checking {len(sample_files)} random layout files...")

    for layout_file in sample_files:
        try:
            with open(layout_file, "r", encoding="utf-8") as f:
                layout = json.load(f)

            # Check different possible keys
            spans = layout.get("text_spans", [])
            drawings = layout.get("drawings", [])

            # Alternative keys
            if not spans:
                spans = layout.get("spans", [])
            if not spans:
                spans = layout.get("text_blocks", [])

            has_content = False
            bbox_count = 0

            # Count spans
            if spans:
                results["files_with_spans"] += 1
                results["total_spans"] += len(spans)
                has_content = True

                # Count bboxes in spans
                for span in spans:
                    if (
                        "bbox" in span
                        and isinstance(span["bbox"], list)
                        and len(span["bbox"]) == 4
                    ):
                        bbox_count += 1

            # Count drawings
            if drawings:
                results["files_with_drawings"] += 1
                results["total_drawings"] += len(drawings)
                has_content = True

            if bbox_count > 0:
                results["files_with_bboxes"] += 1
                results["total_bboxes"] += bbox_count

            if not has_content:
                results["empty_files"].append(layout_file.name)

            # Save first example with content
            if has_content and len(results["example_layouts"]) < 3:
                results["example_layouts"].append(
                    {
                        "file": layout_file.name,
                        "spans": len(spans),
                        "drawings": len(drawings),
                        "bboxes": bbox_count,
                        "sample_span": spans[0] if spans else None,
                    }
                )

        except Exception as e:
            print(f"   ⚠️  Error reading {layout_file.name}: {e}")

    return results


def analyze_tag_bboxes(num_examples: int = 20) -> Dict:
    """Analyze bboxes in extracted tags"""
    print(f"\n📂 Analyzing tags in: {TAGS_FILE}\n")

    if not TAGS_FILE.exists():
        print(f"❌ File not found: {TAGS_FILE}")
        return {}

    results = {
        "total_tags": 0,
        "tags_with_bbox": 0,
        "tags_with_valid_bbox": 0,
        "examples": [],
    }

    with open(TAGS_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= num_examples:
                break

            try:
                tag = json.loads(line.strip())
                results["total_tags"] += 1

                bbox = tag.get("bbox")

                if bbox is not None:
                    results["tags_with_bbox"] += 1

                    # Validate bbox
                    is_valid = (
                        isinstance(bbox, list)
                        and len(bbox) == 4
                        and all(isinstance(v, (int, float)) for v in bbox)
                        and all(v >= 0 for v in bbox)
                        and bbox[2] > bbox[0]
                        and bbox[3] > bbox[1]
                    )

                    if is_valid:
                        results["tags_with_valid_bbox"] += 1

                    # Save examples
                    if len(results["examples"]) < 3:
                        results["examples"].append(
                            {
                                "tag": tag.get("tag"),
                                "bbox": bbox,
                                "page": tag.get("page"),
                                "confidence": tag.get("confidence"),
                                "valid": is_valid,
                            }
                        )

            except json.JSONDecodeError:
                continue

    # Count remaining tags
    with open(TAGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            results["total_tags"] += 1

    return results


def main():
    """Main verification execution"""
    print_separator()
    print("DEEP VERIFICATION: Spatial Data (BBox) Integrity")
    print_separator()
    print("Investigating if bounding boxes exist in layout files and tags\n")

    # ========== A. Layout File Analysis ==========
    print_separator("=")
    print("A. LAYOUT FILES ANALYSIS (The Input)")
    print_separator("=")

    layout_results = analyze_layout_files(sample_size=50)

    if layout_results:
        print(f"\n📊 Layout File Statistics:")
        print(f"   Total layout files: {layout_results['total_files']:,}")
        print(f"   Files checked: {layout_results['files_checked']}")
        print(
            f"   Files with spans: {layout_results['files_with_spans']} "
            f"({100*layout_results['files_with_spans']/max(1,layout_results['files_checked']):.1f}%)"
        )
        print(
            f"   Files with drawings: {layout_results['files_with_drawings']} "
            f"({100*layout_results['files_with_drawings']/max(1,layout_results['files_checked']):.1f}%)"
        )
        print(
            f"   Files with bboxes: {layout_results['files_with_bboxes']} "
            f"({100*layout_results['files_with_bboxes']/max(1,layout_results['files_checked']):.1f}%)"
        )

        print(f"\n📈 Content Statistics:")
        print(f"   Total spans: {layout_results['total_spans']:,}")
        print(f"   Total drawings: {layout_results['total_drawings']:,}")
        print(f"   Total bboxes: {layout_results['total_bboxes']:,}")

        if layout_results["files_checked"] > 0:
            avg_spans = layout_results["total_spans"] / layout_results["files_checked"]
            print(f"   Average spans per file: {avg_spans:.1f}")

        # Empty files warning
        if layout_results["empty_files"]:
            print(f"\n⚠️  Empty Layout Files ({len(layout_results['empty_files'])}):")
            for filename in layout_results["empty_files"][:10]:
                print(f"      - {filename}")
            if len(layout_results["empty_files"]) > 10:
                print(f"      ... and {len(layout_results['empty_files']) - 10} more")

        # Show examples
        if layout_results["example_layouts"]:
            print(f"\n📄 Example Layouts with Content:")
            for example in layout_results["example_layouts"]:
                print(f"\n   File: {example['file']}")
                print(
                    f"   Spans: {example['spans']}, Drawings: {example['drawings']}, BBoxes: {example['bboxes']}"
                )
                if example["sample_span"]:
                    print(f"   Sample span: {example['sample_span']}")

    # ========== B. Tag BBox Verification ==========
    print(f"\n")
    print_separator("=")
    print("B. TAG BBOX VERIFICATION (The Output)")
    print_separator("=")

    tag_results = analyze_tag_bboxes(num_examples=20)

    if tag_results:
        print(f"\n📊 Tag BBox Statistics:")
        print(f"   Total tags (in file): {tag_results['total_tags']:,}")
        print(f"   Tags with bbox: {tag_results['tags_with_bbox']}")
        print(f"   Tags with valid bbox: {tag_results['tags_with_valid_bbox']}")

        if tag_results["examples"]:
            print(f"\n📍 Example Tags with BBoxes:")
            for i, example in enumerate(tag_results["examples"], 1):
                print(f"\n   Example {i}:")
                print(f"      Tag: {example['tag']}")
                print(f"      BBox: {example['bbox']}")
                print(f"      Page: {example['page']}")
                print(f"      Confidence: {example['confidence']}")
                print(f"      Valid: {'✅' if example['valid'] else '❌'}")

    # ========== Final Verdict ==========
    print(f"\n")
    print_separator("=")
    print("🎯 FINAL VERDICT")
    print_separator("=")

    has_layout_data = (
        layout_results.get("total_bboxes", 0) > 0
        or layout_results.get("total_spans", 0) > 0
    )
    has_tag_bboxes = tag_results.get("tags_with_valid_bbox", 0) > 0

    print(f"\n✅ Spatial Data Status:")
    print(f"   Layout Files: {'✅ DATA FOUND' if has_layout_data else '❌ NO DATA'}")
    print(f"   Tag BBoxes: {'✅ VALID' if has_tag_bboxes else '❌ MISSING'}")

    if has_layout_data and has_tag_bboxes:
        print(f"\n🎉 VERDICT: ✅ SPATIAL DATA EXISTS")
        print(f"   Bounding boxes are present in both input and output")
        print(
            f"   Previous '0 bboxes' was likely due to small sample or wrong key name"
        )
    elif has_layout_data and not has_tag_bboxes:
        print(f"\n⚠️  VERDICT: PARTIAL - Layout data exists but tags missing bboxes")
        print(f"   Possible extraction issue")
    elif has_tag_bboxes and not has_layout_data:
        print(f"\n⚠️  VERDICT: PARTIAL - Tags have bboxes but layouts appear empty")
        print(f"   May be checking wrong keys in layout files")
    else:
        print(f"\n❌ VERDICT: NO SPATIAL DATA FOUND")
        print(f"   Serious data loss - requires investigation")

    print_separator()
    print("✅ Deep Verification Complete")
    print_separator()


if __name__ == "__main__":
    main()
