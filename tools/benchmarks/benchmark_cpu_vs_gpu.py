"""
BENCHMARK CPU vs GPU - 10 mẫu đại diện
Đo speedup thực tế của GPU so với CPU
"""

import importlib.util
import os
import random
import sys
import time
from pathlib import Path

import fitz

# Configure NVIDIA DLL paths for GPU
print("=" * 100)
print("BENCHMARK CPU vs GPU - OCR PERFORMANCE")
print("=" * 100)

print("\n[1/5] CONFIGURE GPU ENVIRONMENT")
print("-" * 100)

try:
    added = []
    for pkg, sub in [
        ("nvidia.cuda_runtime", "bin"),
        ("nvidia.cudnn", "bin"),
        ("nvidia.cublas", "bin"),
    ]:
        spec = importlib.util.find_spec(pkg)
        if spec and spec.submodule_search_locations:
            pkg_dir = spec.submodule_search_locations[0]
            bin_dir = os.path.join(pkg_dir, sub)
            if os.path.isdir(bin_dir):
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                os.add_dll_directory(bin_dir)
                added.append(bin_dir)
    if added:
        print(f"✓ Added {len(added)} NVIDIA DLL paths to PATH")
    else:
        print("⚠ No NVIDIA DLL paths added")
except Exception as e:
    print(f"⚠ Failed to configure GPU paths: {e}")

import paddle

# Import after path config
from paddleocr import PaddleOCR

print(f"✓ PaddlePaddle: {paddle.__version__}")
print(f"✓ CUDA compiled: {paddle.is_compiled_with_cuda()}")

# Initialize OCR engines
print("\n[2/5] INITIALIZE OCR ENGINES")
print("-" * 100)

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"

print("Initializing CPU OCR...")
ocr_cpu = PaddleOCR(
    lang="en",
    det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
    cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
    use_angle_cls=True,
    use_gpu=False,
    use_space_char=True,
    show_log=False,
)
print("✓ CPU OCR ready")

print("Initializing GPU OCR...")
try:
    ocr_gpu = PaddleOCR(
        lang="en",
        det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
        cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
        use_angle_cls=True,
        use_gpu=True,
        use_space_char=True,
        show_log=False,
    )
    print("✓ GPU OCR ready")
    gpu_available = True
except Exception as e:
    print(f"✗ GPU OCR failed: {e}")
    gpu_available = False
    sys.exit(1)

# Get sample files
print("\n[3/5] PREPARE TEST SAMPLES")
print("-" * 100)

data_dir = Path(r"D:\Data_Raw")
pdf_files = [f for f in data_dir.rglob("*.pdf") if not f.name.startswith("._")]

if len(pdf_files) < 10:
    print(f"⚠ Only {len(pdf_files)} PDFs found, will use all")
    sample_files = pdf_files
else:
    random.seed(42)
    sample_files = random.sample(pdf_files, 10)

print(f"✓ Selected {len(sample_files)} files for benchmark")
for i, f in enumerate(sample_files, 1):
    print(f"  {i}. {f.name}")


# Benchmark function
def benchmark_ocr(ocr_engine, pdf_path, mode_name, dpi=150):
    """Run OCR on first page and return timing stats"""
    try:
        # Convert PDF to image
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)

        temp_img = f"temp_bench_{mode_name}_{os.getpid()}.png"
        pix.save(temp_img)
        doc.close()

        # Run OCR
        start = time.time()
        result = ocr_engine.ocr(temp_img, cls=True)
        ocr_time = time.time() - start

        # Cleanup
        if os.path.exists(temp_img):
            os.remove(temp_img)

        # Stats
        regions = len(result[0]) if result and result[0] else 0

        return {"success": True, "time": ocr_time, "regions": regions}
    except Exception as e:
        return {"success": False, "error": str(e), "time": 0, "regions": 0}


# Run benchmark
print("\n[4/5] RUN BENCHMARK")
print("-" * 100)

results = []

for idx, pdf_file in enumerate(sample_files, 1):
    print(f"\n[{idx}/{len(sample_files)}] {pdf_file.name}")

    # CPU benchmark
    print("  CPU: ", end="", flush=True)
    cpu_result = benchmark_ocr(ocr_cpu, pdf_file, "cpu")
    if cpu_result["success"]:
        print(f"{cpu_result['time']:.2f}s ({cpu_result['regions']} regions)")
    else:
        print(f"✗ Error: {cpu_result['error']}")

    # GPU benchmark
    if gpu_available:
        print("  GPU: ", end="", flush=True)
        gpu_result = benchmark_ocr(ocr_gpu, pdf_file, "gpu")
        if gpu_result["success"]:
            speedup = (
                cpu_result["time"] / gpu_result["time"] if gpu_result["time"] > 0 else 0
            )
            print(
                f"{gpu_result['time']:.2f}s ({gpu_result['regions']} regions) - Speedup: {speedup:.2f}x"
            )
        else:
            print(f"✗ Error: {gpu_result['error']}")
            gpu_result = None
    else:
        gpu_result = None

    results.append({"file": pdf_file.name, "cpu": cpu_result, "gpu": gpu_result})

# Analysis
print("\n[5/5] ANALYSIS")
print("=" * 100)

# Filter successful results
successful = [
    r for r in results if r["cpu"]["success"] and r["gpu"] and r["gpu"]["success"]
]

if not successful:
    print("✗ No successful benchmark results")
    sys.exit(1)

# Calculate statistics
cpu_times = [r["cpu"]["time"] for r in successful]
gpu_times = [r["gpu"]["time"] for r in successful]
speedups = [r["cpu"]["time"] / r["gpu"]["time"] for r in successful]

avg_cpu = sum(cpu_times) / len(cpu_times)
avg_gpu = sum(gpu_times) / len(gpu_times)
avg_speedup = sum(speedups) / len(speedups)
min_speedup = min(speedups)
max_speedup = max(speedups)

print(f"\n📊 BENCHMARK RESULTS ({len(successful)} samples)")
print("-" * 100)
print(f"{'File':<50} {'CPU (s)':<10} {'GPU (s)':<10} {'Speedup':<10} {'Regions':<8}")
print("-" * 100)

for r in successful:
    speedup = r["cpu"]["time"] / r["gpu"]["time"]
    print(
        f"{r['file']:<50} {r['cpu']['time']:<10.2f} {r['gpu']['time']:<10.2f} "
        f"{speedup:<10.2f}x {r['cpu']['regions']:<8}"
    )

print("\n📈 SUMMARY STATISTICS")
print("-" * 100)
print(f"Average CPU time:        {avg_cpu:.2f}s per page")
print(f"Average GPU time:        {avg_gpu:.2f}s per page")
print(f"Average speedup:         {avg_speedup:.2f}x")
print(f"Speedup range:           {min_speedup:.2f}x - {max_speedup:.2f}x")

print("\n💡 ESTIMATED TOTAL TIME (276 files, ~1,380 pages)")
print("-" * 100)
total_pages = 1380
cpu_total_mins = (total_pages * avg_cpu) / 60
gpu_total_mins = (total_pages * avg_gpu) / 60
time_saved_mins = cpu_total_mins - gpu_total_mins

print(f"CPU mode:   ~{cpu_total_mins:.0f} minutes (~{cpu_total_mins/60:.1f} hours)")
print(f"GPU mode:   ~{gpu_total_mins:.0f} minutes (~{gpu_total_mins/60:.1f} hours)")
print(
    f"Time saved: ~{time_saved_mins:.0f} minutes (~{time_saved_mins/60:.1f} hours) with GPU"
)

print("\n🎯 RECOMMENDATION")
print("-" * 100)

if avg_speedup >= 2.0:
    print(
        f"✅ GPU provides {avg_speedup:.1f}x speedup - STRONGLY RECOMMENDED for production"
    )
    print(
        f"   Use GPU mode to save ~{time_saved_mins:.0f} minutes ({time_saved_mins/60:.1f} hours)"
    )
elif avg_speedup >= 1.5:
    print(f"✓ GPU provides {avg_speedup:.1f}x speedup - RECOMMENDED for production")
    print(f"  Use GPU mode to save ~{time_saved_mins:.0f} minutes")
elif avg_speedup >= 1.2:
    print(f"• GPU provides {avg_speedup:.1f}x speedup - MODERATE benefit")
    print(f"  GPU mode can save ~{time_saved_mins:.0f} minutes, but CPU is acceptable")
else:
    print(f"⚠ GPU speedup is only {avg_speedup:.1f}x - CPU may be sufficient")
    print(f"  Consider CPU mode unless processing very large datasets")

print("\n" + "=" * 100)
print("BENCHMARK COMPLETE")
print("=" * 100)

# Save results
import json

output_file = "benchmark_cpu_vs_gpu_results.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(
        {
            "summary": {
                "samples": len(successful),
                "avg_cpu_time": round(avg_cpu, 3),
                "avg_gpu_time": round(avg_gpu, 3),
                "avg_speedup": round(avg_speedup, 2),
                "min_speedup": round(min_speedup, 2),
                "max_speedup": round(max_speedup, 2),
            },
            "details": results,
        },
        f,
        indent=2,
        ensure_ascii=False,
    )

print(f"\n💾 Results saved to: {output_file}")
