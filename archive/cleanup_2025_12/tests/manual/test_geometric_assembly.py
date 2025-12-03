"""
Test Geometric Assembly for P&ID tag extraction on page 113
"""
import sys
import time
from pathlib import Path

# Add project root to path (handle both root and tests/manual execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import io

from google.cloud import vision
from PIL import Image

from app.ingestion.geometric_assembly import GeometricAssembler

# Disable PIL decompression bomb check
Image.MAX_IMAGE_PIXELS = None


def main():
    print("\n" + "=" * 80)
    print("GEOMETRIC ASSEMBLY TEST ON test113.jpg")
    print("=" * 80)

    image_path = Path(r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\test113.jpg")

    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        return False

    print(f"[OK] Image found: {image_path.name}")

    # Load and resize image
    pil_img = Image.open(image_path)
    orig_width, orig_height = pil_img.size
    print(f"[INFO] Original size: {orig_width} x {orig_height} pixels")

    # Resize to prevent GPU OOM
    max_dim = 3000
    if orig_width > max_dim or orig_height > max_dim:
        ratio = min(max_dim / orig_width, max_dim / orig_height)
        new_size = (int(orig_width * ratio), int(orig_height * ratio))
        pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"[INFO] Resized to: {pil_img.size[0]} x {pil_img.size[1]} pixels")

    # Convert to bytes
    img_buffer = io.BytesIO()
    pil_img.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    print(f"[INFO] Image size: {len(img_bytes) / 1_000_000:.2f} MB")

    # Apply Real-ESRGAN 2x enhancement
    print("\n" + "=" * 80)
    print("STEP 1: REAL-ESRGAN 2X ENHANCEMENT")
    print("=" * 80)

    try:
        import cv2
        import numpy as np
        import torch
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        print("[INFO] Loading Real-ESRGAN model...")
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4
        )

        model_path = Path(__file__).parent / "RealESRGAN_x4plus_anime_6B.pth"
        device = "cuda" if torch.cuda.is_available() else "cpu"

        upsampler = RealESRGANer(
            scale=4,
            model_path=str(model_path),
            model=model,
            tile=400,
            tile_pad=10,
            pre_pad=0,
            half=True if device == "cuda" else False,
            device=device,
        )

        print(f"[OK] Model loaded on {device}")

        # Enhance
        print("[INFO] Enhancing image (2x upscale)...")
        start_enhance = time.time()

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        enhanced, _ = upsampler.enhance(img, outscale=2)

        _, buffer = cv2.imencode(".png", enhanced)
        enhanced_bytes = buffer.tobytes()

        enhance_time = time.time() - start_enhance

        print(f"[TIME] Enhancement: {enhance_time:.2f}s")
        print(f"[INFO] Enhanced size: {len(enhanced_bytes) / 1_000_000:.2f} MB")

    except Exception as e:
        print(f"[ERROR] Enhancement failed: {e}")
        return False

    # OCR with Google Cloud Vision
    print("\n" + "=" * 80)
    print("STEP 2: GOOGLE CLOUD VISION OCR")
    print("=" * 80)

    client = vision.ImageAnnotatorClient()
    image_enhanced = vision.Image(content=enhanced_bytes)

    print("[INFO] Running OCR on enhanced image...")
    start_ocr = time.time()
    response = client.text_detection(image=image_enhanced)
    ocr_time = time.time() - start_ocr

    print(f"[TIME] OCR: {ocr_time:.2f}s")

    if not response.text_annotations:
        print("[ERROR] No text detected by Vision API")
        return False

    full_text = response.text_annotations[0].description
    print(f"[INFO] Raw OCR text: {len(full_text)} chars")
    print(f"[INFO] Text fragments: {len(response.text_annotations) - 1}")

    # Geometric Assembly
    print("\n" + "=" * 80)
    print("STEP 3: GEOMETRIC ASSEMBLY")
    print("=" * 80)

    assembler = GeometricAssembler(
        vertical_tolerance=0.3, horizontal_tolerance=0.2, min_confidence=0.5
    )

    print("[INFO] Parsing fragments and assembling tags...")
    start_assembly = time.time()

    assembled_tags = assembler.extract_tags_from_vision_response(response)

    assembly_time = time.time() - start_assembly

    print(f"[TIME] Assembly: {assembly_time:.2f}s")
    print(f"[RESULT] Assembled {len(assembled_tags)} tags")

    # Display assembled tags
    print("\n" + "=" * 80)
    print("ASSEMBLED TAGS")
    print("=" * 80)

    if assembled_tags:
        # Sort by confidence
        sorted_tags = sorted(assembled_tags, key=lambda t: t.confidence, reverse=True)

        for i, tag in enumerate(sorted_tags[:20], 1):  # Show top 20
            print(
                f"{i:2d}. {tag.tag:20s} (conf: {tag.confidence:.2f}, pattern: {tag.pattern_match})"
            )
    else:
        print("[WARNING] No tags assembled")

    # Check for target tags
    print("\n" + "=" * 80)
    print("TARGET TAG DETECTION")
    print("=" * 80)

    target_tags = [
        "29 TE 2003B",
        "29 TE 2035B",
        "29 TE 2004A",
        "29 KE 2014B",
        "29 XE 2012B",
        "29 XE 2013B",
    ]

    assembled_tag_strings = [tag.tag for tag in assembled_tags]

    found_count = 0
    for target in target_tags:
        if target in assembled_tag_strings:
            print(f"  [FOUND] {target}")
            found_count += 1
        else:
            # Check for partial matches
            partial = any(
                target.split()[1] in tag
                for tag in assembled_tag_strings
                if target.split()[0] in tag
            )
            if partial:
                print(f"  [PARTIAL] {target}")
            else:
                print(f"  [MISS] {target}")

    print(f"\nSummary: {found_count}/{len(target_tags)} complete target tags found")

    # Show all tags containing target components
    print("\n" + "=" * 80)
    print("ALL TAGS WITH TARGET COMPONENTS")
    print("=" * 80)

    target_components = ["TE", "KE", "XE"]
    for comp in target_components:
        matching = [tag.tag for tag in assembled_tags if comp in tag.tag]
        if matching:
            print(f"\n{comp} tags ({len(matching)}):")
            for tag in matching[:10]:  # Show first 10
                print(f"  - {tag}")

    # Performance summary
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)

    total_time = enhance_time + ocr_time + assembly_time
    print(f"Enhancement:  {enhance_time:.2f}s ({enhance_time/total_time*100:.1f}%)")
    print(f"OCR:          {ocr_time:.2f}s ({ocr_time/total_time*100:.1f}%)")
    print(f"Assembly:     {assembly_time:.2f}s ({assembly_time/total_time*100:.1f}%)")
    print(f"TOTAL:        {total_time:.2f}s")

    # Success criteria
    success = len(assembled_tags) > 0 and found_count > 0

    print("\n" + "=" * 80)
    print(f"TEST {'PASSED' if success else 'FAILED'}")
    print("=" * 80 + "\n")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
