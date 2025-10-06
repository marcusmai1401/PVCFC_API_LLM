"""
TEST GPU OCR after installing cuDNN v8 (nvidia-cudnn-cu11)
This script adds cuDNN v8 (cu11) bin path dynamically, then runs a small OCR on GPU.
"""

import importlib.util
import os
import sys
import time

# 1) Prefer CUDA 11.8 runtime + cuDNN v8 (cu11) + cuBLAS bin in DLL search path
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
                # Prepend to PATH for Paddle's dynamic loader
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                os.add_dll_directory(bin_dir)
                added.append(bin_dir)
    if added:
        for d in added:
            print(f"✓ Added to DLL path: {d}")
    else:
        print("⚠ No NVIDIA DLL paths added (packages not found)")
except Exception as e:
    print(f"⚠ Failed to configure NVIDIA DLL paths: {e}")

# 2) Quick Paddle GPU check
import paddle

print(f"Paddle: {paddle.__version__}")
print(f"Compiled with CUDA: {paddle.is_compiled_with_cuda()}")
try:
    paddle.set_device("gpu:0")
    x = paddle.randn([2, 3])
    print("✓ GPU set_device ok, x place:", x.place)
except Exception as e:
    print("✗ GPU init failed:", e)
    sys.exit(1)

from pathlib import Path

# 3) Minimal OCR on GPU
from paddleocr import PaddleOCR

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"

ocr = PaddleOCR(
    lang="en",
    det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
    cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
    use_angle_cls=True,
    use_gpu=True,
    use_space_char=True,
    show_log=False,
)

# Pick one PDF and convert first page
import fitz

data_dir = Path(r"D:\Data_Raw")
pdf_files = [f for f in data_dir.rglob("*.pdf") if not f.name.startswith("._")]

if not pdf_files:
    print("✗ No PDF files found")
    sys.exit(1)

pdf_path = pdf_files[0]
print(f"Testing OCR GPU with: {pdf_path.name}")

# Convert to image
try:
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    temp_img = "_tmp_gpu_test.png"
    pix.save(temp_img)
    doc.close()
except Exception as e:
    print("✗ PDF to image failed:", e)
    sys.exit(1)

# Run OCR
try:
    t0 = time.time()
    res = ocr.ocr(temp_img, cls=True)
    dt = time.time() - t0
    if res and res[0]:
        print(f"✓ OCR GPU ok: {len(res[0])} regions in {dt:.2f}s")
        for i, line in enumerate(res[0][:3], 1):
            print(f"  {i}. '{line[1][0]}' (conf: {line[1][1]:.3f})")
    else:
        print("⚠ OCR returned no text")
finally:
    if os.path.exists(temp_img):
        try:
            os.remove(temp_img)
        except:
            pass
