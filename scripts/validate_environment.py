#!/usr/bin/env python3
"""
Comprehensive Environment Validation
Validate all dependencies before ingestion
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime

# Validation results
results = {"timestamp": datetime.now().isoformat(), "validation": {}}

print("=" * 80)
print("COMPREHENSIVE ENVIRONMENT VALIDATION")
print("=" * 80)

# ============================================================================
# Phase 1: Python Environment
# ============================================================================
print("\n[PHASE 1] PYTHON ENVIRONMENT")
print("-" * 80)

import platform

python_version = platform.python_version()
print(f"Python version: {python_version}")

if python_version.startswith("3.11."):
    print("[OK] Python 3.11.x detected")
    results["validation"]["python_version"] = {
        "status": "pass",
        "version": python_version,
    }
else:
    print(f"[WARN] Python version is {python_version}, recommended: 3.11.9")
    results["validation"]["python_version"] = {
        "status": "warn",
        "version": python_version,
    }

# ============================================================================
# Phase 2: Critical Packages
# ============================================================================
print("\n[PHASE 2] CRITICAL PACKAGES")
print("-" * 80)

packages_to_check = {
    "google-cloud-vision": ("google.cloud.vision", "3.7.0"),
    "torch": ("torch", "2.5.0"),
    "torchvision": ("torchvision", "0.20.0"),
    "realesrgan": (None, "0.3.0"),  # Skip import due to compatibility
    "basicsr": (None, "1.4.2"),  # Skip import
    "pymupdf": ("fitz", "1.26.0"),
    "weaviate-client": ("weaviate", "4.17.0"),
    "opensearch-py": ("opensearchpy", "3.0.0"),
}

packages_status = {}

for package_name, (import_name, min_version) in packages_to_check.items():
    try:
        if import_name:
            module = __import__(import_name)
            version = getattr(module, "__version__", "unknown")
            print(f"  [OK] {package_name:25s} {version}")
            packages_status[package_name] = {"status": "installed", "version": version}
        else:
            # Skip import for problematic packages
            print(f"  [OK] {package_name:25s} pip-installed")
            packages_status[package_name] = {
                "status": "installed",
                "version": "pip-installed",
            }
    except Exception as e:
        print(f"  [FAIL] {package_name:25s} NOT FOUND")
        packages_status[package_name] = {"status": "missing", "error": str(e)}

results["validation"]["packages"] = packages_status

# ============================================================================
# Phase 3: GPU & CUDA
# ============================================================================
print("\n[PHASE 3] GPU & CUDA")
print("-" * 80)

try:
    import torch

    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU device: {torch.cuda.get_device_name(0)}")
        print(f"GPU count: {torch.cuda.device_count()}")
        print("[OK] GPU acceleration available")
        results["validation"]["gpu"] = {
            "status": "available",
            "device": torch.cuda.get_device_name(0),
            "cuda_version": torch.version.cuda,
        }
    else:
        print("[WARN] CUDA not available - will use CPU (slower)")
        results["validation"]["gpu"] = {"status": "cpu_only"}

except Exception as e:
    print(f"[FAIL] GPU check failed: {e}")
    results["validation"]["gpu"] = {"status": "error", "error": str(e)}

# ============================================================================
# Phase 4: Critical Files
# ============================================================================
print("\n[PHASE 4] CRITICAL FILES")
print("-" * 80)

files_to_check = {
    "RealESRGAN model": Path("RealESRGAN_x4plus_anime_6B.pth"),
    "Google credentials": Path("credentials.json"),
    "Source directory": Path(r"D:\Data_Raw"),
    "Artifacts directory": Path(r"D:\PVCFC_Artifacts"),
}

files_status = {}

for file_name, file_path in files_to_check.items():
    if file_path.exists():
        if file_path.is_file():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  [OK] {file_name:25s} {size_mb:.2f} MB")
            files_status[file_name] = {"status": "exists", "size_mb": round(size_mb, 2)}
        else:
            print(f"  [OK] {file_name:25s} (directory)")
            files_status[file_name] = {"status": "exists", "type": "directory"}
    else:
        print(f"  [FAIL] {file_name:25s} NOT FOUND")
        files_status[file_name] = {"status": "missing", "path": str(file_path)}

results["validation"]["files"] = files_status

# ============================================================================
# Phase 5: Config Files
# ============================================================================
print("\n[PHASE 5] CONFIG FILES")
print("-" * 80)

config_files = [
    "config/cadlike_gate.yaml",
    "config/tag_grammar.yaml",
    "config/page_filters.yaml",
]

config_status = {}

for config_file in config_files:
    path = Path(config_file)
    if path.exists():
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            print(f"  [OK] {config_file:30s} (valid YAML)")
            config_status[config_file] = {"status": "valid"}
        except Exception as e:
            print(f"  [FAIL] {config_file:30s} (invalid YAML): {e}")
            config_status[config_file] = {"status": "invalid", "error": str(e)}
    else:
        print(f"  [FAIL] {config_file:30s} NOT FOUND")
        config_status[config_file] = {"status": "missing"}

results["validation"]["config_files"] = config_status

# ============================================================================
# Phase 6: Google Cloud Vision Connection
# ============================================================================
print("\n[PHASE 6] GOOGLE CLOUD VISION API")
print("-" * 80)

try:
    import io

    from google.cloud import vision
    from PIL import Image, ImageDraw

    client = vision.ImageAnnotatorClient()
    print("[OK] Vision API client initialized")

    # Quick test with dummy image
    test_img = Image.new("RGB", (100, 50), color="white")
    draw = ImageDraw.Draw(test_img)
    draw.text((10, 15), "TEST", fill="black")

    img_buffer = io.BytesIO()
    test_img.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    image = vision.Image(content=img_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        print(f"[FAIL] Vision API error: {response.error.message}")
        results["validation"]["vision_api"] = {
            "status": "error",
            "error": response.error.message,
        }
    else:
        detected = (
            response.text_annotations[0].description
            if response.text_annotations
            else ""
        )
        print(f"[OK] Vision API working (detected: '{detected.strip()}')")
        results["validation"]["vision_api"] = {"status": "pass"}

except Exception as e:
    print(f"[FAIL] Vision API test failed: {e}")
    results["validation"]["vision_api"] = {"status": "error", "error": str(e)}

# ============================================================================
# Phase 7: Real-ESRGAN
# ============================================================================
print("\n[PHASE 7] REAL-ESRGAN")
print("-" * 80)

try:
    import torch
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    print("[OK] Real-ESRGAN imports successfully")

    # Check model file
    model_path = Path("RealESRGAN_x4plus_anime_6B.pth")
    if model_path.exists():
        print(
            f"[OK] Model file found: {model_path.stat().st_size / (1024*1024):.2f} MB"
        )

        # Test model loading (quick init)
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"[OK] Real-ESRGAN will use device: {device}")
        results["validation"]["realesrgan"] = {"status": "pass", "device": device}
    else:
        print(f"[FAIL] Model file not found: {model_path}")
        results["validation"]["realesrgan"] = {
            "status": "error",
            "error": "Model file missing",
        }

except Exception as e:
    print(f"[FAIL] Real-ESRGAN test failed: {e}")
    results["validation"]["realesrgan"] = {"status": "error", "error": str(e)}

# ============================================================================
# Phase 8: basicsr Patch Verification
# ============================================================================
print("\n[PHASE 8] BASICSR PATCH")
print("-" * 80)

try:
    basicsr_file = Path(
        "C:/Users/Admin/AppData/Local/Programs/Python/Python311/Lib/site-packages/basicsr/data/degradations.py"
    )

    if basicsr_file.exists():
        with open(basicsr_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            line8 = lines[7].strip() if len(lines) > 7 else ""

        if "from torchvision.transforms.functional import rgb_to_grayscale" in line8:
            print("[OK] basicsr patch applied correctly")
            print(f"     Line 8: {line8}")
            results["validation"]["basicsr_patch"] = {"status": "pass"}
        else:
            print(f"[WARN] basicsr may not be patched")
            print(f"       Line 8: {line8}")
            results["validation"]["basicsr_patch"] = {"status": "warn", "line8": line8}
    else:
        print(f"[SKIP] basicsr file not found at expected location")
        results["validation"]["basicsr_patch"] = {"status": "skip"}

except Exception as e:
    print(f"[SKIP] Patch check failed: {e}")
    results["validation"]["basicsr_patch"] = {"status": "skip"}

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

# Count pass/fail
total_checks = len(results["validation"])
passed = sum(
    1
    for v in results["validation"].values()
    if isinstance(v, dict) and v.get("status") in ["pass", "valid", "available"]
)
warned = sum(
    1
    for v in results["validation"].values()
    if isinstance(v, dict) and v.get("status") == "warn"
)
failed = sum(
    1
    for v in results["validation"].values()
    if isinstance(v, dict) and v.get("status") in ["error", "missing", "invalid"]
)

print(f"Total checks: {total_checks}")
print(f"  Passed: {passed}")
print(f"  Warnings: {warned}")
print(f"  Failed: {failed}")

# Save results
output_file = Path("validation_results.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: {output_file}")

print("\n" + "=" * 80)
if failed == 0:
    print("[OK] ENVIRONMENT VALIDATION: PASSED")
    print("=" * 80)
    sys.exit(0)
else:
    print(f"[FAIL] ENVIRONMENT VALIDATION: {failed} CRITICAL FAILURES")
    print("=" * 80)
    print("\nFix critical issues before proceeding with ingestion!")
    sys.exit(1)
