#!/usr/bin/env python3
"""Test OCR on specific pages from PDF"""
import io
import json
import sys
from pathlib import Path

import fitz
from google.cloud import vision
from PIL import Image

# Add project root to path (handle both root and tests/manual execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from app.ingestion.geometric_assembly import GeometricAssembler


def process_pdf_page(pdf_path, page_num):
    """Process single page from PDF with OCR + Geometric Assembly"""
    print(f"\n{'='*80}")
    print(f"PROCESSING PAGE {page_num} from {Path(pdf_path).name}")
    print(f"{'='*80}")

    # Open PDF
    doc = fitz.open(str(pdf_path))

    if len(doc) < page_num:
        print(f"[ERROR] PDF only has {len(doc)} pages")
        doc.close()
        return None

    page = doc[page_num - 1]  # 0-indexed

    # Render page to image at high DPI
    print(f"[1/3] Rendering page to image...")
    mat = fitz.Matrix(3.0, 3.0)  # 3x scale = 216 DPI
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")

    # OCR with Google Vision
    print(f"[2/3] Running OCR with Google Vision...")
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=img_bytes)
    response = client.text_detection(image=image)

    # Assemble tags
    print(f"[3/3] Assembling instrument tags...")
    assembler = GeometricAssembler(
        vertical_tolerance=0.3, horizontal_tolerance=0.2, min_confidence=0.5
    )
    assembled_tags = assembler.extract_tags_from_vision_response(response)

    # Extract full text
    ocr_text = (
        response.text_annotations[0].description if response.text_annotations else ""
    )

    # Format output
    tag_strings = [tag.tag for tag in assembled_tags]
    assembled_tags_text = "\n".join(tag_strings)

    doc.close()

    return {
        "page_num": page_num,
        "ocr_text": ocr_text,
        "assembled_tags": tag_strings,
        "assembled_tags_count": len(assembled_tags),
        "full_text": f"{ocr_text}\n\n[Assembled Tags]\n{assembled_tags_text}",
    }


def main():
    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return False

    # Test pages 113 and 117
    pages_to_test = [113, 117]
    results = []

    for page_num in pages_to_test:
        result = process_pdf_page(pdf_path, page_num)
        if result:
            results.append(result)

            # Display results
            print(f"\n{'='*80}")
            print(f"RESULTS - PAGE {page_num}")
            print(f"{'='*80}")
            print(f"[Assembled Tags] {result['assembled_tags_count']} found")
            print(f"\nTags:")
            for tag in result["assembled_tags"]:
                print(f"  - {tag}")

    # Save results
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    for result in results:
        page_num = result["page_num"]

        # Save text file
        txt_file = output_dir / f"page{page_num}_raw.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"PAGE {page_num} RAW OCR OUTPUT\n")
            f.write("=" * 80 + "\n\n")
            f.write(result["full_text"])

        # Save JSON file
        json_file = output_dir / f"page{page_num}_raw.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n[SAVED] {txt_file}")
        print(f"[SAVED] {json_file}")

    print(f"\n{'='*80}")
    print("SUCCESS - Check output/ directory for full results")
    print(f"{'='*80}\n")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
