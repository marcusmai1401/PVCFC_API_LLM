#!/usr/bin/env python
"""
Visual Verification Test for Page Watermark

Tests that watermarks are correctly rendered on PDF pages.
Manual inspection required.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import io

from PIL import Image

from tools.pdf_renderer import PDFRenderer


def test_watermark_visual():
    """Render sample pages and visually inspect watermarks"""

    print("=" * 70)
    print("WATERMARK VISUAL VERIFICATION TEST")
    print("=" * 70)

    renderer = PDFRenderer()

    # P&ID document path
    pdf_path = r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf"

    # Test pages: mix of different locations
    test_pages = [
        10,  # Early page (legend area)
        27,  # Equipment section
        54,  # Mid document
        61,  # MYLP 04501A location
        71,  # MYLP 04504 location
        97,  # Later page
        102,  # Near end
    ]

    output_dir = PROJECT_ROOT / "temp_watermark_test"
    output_dir.mkdir(exist_ok=True)

    print(f"\nRendering {len(test_pages)} test pages...")
    print(f"Output directory: {output_dir}\n")

    results = []

    for page_num in test_pages:
        try:
            print(f"Page {page_num:3d}: ", end="", flush=True)

            # Render page
            img_bytes, metadata = renderer.render_page_to_image(
                pdf_path,
                page_num,
                dpi=200,
                format="png",
                use_cache=False,  # Force fresh render
            )

            # Save to file
            output_path = output_dir / f"page_{page_num:03d}_watermark.png"
            with open(output_path, "wb") as f:
                f.write(img_bytes)

            # Check image size
            img = Image.open(io.BytesIO(img_bytes))
            width, height = img.size

            # Expected font size for this height
            font_size = renderer._get_watermark_font_size(height)
            font_percent = (font_size / height) * 100

            print(
                f"OK | {width}x{height}px | Font: {font_size}px ({font_percent:.1f}%)"
            )

            results.append(
                {
                    "page": page_num,
                    "status": "OK",
                    "size": (width, height),
                    "font_size": font_size,
                    "font_percent": font_percent,
                    "file": str(output_path),
                }
            )

        except Exception as e:
            print(f"FAIL | Error: {e}")
            results.append({"page": page_num, "status": "FAIL", "error": str(e)})

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r.get("status") == "OK")
    print(f"Pages rendered: {success_count}/{len(test_pages)}")

    if success_count > 0:
        avg_font_percent = (
            sum(r.get("font_percent", 0) for r in results if r.get("status") == "OK")
            / success_count
        )
        print(f"Average font size: {avg_font_percent:.1f}% of image height")

    print(f"\nOutput files saved to: {output_dir}")

    # Manual inspection instructions
    print("\n" + "=" * 70)
    print("MANUAL INSPECTION CHECKLIST")
    print("=" * 70)
    print("Please open the generated PNG files and verify:")
    print()
    print("  1. ✓ Watermark 'P. XX' appears at TOP-LEFT corner")
    print("  2. ✓ Yellow background box is visible")
    print("  3. ✓ Black text with white outline is legible")
    print("  4. ✓ Watermark does NOT obscure important content")
    print("  5. ✓ Font size is appropriate for image size")
    print("  6. ✓ Position is consistent across all pages")
    print()
    print(f"  Open folder: {output_dir}")
    print()

    # Return status
    return success_count == len(test_pages)


if __name__ == "__main__":
    success = test_watermark_visual()
    sys.exit(0 if success else 1)
