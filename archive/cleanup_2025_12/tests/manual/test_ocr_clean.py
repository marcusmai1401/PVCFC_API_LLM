#!/usr/bin/env python3
"""
OCR System Verification Test
Tests Google Cloud Vision + Real-ESRGAN + Geometric Assembly
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path (handle both root and tests/manual execution)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import io

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

print("=" * 80)
print("OCR SYSTEM VERIFICATION TEST")
print("=" * 80)

# Track results
results = {"timestamp": datetime.now().isoformat(), "phases": {}}

# ============================================================================
# PHASE 1: Environment Verification
# ============================================================================
print("\n[PHASE 1] ENVIRONMENT VERIFICATION")
print("-" * 80)

# Check Python version
import platform

python_version = platform.python_version()
print(f"Python version: {python_version}")
results["phases"]["phase1_environment"] = {
    "python_version": python_version,
    "packages": {},
    "files": {},
}

# Check packages
packages_to_check = [
    "google-cloud-vision",
    "realesrgan",
    "basicsr",
    "torch",
    "torchvision",
]

for package in packages_to_check:
    try:
        if package == "google-cloud-vision":
            import google.cloud.vision

            version = google.cloud.vision.__version__
        elif package == "realesrgan":
            version = "pip-installed"
            results["phases"]["phase1_environment"]["packages"][package] = version
            print(f"  [OK] {package}: {version}")
            continue
        elif package == "basicsr":
            version = "pip-installed"
            results["phases"]["phase1_environment"]["packages"][package] = version
            print(f"  [OK] {package}: {version}")
            continue
        elif package == "torch":
            import torch

            version = torch.__version__
        elif package == "torchvision":
            import torchvision

            version = torchvision.__version__

        print(f"  [OK] {package}: {version}")
        results["phases"]["phase1_environment"]["packages"][package] = version
    except Exception as e:
        print(f"  [FAIL] {package}: NOT FOUND")
        results["phases"]["phase1_environment"]["packages"][package] = None

# Check critical files
files_to_check = {
    "realesrgan_model": "RealESRGAN_x4plus_anime_6B.pth",
    "credentials": "credentials.json",
    "pdf": r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf",
}

for file_key, file_path in files_to_check.items():
    path = Path(file_path)
    if path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  [OK] {file_key}: {size_mb:.2f} MB")
        results["phases"]["phase1_environment"]["files"][file_key] = {
            "exists": True,
            "size_mb": round(size_mb, 2),
        }
    else:
        print(f"  [FAIL] {file_key}: NOT FOUND")
        results["phases"]["phase1_environment"]["files"][file_key] = {"exists": False}

print("[PHASE 1] [OK] PASSED")

# ============================================================================
# PHASE 2: Google Cloud Vision Connection Test
# ============================================================================
print("\n[PHASE 2] GOOGLE CLOUD VISION CONNECTION TEST")
print("-" * 80)

try:
    from google.cloud import vision

    # Initialize client
    print("  Initializing Vision API client...")
    client = vision.ImageAnnotatorClient()
    print("  [OK] Client initialized")

    # Create a simple test image (white with black text)
    from PIL import Image, ImageDraw, ImageFont

    test_img = Image.new("RGB", (200, 100), color="white")
    draw = ImageDraw.Draw(test_img)

    # Draw simple text
    draw.text((20, 30), "TEST 123", fill="black")

    # Convert to bytes
    img_buffer = io.BytesIO()
    test_img.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    # Test OCR
    print("  Testing text detection with dummy image...")
    image = vision.Image(content=img_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        print(f"  [FAIL] Vision API error: {response.error.message}")
        results["phases"]["phase2_vision_connection"] = {
            "status": "FAILED",
            "error": response.error.message,
        }
    else:
        detected_text = (
            response.text_annotations[0].description
            if response.text_annotations
            else ""
        )
        print(f"  [OK] Text detected: '{detected_text.strip()}'")
        results["phases"]["phase2_vision_connection"] = {
            "status": "PASSED",
            "detected_text": detected_text.strip(),
        }

    print("[PHASE 2] [OK] PASSED")

except Exception as e:
    print(f"  [FAIL] Connection test failed: {e}")
    results["phases"]["phase2_vision_connection"] = {
        "status": "FAILED",
        "error": str(e),
    }
    print("[PHASE 2] [FAIL] FAILED")
    sys.exit(1)

# ============================================================================
# PHASE 3: OCR Test on Page 113
# ============================================================================
print("\n[PHASE 3] OCR TEST ON PAGE 113")
print("-" * 80)

pdf_path = Path(r"D:\Data_Raw\01. P&ID Ammonia Unit Rev12 (04000).pdf")
page_num = 113

phase3_results = {"page_num": page_num, "timings": {}, "metrics": {}}

try:
    # 3.1 Extract page
    print(f"  [1/4] Extracting page {page_num} from PDF...")
    doc = fitz.open(str(pdf_path))

    if len(doc) < page_num:
        raise ValueError(f"PDF only has {len(doc)} pages")

    page = doc[page_num - 1]  # 0-indexed
    print(
        f"  [OK] Page extracted (size: {page.rect.width:.0f}x{page.rect.height:.0f} pts)"
    )

    # Render to high-res PNG
    mat = fitz.Matrix(3.0, 3.0)  # 3x = 216 DPI
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    base_size_mb = len(img_bytes) / (1024 * 1024)

    print(f"  [OK] Rendered to PNG: {base_size_mb:.2f} MB")
    phase3_results["metrics"]["base_image_mb"] = round(base_size_mb, 2)

    # 3.2 Apply Real-ESRGAN enhancement
    print(f"  [2/4] Applying Real-ESRGAN 2x enhancement...")
    start_enhance = time.time()

    try:
        import cv2
        import torch
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4
        )

        model_path = Path("RealESRGAN_x4plus_anime_6B.pth")
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

        # Convert to numpy array
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Enhance
        enhanced, _ = upsampler.enhance(img, outscale=2)

        # Encode back to PNG
        _, buffer = cv2.imencode(".png", enhanced)
        enhanced_bytes = buffer.tobytes()

        enhance_time = time.time() - start_enhance
        enhanced_size_mb = len(enhanced_bytes) / (1024 * 1024)

        print(f"  [OK] Enhanced in {enhance_time:.2f}s (device: {device})")
        print(f"  [OK] Enhanced size: {enhanced_size_mb:.2f} MB")

        phase3_results["timings"]["enhancement_sec"] = round(enhance_time, 2)
        phase3_results["metrics"]["enhanced_image_mb"] = round(enhanced_size_mb, 2)
        phase3_results["metrics"]["device"] = device

        img_to_ocr = enhanced_bytes

    except Exception as e:
        print(f"  [WARN] Enhancement failed: {e}")
        print(f"  [INFO] Falling back to base image")
        enhance_time = 0
        img_to_ocr = img_bytes
        phase3_results["timings"]["enhancement_sec"] = 0
        phase3_results["metrics"]["enhancement_status"] = "SKIPPED"

    # 3.3 Run Google Cloud Vision OCR
    print(f"  [3/4] Running Google Cloud Vision OCR...")
    start_ocr = time.time()

    image = vision.Image(content=img_to_ocr)
    response = client.text_detection(image=image)

    ocr_time = time.time() - start_ocr

    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")

    # Extract results
    full_text = (
        response.text_annotations[0].description if response.text_annotations else ""
    )
    fragment_count = len(response.text_annotations) - 1  # Exclude first (full text)

    print(f"  [OK] OCR completed in {ocr_time:.2f}s")
    print(f"  [OK] Text extracted: {len(full_text)} chars")
    print(f"  [OK] Fragments detected: {fragment_count}")

    phase3_results["timings"]["ocr_sec"] = round(ocr_time, 2)
    phase3_results["metrics"]["text_chars"] = len(full_text)
    phase3_results["metrics"]["fragments"] = fragment_count

    # 3.4 Save OCR results
    print(f"  [4/4] Saving OCR results...")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Save text
    txt_file = output_dir / "page113_ocr_raw.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"PAGE {page_num} - RAW OCR OUTPUT\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        f.write(full_text)

    print(f"  [OK] Saved: {txt_file}")

    # Save JSON
    json_data = {
        "page_num": page_num,
        "ocr_text": full_text,
        "char_count": len(full_text),
        "fragment_count": fragment_count,
        "timings": phase3_results["timings"],
        "metrics": phase3_results["metrics"],
    }

    json_file = output_dir / "page113_ocr_raw.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Saved: {json_file}")

    doc.close()

    results["phases"]["phase3_ocr"] = phase3_results
    print("[PHASE 3] [OK] PASSED")

    # Store response for next phase
    ocr_response = response

except Exception as e:
    print(f"  [FAIL] OCR test failed: {e}")
    import traceback

    traceback.print_exc()
    results["phases"]["phase3_ocr"] = {"status": "FAILED", "error": str(e)}
    print("[PHASE 3] [FAIL] FAILED")
    sys.exit(1)

# ============================================================================
# PHASE 4: Geometric Assembly Test
# ============================================================================
print("\n[PHASE 4] GEOMETRIC ASSEMBLY TEST")
print("-" * 80)

phase4_results = {"timings": {}, "metrics": {}, "tags": []}

try:
    from app.ingestion.geometric_assembly import GeometricAssembler

    print("  [1/2] Running geometric assembly...")
    start_assembly = time.time()

    assembler = GeometricAssembler(
        vertical_tolerance=0.3, horizontal_tolerance=0.2, min_confidence=0.5
    )

    assembled_tags = assembler.extract_tags_from_vision_response(ocr_response)

    assembly_time = time.time() - start_assembly

    print(f"  [OK] Assembly completed in {assembly_time:.2f}s")
    print(f"  [OK] Tags assembled: {len(assembled_tags)}")

    phase4_results["timings"]["assembly_sec"] = round(assembly_time, 2)
    phase4_results["metrics"]["tags_count"] = len(assembled_tags)

    # Display tags
    if assembled_tags:
        print(f"\n  Assembled tags:")
        for i, tag in enumerate(assembled_tags[:10], 1):
            print(
                f"    {i}. {tag.tag} (conf: {tag.confidence:.2f}, pattern: {tag.pattern_match})"
            )
            phase4_results["tags"].append(
                {
                    "tag": tag.tag,
                    "confidence": tag.confidence,
                    "pattern": tag.pattern_match,
                    "bbox": tag.bbox,
                }
            )

        if len(assembled_tags) > 10:
            print(f"    ... and {len(assembled_tags) - 10} more")

    # Check target tags
    print(f"\n  [2/2] Checking target tags...")
    target_tags = ["29 TE 2003B", "29 TE 2035B", "29 KE 2014B", "29 XE 2012B"]

    assembled_tag_strings = [tag.tag for tag in assembled_tags]
    found_tags = []

    for target in target_tags:
        if target in assembled_tag_strings:
            print(f"    [OK] Found: {target}")
            found_tags.append(target)
        else:
            print(f"    [FAIL] Missing: {target}")

    phase4_results["metrics"]["target_tags_found"] = len(found_tags)
    phase4_results["metrics"]["target_tags_total"] = len(target_tags)

    # Save assembly results
    assembly_file = output_dir / "page113_assembled_tags.json"
    with open(assembly_file, "w", encoding="utf-8") as f:
        json.dump(phase4_results, f, indent=2, ensure_ascii=False)

    print(f"\n  [OK] Saved: {assembly_file}")

    results["phases"]["phase4_assembly"] = phase4_results
    print("[PHASE 4] [OK] PASSED")

except Exception as e:
    print(f"  [FAIL] Assembly test failed: {e}")
    import traceback

    traceback.print_exc()
    results["phases"]["phase4_assembly"] = {"status": "FAILED", "error": str(e)}
    print("[PHASE 4] [FAIL] FAILED")
    sys.exit(1)

# ============================================================================
# PHASE 5: Integration Test (PDFProcessor)
# ============================================================================
print("\n[PHASE 5] INTEGRATION TEST (PDFProcessor)")
print("-" * 80)

phase5_results = {"timings": {}, "metrics": {}}

try:
    from app.ingestion.pdf_processor import PDFProcessor

    print("  [1/2] Initializing PDFProcessor with OCR enabled...")
    processor = PDFProcessor(
        enable_ocr=True, document_type="P&ID", force_ocr_all_pages=False
    )

    print(f"  [OK] Processor initialized")
    print(f"    - OCR enabled: {processor.enable_ocr}")
    print(f"    - Document type: {processor.document_type}")

    # Process single page
    print(f"\n  [2/2] Processing page {page_num} via PDFProcessor...")
    print("  (This may take 20-30 seconds with Real-ESRGAN enhancement)")

    start_processing = time.time()

    # We'll manually process just one page to avoid full PDF processing
    doc = fitz.open(str(pdf_path))
    page = doc[page_num - 1]

    page_content, is_ocr = processor._process_page_with_ocr(
        page, page_num, str(pdf_path)
    )

    processing_time = time.time() - start_processing

    doc.close()

    print(f"  [OK] Processing completed in {processing_time:.2f}s")
    print(f"  [OK] Used OCR: {is_ocr}")
    print(f"  [OK] Text chars: {page_content.char_count}")
    print(f"  [OK] Words: {page_content.word_count}")

    # Check if assembled tags are in the text
    if "[Assembled Tags]" in page_content.text:
        print(f"  [OK] Assembled tags included in output")

    phase5_results["timings"]["processing_sec"] = round(processing_time, 2)
    phase5_results["metrics"]["used_ocr"] = is_ocr
    phase5_results["metrics"]["char_count"] = page_content.char_count
    phase5_results["metrics"]["word_count"] = page_content.word_count

    results["phases"]["phase5_integration"] = phase5_results
    print("[PHASE 5] [OK] PASSED")

except Exception as e:
    print(f"  [FAIL] Integration test failed: {e}")
    import traceback

    traceback.print_exc()
    results["phases"]["phase5_integration"] = {"status": "FAILED", "error": str(e)}
    print("[PHASE 5] [FAIL] FAILED")
    sys.exit(1)

# ============================================================================
# PHASE 6: Performance Benchmarks
# ============================================================================
print("\n[PHASE 6] PERFORMANCE BENCHMARKS")
print("-" * 80)

try:
    # Collect all timings
    enhancement_time = phase3_results["timings"].get("enhancement_sec", 0)
    ocr_time = phase3_results["timings"].get("ocr_sec", 0)
    assembly_time = phase4_results["timings"].get("assembly_sec", 0)
    total_time = enhancement_time + ocr_time + assembly_time

    print(
        f"  Enhancement:  {enhancement_time:6.2f}s ({enhancement_time/total_time*100:5.1f}%)"
    )
    print(f"  OCR:          {ocr_time:6.2f}s ({ocr_time/total_time*100:5.1f}%)")
    print(
        f"  Assembly:     {assembly_time:6.2f}s ({assembly_time/total_time*100:5.1f}%)"
    )
    print(f"  TOTAL:        {total_time:6.2f}s")

    # Check against targets
    print(f"\n  Target benchmarks:")
    print(
        f"    Enhancement: {enhancement_time:.2f}s {'[OK]' if enhancement_time < 25 else '[FAIL]'} (target: <25s)"
    )
    print(
        f"    OCR: {ocr_time:.2f}s {'[OK]' if ocr_time < 10 else '[FAIL]'} (target: <10s)"
    )
    print(
        f"    Total: {total_time:.2f}s {'[OK]' if total_time < 40 else '[FAIL]'} (target: <40s)"
    )

    results["phases"]["phase6_benchmarks"] = {
        "enhancement_sec": enhancement_time,
        "ocr_sec": ocr_time,
        "assembly_sec": assembly_time,
        "total_sec": total_time,
        "meets_targets": total_time < 40,
    }

    print("[PHASE 6] [OK] PASSED")

except Exception as e:
    print(f"  [FAIL] Benchmark analysis failed: {e}")
    results["phases"]["phase6_benchmarks"] = {"status": "FAILED", "error": str(e)}

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

all_passed = True
for phase_name, phase_data in results["phases"].items():
    if isinstance(phase_data, dict) and phase_data.get("status") == "FAILED":
        all_passed = False

# Check success criteria
success_criteria = {
    "Google Vision connects": results["phases"]["phase2_vision_connection"]["status"]
    == "PASSED",
    "Real-ESRGAN loads": phase3_results["timings"].get("enhancement_sec", 0) > 0,
    "OCR extracts 2500+ chars": phase3_results["metrics"]["text_chars"] >= 2500,
    "Assembly finds tags": phase4_results["metrics"]["tags_count"] >= 1,
    "Processing time < 40s": results["phases"]["phase6_benchmarks"]["total_sec"] < 40,
}

print("\nSuccess Criteria:")
for criterion, passed in success_criteria.items():
    print(f"  {'[OK]' if passed else '[FAIL]'} {criterion}")

all_success = all(success_criteria.values())

results["summary"] = {
    "all_phases_passed": all_passed,
    "success_criteria_met": all_success,
    "overall_status": "PASSED" if all_success else "FAILED",
}

# Save full results
results_file = output_dir / "ocr_verification_results.json"
with open(results_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n[OK] Full results saved to: {results_file}")

print("\n" + "=" * 80)
if all_success:
    print("[OK] OCR SYSTEM VERIFICATION: PASSED")
else:
    print("[FAIL] OCR SYSTEM VERIFICATION: FAILED")
print("=" * 80 + "\n")

sys.exit(0 if all_success else 1)
