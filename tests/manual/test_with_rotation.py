"""
Test OCR with page rotation correction
"""
import sys
from pathlib import Path

# Add project root to path (handle both root and tests/manual execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import io

import fitz
from google.cloud import vision
from PIL import Image

from app.ingestion.geometric_assembly import GeometricAssembler


def test_with_rotation(page_idx=113):
    """Test OCR with rotation correction"""

    pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")

    doc = fitz.open(str(pdf_path))
    page = doc[page_idx]

    rotation = page.rotation
    print(f"\n{'='*80}")
    print(f"TESTING WITH ROTATION CORRECTION - PAGE {page_idx}")
    print(f"{'='*80}")
    print(f"Original page rotation: {rotation} degrees")
    print(f"Page size: {page.rect.width} x {page.rect.height}\n")

    # Get pixmap with high resolution
    mat = fitz.Matrix(2.5, 2.5)
    pix = page.get_pixmap(matrix=mat)

    # Convert to PIL Image
    img_bytes = pix.tobytes("png")
    pil_img = Image.open(io.BytesIO(img_bytes))

    print(f"Original image size: {pil_img.size}")

    # Rotate image to correct orientation
    # If page rotation is 270, we need to rotate image by -270 (or +90) to correct
    if rotation == 270:
        # Rotate counter-clockwise 90 degrees to correct
        pil_img_corrected = pil_img.rotate(90, expand=True)
        print(f"Rotating image +90 degrees to correct 270-degree page rotation")
    elif rotation == 90:
        pil_img_corrected = pil_img.rotate(-90, expand=True)
        print(f"Rotating image -90 degrees to correct 90-degree page rotation")
    elif rotation == 180:
        pil_img_corrected = pil_img.rotate(180, expand=True)
        print(f"Rotating image 180 degrees to correct 180-degree page rotation")
    else:
        pil_img_corrected = pil_img
        print(f"No rotation needed")

    print(f"Corrected image size: {pil_img_corrected.size}\n")

    # Convert back to bytes
    img_buffer = io.BytesIO()
    pil_img_corrected.save(img_buffer, format="PNG")
    img_bytes_corrected = img_buffer.getvalue()

    # OCR with Vision API
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=img_bytes_corrected)
    response = client.text_detection(image=image)

    if not response.text_annotations:
        print("❌ No text detected!")
        doc.close()
        return

    assembler = GeometricAssembler(
        vertical_tolerance=0.4, horizontal_tolerance=0.5, min_confidence=0.5
    )

    fragments = assembler.parse_vision_response(response)
    print(f"Parsed {len(fragments)} fragments\n")

    # Find all fragments containing TE/KE/XE
    te_containing = [f for f in fragments if "TE" in f.text.upper()]
    ke_containing = [f for f in fragments if "KE" in f.text.upper()]
    xe_containing = [f for f in fragments if "XE" in f.text.upper()]

    print(f"Fragments containing 'TE': {len(te_containing)}")
    if te_containing:
        print("Sample:")
        for f in te_containing[:10]:
            print(f"  '{f.text}'")

    print(f"\nFragments containing 'KE': {len(ke_containing)}")
    if ke_containing:
        print("Sample:")
        for f in ke_containing[:10]:
            print(f"  '{f.text}'")

    print(f"\nFragments containing 'XE': {len(xe_containing)}")
    if xe_containing:
        print("Sample:")
        for f in xe_containing[:10]:
            print(f"  '{f.text}'")

    print()

    # Search for target components
    print(f"{'='*80}")
    print("SEARCHING FOR TARGET TAG COMPONENTS")
    print(f"{'='*80}\n")

    frag_29 = [f for f in fragments if f.text == "29"]
    frag_TE = [f for f in fragments if f.text.upper() == "TE"]
    frag_KE = [f for f in fragments if f.text.upper() == "KE"]
    frag_XE = [f for f in fragments if f.text.upper() == "XE"]

    print(f"'29' fragments: {len(frag_29)}")
    print(f"'TE' fragments: {len(frag_TE)}")
    print(f"'KE' fragments: {len(frag_KE)}")
    print(f"'XE' fragments: {len(frag_XE)}")

    if frag_TE:
        print(f"\n✅ FOUND {len(frag_TE)} 'TE' fragments!")
        for f in frag_TE[:5]:
            print(f"  - '{f.text}' at ({f.center_x:.1f}, {f.center_y:.1f})")

    if frag_KE:
        print(f"\n✅ FOUND {len(frag_KE)} 'KE' fragments!")
        for f in frag_KE[:5]:
            print(f"  - '{f.text}' at ({f.center_x:.1f}, {f.center_y:.1f})")

    if frag_XE:
        print(f"\n✅ FOUND {len(frag_XE)} 'XE' fragments!")
        for f in frag_XE[:5]:
            print(f"  - '{f.text}' at ({f.center_x:.1f}, {f.center_y:.1f})")

    # Try to assemble tags
    print(f"\n{'='*80}")
    print("ATTEMPTING TAG ASSEMBLY")
    print(f"{'='*80}\n")

    tags = assembler.assemble_tags(fragments)

    if tags:
        print(f"✅ ASSEMBLED {len(tags)} TAGS!\n")
        for tag in tags:
            print(f"  🎯 {tag.tag}")
            print(f"     Pattern: {tag.pattern_match}")
            print(f"     Bbox: {tag.bbox}")
            print(f"     Confidence: {tag.confidence:.2f}\n")
    else:
        print("❌ No tags assembled")

    doc.close()
    return tags


if __name__ == "__main__":
    tags = test_with_rotation(113)
