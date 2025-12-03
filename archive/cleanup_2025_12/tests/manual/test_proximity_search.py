#!/usr/bin/env python3
"""
Test proximity-based tag search on P&ID pages 113 and 117

Search strategy:
1. Query: "04 TT 2020" → Split into parts: ["04", "TT", "2020"]
2. Find pages where ALL parts exist
3. Check if parts are spatially close (using bounding boxes)
4. Rank by proximity score
"""
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz
from google.cloud import vision

# Add project root to path (handle both root and tests/manual execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TextFragment:
    """OCR text fragment with position"""

    text: str
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    page: int


@dataclass
class TagMatch:
    """Matched tag with proximity score"""

    tag: str
    parts: List[str]
    fragments: List[TextFragment]
    proximity_score: float
    page: int
    bbox: Tuple[int, int, int, int]  # Combined bbox


def extract_fragments_from_vision(response, page_num: int) -> List[TextFragment]:
    """Extract all text fragments with bounding boxes from Vision API response"""
    fragments = []

    if not response.text_annotations:
        return fragments

    # Skip first annotation (full text), use individual words
    for annotation in response.text_annotations[1:]:
        text = annotation.description.strip()

        # Get bounding box
        vertices = annotation.bounding_poly.vertices
        if len(vertices) != 4:
            continue

        x_coords = [v.x for v in vertices]
        y_coords = [v.y for v in vertices]

        x = min(x_coords)
        y = min(y_coords)
        width = max(x_coords) - x
        height = max(y_coords) - y

        bbox = (x, y, width, height)
        confidence = 1.0  # Vision API doesn't provide per-word confidence

        fragments.append(
            TextFragment(text=text, bbox=bbox, confidence=confidence, page=page_num)
        )

    return fragments


def calculate_distance(
    bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]
) -> float:
    """Calculate distance between two bounding boxes (center to center)"""
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    # Calculate centers
    cx1 = x1 + w1 / 2
    cy1 = y1 + h1 / 2
    cx2 = x2 + w2 / 2
    cy2 = y2 + h2 / 2

    # Euclidean distance
    return math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)


def find_tag_by_parts(
    fragments: List[TextFragment], tag_parts: List[str], max_distance: float = 200.0
) -> List[TagMatch]:
    """
    Find tag by searching for parts in proximity

    Args:
        fragments: List of OCR text fragments
        tag_parts: Tag parts to search for (e.g., ["04", "TT", "2020"])
        max_distance: Maximum distance between parts (pixels)

    Returns:
        List of matched tags with proximity scores
    """
    matches = []

    # Find all fragments matching each part
    part_fragments = {}
    for i, part in enumerate(tag_parts):
        part_upper = part.upper()
        matching = [f for f in fragments if f.text.upper() == part_upper]
        part_fragments[i] = matching

        print(f"  Part '{part}': {len(matching)} matches")

    # Check if all parts exist
    if any(len(matches) == 0 for matches in part_fragments.values()):
        print(f"  ❌ Not all parts found")
        return []

    # Try to find combinations where all parts are close together
    # Start with first part, then check if other parts are nearby
    for f0 in part_fragments[0]:
        # Try to find other parts near f0
        candidate_fragments = [f0]
        total_distance = 0.0

        for i in range(1, len(tag_parts)):
            # Find closest fragment for part i
            closest = None
            min_dist = float("inf")

            for fi in part_fragments[i]:
                dist = calculate_distance(candidate_fragments[-1].bbox, fi.bbox)
                if dist < min_dist:
                    min_dist = dist
                    closest = fi

            if closest and min_dist <= max_distance:
                candidate_fragments.append(closest)
                total_distance += min_dist
            else:
                # Part too far away, skip this combination
                break

        # Check if we found all parts
        if len(candidate_fragments) == len(tag_parts):
            # Calculate proximity score (lower distance = higher score)
            avg_distance = (
                total_distance / (len(tag_parts) - 1) if len(tag_parts) > 1 else 0
            )
            proximity_score = 1000.0 / (1.0 + avg_distance)  # Normalized score

            # Calculate combined bounding box
            all_x = [f.bbox[0] for f in candidate_fragments]
            all_y = [f.bbox[1] for f in candidate_fragments]
            all_x2 = [f.bbox[0] + f.bbox[2] for f in candidate_fragments]
            all_y2 = [f.bbox[1] + f.bbox[3] for f in candidate_fragments]

            combined_bbox = (
                min(all_x),
                min(all_y),
                max(all_x2) - min(all_x),
                max(all_y2) - min(all_y),
            )

            tag_text = " ".join(tag_parts)

            matches.append(
                TagMatch(
                    tag=tag_text,
                    parts=tag_parts,
                    fragments=candidate_fragments,
                    proximity_score=proximity_score,
                    page=f0.page,
                    bbox=combined_bbox,
                )
            )

            print(
                f"  ✅ Found '{tag_text}' with avg distance: {avg_distance:.1f}px, score: {proximity_score:.2f}"
            )

    # Sort by proximity score (higher = better)
    matches.sort(key=lambda m: m.proximity_score, reverse=True)

    return matches


def test_page(pdf_path: Path, page_num: int, test_tags: List[List[str]]):
    """Test proximity search on a specific page"""
    print(f"\n{'='*80}")
    print(f"TESTING PAGE {page_num}")
    print(f"{'='*80}")

    # Open PDF and get page
    doc = fitz.open(str(pdf_path))
    page = doc[page_num - 1]  # 0-indexed

    # Render to image at high DPI for better OCR
    print(f"[1/3] Rendering page at high DPI...")
    # Use 4x scale = 288 DPI (higher quality for OCR)
    mat = fitz.Matrix(4.0, 4.0)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    print(f"     Image size: {len(img_bytes) / 1024 / 1024:.2f} MB")

    # OCR
    print(f"[2/3] Running OCR...")
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=img_bytes)
    response = client.text_detection(image=image)

    # Extract fragments
    fragments = extract_fragments_from_vision(response, page_num)
    print(f"[3/3] Extracted {len(fragments)} text fragments")

    doc.close()

    # Test each tag
    print(f"\n{'='*80}")
    print(f"SEARCHING FOR TAGS")
    print(f"{'='*80}")

    all_results = []

    for tag_parts in test_tags:
        tag_str = " ".join(tag_parts)
        print(f"\n🔍 Searching for: {tag_str}")

        matches = find_tag_by_parts(fragments, tag_parts, max_distance=200)

        if matches:
            print(f"   Found {len(matches)} match(es)")
            for i, match in enumerate(matches[:3], 1):  # Show top 3
                print(f"   #{i}: Score={match.proximity_score:.2f}, BBox={match.bbox}")

            all_results.append(
                {
                    "query": tag_str,
                    "found": True,
                    "matches": len(matches),
                    "best_score": matches[0].proximity_score,
                    "best_bbox": matches[0].bbox,
                }
            )
        else:
            print(f"   ❌ Not found")
            all_results.append({"query": tag_str, "found": False, "matches": 0})

    return all_results


def main():
    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return False

    # Test tags (split into parts)
    test_tags = [
        ["29", "TE", "2003B"],
        ["29", "TE", "2035B"],
        ["29", "TE", "2004A"],
        ["29", "KE", "2014B"],
        ["29", "XE", "2012B"],
        ["29", "XE", "2013B"],
        # Also test tags we know exist from previous test
        ["29", "SG", "2201A"],  # Page 113
        ["04", "PV", "2029"],  # Page 117
        ["29", "PSV", "3001A"],  # Page 117
    ]

    all_page_results = {}

    # Test pages 113 and 117
    for page_num in [113, 117]:
        results = test_page(pdf_path, page_num, test_tags)
        all_page_results[page_num] = results

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    for page_num, results in all_page_results.items():
        print(f"\n📄 Page {page_num}:")
        found_count = sum(1 for r in results if r["found"])
        print(f"   Found: {found_count}/{len(results)} tags")

        for r in results:
            if r["found"]:
                print(f"   ✅ {r['query']} - Score: {r['best_score']:.2f}")
            else:
                print(f"   ❌ {r['query']}")

    # Save results
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "proximity_search_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_page_results, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] {output_file}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
