#!/usr/bin/env python
"""
Debug script for Level 1: Visual Verification of Hybrid Layout Extraction.
Tests Page 7 of a real scanned document to verify table detection.

ENHANCED DEBUG VERSION - Prints detailed region and mapping info.
"""
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
from loguru import logger

# Setup path để import được module app
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_path = Path(PROJECT_ROOT) / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        logger.info(f"Loaded environment variables from {env_path}")

        # Set GOOGLE_APPLICATION_CREDENTIALS if in .env
        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
                        creds_path = line.split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
                        logger.info(f"Set GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
                        break
except ImportError:
    logger.warning("python-dotenv not installed")

from app.ingestion.layout.detector import LayoutDetector
from app.ingestion.layout.orchestrator import HybridExtractionOrchestrator
from app.ingestion.pdf_processor import PDFProcessor


def calculate_overlap(word_bbox, region_bbox, page_width, page_height):
    """
    Calculate overlap percentage of word within region.
    word_bbox: (x0, y0, x1, y1) in pixels
    region_bbox: (x0, y0, x1, y1) normalized 0-1
    """
    # Normalize word bbox to 0-1
    word_norm = (
        word_bbox[0] / page_width,
        word_bbox[1] / page_height,
        word_bbox[2] / page_width,
        word_bbox[3] / page_height,
    )

    # Calculate intersection
    x0 = max(word_norm[0], region_bbox[0])
    y0 = max(word_norm[1], region_bbox[1])
    x1 = min(word_norm[2], region_bbox[2])
    y1 = min(word_norm[3], region_bbox[3])

    if x0 >= x1 or y0 >= y1:
        return 0.0

    intersection = (x1 - x0) * (y1 - y0)
    word_area = (word_norm[2] - word_norm[0]) * (word_norm[3] - word_norm[1])

    if word_area <= 0:
        return 0.0

    return intersection / word_area


def verify_page_7():
    pdf_path = r"D:\Data_Raw\KT06101_TURBINE_HTC\KT06101_TURBINE_HTC\Data\3N4-S4275356 Steam turbine datasheet.pdf"
    target_page_num = 7  # 1-based index

    print(f"🚀 STARTING VERIFICATION FOR: {pdf_path}")
    print(f"📄 Target Page: {target_page_num}")

    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found at {pdf_path}")
        return

    try:
        # 1. Init Components
        processor = PDFProcessor()
        layout_detector = LayoutDetector.get_instance()

        # 2. Open PDF & Get Page
        doc = fitz.open(pdf_path)
        page = doc[target_page_num - 1]  # 0-indexed -> index 6

        # Get page dimensions (PDF points)
        page_width_pts = int(page.rect.width)
        page_height_pts = int(page.rect.height)
        print(f"\n📐 PDF Page dimensions (points): {page_width_pts} x {page_height_pts}")

        # 3. Render Image (Simulation of Ingestion flow)
        print("\n📸 Rendering page to image...")
        dpi = 200
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        # Image dimensions (pixels)
        img_width = pix.width
        img_height = pix.height
        print(f"📐 Rendered Image dimensions (pixels): {img_width} x {img_height}")
        print(f"📐 Zoom factor: {zoom:.2f}x (DPI: {dpi})")

        # ============================================================
        # DEBUG STEP 1: Run Surya Layout Detection DIRECTLY
        # ============================================================
        print("\n" + "=" * 60)
        print("🔍 DEBUG STEP 1: SURYA LAYOUT DETECTION (RAW)")
        print("=" * 60)

        raw_regions = layout_detector.detect_layout(img_bytes)
        print(f"\n📊 Surya detected {len(raw_regions)} regions:")

        if not raw_regions:
            print("   ❌ NO REGIONS DETECTED! This is the problem.")
            print("   Possible causes:")
            print("   - Surya model not loaded correctly")
            print("   - Image format issue")
            print("   - Document type not supported by Surya")
        else:
            for i, region in enumerate(raw_regions):
                bbox = region.bbox
                print(f"\n   [{i+1}] Label: {region.label}")
                print(f"       Confidence: {region.confidence:.3f}")
                print(
                    f"       BBox (normalized 0-1): ({bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f})"
                )
                # Convert to pixels for easier understanding
                px_bbox = (
                    int(bbox[0] * img_width),
                    int(bbox[1] * img_height),
                    int(bbox[2] * img_width),
                    int(bbox[3] * img_height),
                )
                print(
                    f"       BBox (pixels): ({px_bbox[0]}, {px_bbox[1]}, {px_bbox[2]}, {px_bbox[3]})"
                )
                print(
                    f"       Size (pixels): {px_bbox[2]-px_bbox[0]} x {px_bbox[3]-px_bbox[1]}"
                )

        # ============================================================
        # DEBUG STEP 2: Run GCV OCR
        # ============================================================
        print("\n" + "=" * 60)
        print("🔍 DEBUG STEP 2: GCV OCR EXTRACTION")
        print("=" * 60)

        processor.enable_ocr = True
        gcv_response = processor._perform_ocr(page)
        gcv_words = PDFProcessor.extract_gcv_words(gcv_response)
        print(f"\n📝 GCV extracted {len(gcv_words)} words")

        # Get fallback text
        fallback_text = ""
        if gcv_response and gcv_response.text_annotations:
            fallback_text = gcv_response.text_annotations[0].description

        # ============================================================
        # DEBUG STEP 3: Find specific word "PROTECTIVE" and check mapping
        # ============================================================
        print("\n" + "=" * 60)
        print("🔍 DEBUG STEP 3: MAPPING ANALYSIS - 'PROTECTIVE DEVICES'")
        print("=" * 60)

        # Find words containing "PROTECTIVE" or "DEVICES"
        target_words = []
        for w in gcv_words:
            if "PROTECTIVE" in w["text"].upper() or "DEVICES" in w["text"].upper():
                target_words.append(w)

        if target_words:
            print(f"\n📍 Found {len(target_words)} target words:")
            for w in target_words:
                bbox = w["bbox"]
                print(f"\n   Word: '{w['text']}'")
                print(
                    f"   BBox (pixels): ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})"
                )

                # Normalize to 0-1 for comparison
                norm_bbox = (
                    bbox[0] / img_width,
                    bbox[1] / img_height,
                    bbox[2] / img_width,
                    bbox[3] / img_height,
                )
                print(
                    f"   BBox (normalized): ({norm_bbox[0]:.4f}, {norm_bbox[1]:.4f}, {norm_bbox[2]:.4f}, {norm_bbox[3]:.4f})"
                )

                # Check overlap with each region
                print(f"\n   Overlap with regions:")
                for i, region in enumerate(raw_regions):
                    overlap = calculate_overlap(
                        bbox, region.bbox, img_width, img_height
                    )
                    status = "✅ MATCH" if overlap >= 0.6 else "❌ NO MATCH"
                    print(
                        f"      Region [{i+1}] {region.label}: {overlap*100:.1f}% {status}"
                    )
        else:
            print("   ⚠️ Words 'PROTECTIVE' or 'DEVICES' not found in GCV output")

            # Show first 10 words as sample
            print("\n   Sample of first 10 GCV words:")
            for i, w in enumerate(gcv_words[:10]):
                bbox = w["bbox"]
                print(f"      [{i+1}] '{w['text']}' at ({bbox[0]:.1f}, {bbox[1]:.1f})")

        # ============================================================
        # DEBUG STEP 4: Check coordinate system alignment
        # ============================================================
        print("\n" + "=" * 60)
        print("🔍 DEBUG STEP 4: COORDINATE SYSTEM CHECK")
        print("=" * 60)

        # Check if GCV coordinates are in image space or PDF space
        if gcv_words:
            max_x = max(w["bbox"][2] for w in gcv_words)
            max_y = max(w["bbox"][3] for w in gcv_words)
            print(f"\n   GCV max coordinates: ({max_x:.1f}, {max_y:.1f})")
            print(f"   Image dimensions: ({img_width}, {img_height})")

            if max_x > img_width * 1.1 or max_y > img_height * 1.1:
                print("   ⚠️ WARNING: GCV coordinates exceed image dimensions!")
                print("   This suggests GCV is using PDF points, not image pixels.")
                print(
                    f"   Ratio X: {max_x/img_width:.2f}, Ratio Y: {max_y/img_height:.2f}"
                )
            else:
                print("   ✅ GCV coordinates appear to be in image pixel space")

        # ============================================================
        # DEBUG STEP 5: Run full hybrid extraction
        # ============================================================
        print("\n" + "=" * 60)
        print("🔍 DEBUG STEP 5: FULL HYBRID EXTRACTION")
        print("=" * 60)

        orchestrator = HybridExtractionOrchestrator()
        result = orchestrator.extract_hybrid_markdown(
            page_image=img_bytes,
            gcv_words=gcv_words,
            page_num=target_page_num,
            page_width=img_width,
            page_height=img_height,
            fallback_text=fallback_text,
        )

        # Print stats
        print(f"\n📊 EXTRACTION STATS:")
        print(f"   - Headings detected: {result.heading_count}")
        print(f"   - Tables detected: {result.table_count}")
        print(f"   - Fallback used: {result.fallback_used}")
        print(f"   - Mapped regions count: {len(result.regions)}")

        # Print mapped region details
        print(f"\n📋 MAPPED REGION DETAILS:")
        for i, region in enumerate(result.regions):
            word_count = len(region.words) if hasattr(region, "words") else 0
            text_preview = (
                region.text[:80] + "..." if len(region.text) > 80 else region.text
            )
            print(f"\n   [{i+1}] {region.label} ({word_count} words)")
            print(f"       Text: '{text_preview}'")

        # ============================================================
        # OUTPUT MARKDOWN
        # ============================================================
        print("\n" + "=" * 60)
        print(f"✅ GENERATED MARKDOWN (Page {target_page_num})")
        print("=" * 60)
        print(result.markdown[:2000])  # First 2000 chars
        if len(result.markdown) > 2000:
            print(f"\n... [truncated, total {len(result.markdown)} chars]")
        print("=" * 60)

        # Check specific landmarks
        if (
            "EXHAUST RELIEF" in result.markdown
            or "VACCUM BREAKER" in result.markdown
            or "VACUUM BREAKER" in result.markdown
        ):
            print("\n🌟 SUCCESS: Table content detected!")
        else:
            print("\n⚠️ WARNING: Table content might be missing or malformed.")

        # Check for Markdown structure
        has_headings = "#" in result.markdown
        has_tables = "|" in result.markdown
        print(f"\n📝 MARKDOWN STRUCTURE CHECK:")
        print(f"   - Has headings (#): {has_headings}")
        print(f"   - Has tables (|): {has_tables}")

        if not has_headings and not has_tables:
            print("\n   ❌ OUTPUT IS PLAIN TEXT - NO MARKDOWN STRUCTURE!")
            print("   Root cause analysis:")
            if not raw_regions:
                print("   → Surya detected 0 regions")
            elif all(
                r.label in ("Page_Footer", "PageFooter", "Text") for r in raw_regions
            ):
                print("   → Surya only detected Footer/Text regions, no Headers/Tables")
            else:
                print("   → Check mapping logic - words may not overlap with regions")

        # Save output to file
        output_dir = Path(PROJECT_ROOT) / "artifacts" / "debug_layout"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"page_{target_page_num}_markdown.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.markdown)
        print(f"\n📁 Output saved to: {output_file}")

        # Save detailed debug info to JSON
        import json

        debug_file = output_dir / f"page_{target_page_num}_debug.json"
        debug_data = {
            "page_num": result.page_num,
            "image_dimensions": {"width": img_width, "height": img_height},
            "pdf_dimensions": {"width": page_width_pts, "height": page_height_pts},
            "zoom_factor": zoom,
            "dpi": dpi,
            "gcv_word_count": len(gcv_words),
            "surya_region_count": len(raw_regions),
            "surya_regions": [
                {
                    "label": r.label,
                    "confidence": r.confidence,
                    "bbox_normalized": r.bbox,
                    "bbox_pixels": (
                        int(r.bbox[0] * img_width),
                        int(r.bbox[1] * img_height),
                        int(r.bbox[2] * img_width),
                        int(r.bbox[3] * img_height),
                    ),
                }
                for r in raw_regions
            ],
            "mapped_regions": [
                {
                    "label": r.label,
                    "text": r.text[:200],
                    "word_count": len(r.words) if hasattr(r, "words") else 0,
                }
                for r in result.regions
            ],
            "extraction_stats": {
                "heading_count": result.heading_count,
                "table_count": result.table_count,
                "fallback_used": result.fallback_used,
            },
        }
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(debug_data, f, ensure_ascii=False, indent=2)
        print(f"📁 Debug info saved to: {debug_file}")

        # Cleanup
        orchestrator.cleanup()
        doc.close()

    except Exception as e:
        print(f"\n❌ EXCEPTION OCCURRED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    verify_page_7()
