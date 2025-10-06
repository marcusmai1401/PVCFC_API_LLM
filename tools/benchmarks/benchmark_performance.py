"""
BENCHMARK HIỆU NĂNG CPU - ƯỚC TÍNH GPU
"""

import os
import time
from pathlib import Path

import fitz
from paddleocr import PaddleOCR

print("=" * 100)
print("BENCHMARK HIỆU NĂNG OCR")
print("=" * 100)

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"

# Test với các DPI khác nhau
dpi_configs = [100, 150, 200, 300]

print("\n[1/3] INITIALIZE OCR")
print("-" * 100)

ocr = PaddleOCR(
    lang="en",
    det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
    cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
    use_angle_cls=True,
    use_gpu=False,  # CPU mode
    use_space_char=True,
    show_log=False,
)

print("✓ OCR initialized (CPU mode)")

# Get test file
print("\n[2/3] PREPARE TEST FILE")
print("-" * 100)

data_dir = Path(r"D:\Data_Raw")
pdf_files = [f for f in data_dir.rglob("*.pdf") if not f.name.startswith("._")]

if not pdf_files:
    print("✗ No PDF files found")
    exit(1)

test_pdf = pdf_files[0]
print(f"Test file: {test_pdf.name}")
print(f"Size: {test_pdf.stat().st_size / 1024:.1f} KB")

# Benchmark
print("\n[3/3] BENCHMARK - CPU MODE")
print("-" * 100)

results = []

for dpi in dpi_configs:
    print(f"\n📊 DPI = {dpi}")
    print("  ", end="")

    try:
        # Convert to image
        start_convert = time.time()
        doc = fitz.open(str(test_pdf))
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)
        temp_img = f"temp_bench_{dpi}.png"
        pix.save(temp_img)
        doc.close()
        convert_time = time.time() - start_convert

        img_size = os.path.getsize(temp_img) / 1024

        # OCR
        start_ocr = time.time()
        result = ocr.ocr(temp_img, cls=True)
        ocr_time = time.time() - start_ocr

        # Cleanup
        if os.path.exists(temp_img):
            os.remove(temp_img)

        # Stats
        num_regions = len(result[0]) if result and result[0] else 0
        total_time = convert_time + ocr_time

        results.append(
            {
                "dpi": dpi,
                "image_size_kb": img_size,
                "convert_time": convert_time,
                "ocr_time": ocr_time,
                "total_time": total_time,
                "regions": num_regions,
                "resolution": (pix.width, pix.height),
            }
        )

        print(
            f"Image: {pix.width}x{pix.height} ({img_size:.0f} KB) | "
            f"Convert: {convert_time:.2f}s | OCR: {ocr_time:.2f}s | "
            f"Total: {total_time:.2f}s | Regions: {num_regions}"
        )

    except Exception as e:
        print(f"✗ Error: {e}")

# Summary
print("\n" + "=" * 100)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 100)

if results:
    print("\n📊 PERFORMANCE COMPARISON (CPU)")
    print("-" * 100)
    print(
        f"{'DPI':<6} {'Resolution':<15} {'Image KB':<10} {'OCR Time':<10} {'Total Time':<12} {'Regions':<8}"
    )
    print("-" * 100)
    for r in results:
        print(
            f"{r['dpi']:<6} {str(r['resolution']):<15} {r['image_size_kb']:<10.0f} "
            f"{r['ocr_time']:<10.2f} {r['total_time']:<12.2f} {r['regions']:<8}"
        )

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 100)

    # Optimal DPI
    best_dpi = min(
        results, key=lambda x: x["total_time"] if x["regions"] > 10 else float("inf")
    )
    print(f"\n1. OPTIMAL DPI FOR CPU MODE:")
    print(f"   ✓ DPI = {best_dpi['dpi']} gives best balance")
    print(f"   ✓ Processing time: {best_dpi['total_time']:.2f}s per page")
    print(f"   ✓ Text regions: {best_dpi['regions']}")

    # DPI 150 recommendation
    dpi150 = next((r for r in results if r["dpi"] == 150), None)
    if dpi150:
        print(f"\n2. RECOMMENDED: DPI = 150 (Standard)")
        print(f"   ✓ Good quality/speed balance")
        print(f"   ✓ Processing time: {dpi150['total_time']:.2f}s per page")
        print(f"   ✓ Estimated total time for 276 files (~5 pages avg):")
        print(f"     • Total pages: ~1,380")
        print(
            f"     • Total time: ~{(1380 * dpi150['total_time'] / 60):.0f} minutes (~{(1380 * dpi150['total_time'] / 3600):.1f} hours)"
        )

    # GPU estimation
    print(f"\n3. GPU SPEEDUP (IF FIXED):")
    print(f"   • Typical GPU speedup: 3-5x faster than CPU")
    print(f"   • Estimated GPU time: {dpi150['ocr_time'] / 4:.2f}s per page (DPI 150)")
    print(
        f"   • Total time with GPU: ~{(1380 * dpi150['ocr_time'] / 4 / 60):.0f} minutes (~{(1380 * dpi150['ocr_time'] / 4 / 3600):.1f} hours)"
    )

    print(f"\n4. GPU FIX REQUIREMENT:")
    print(f"   ⚠ PaddlePaddle 2.6.2 requires: CUDA 11.8 + cuDNN 8.6.0")
    print(f"   ⚠ Current system: CUDA 12.6 + cuDNN 9.x (mismatch)")
    print(f"   ")
    print(f"   Options:")
    print(f"   A) Download & install cuDNN 8.6.0 for CUDA 11.8")
    print(f"      - Download: https://developer.nvidia.com/cudnn-downloads")
    print(f"      - Extract cudnn64_8.dll to: C:\\Windows\\System32\\")
    print(f"      - Or add cuDNN bin path to PATH environment")
    print(f"   ")
    print(f"   B) Use CPU mode (current) - acceptable for ~276 files")
    print(f"      - Total time: ~{(1380 * dpi150['total_time'] / 60):.0f} minutes")
    print(f"      - Can run overnight or in background")

print("\n" + "=" * 100)
print("BENCHMARK COMPLETE")
print("=" * 100)
