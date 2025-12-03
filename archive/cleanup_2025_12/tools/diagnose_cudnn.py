"""
CHẨN ĐOÁN LỖI CUDNN
"""

import os
import subprocess
import sys
from pathlib import Path

print("=" * 100)
print("CHẨN ĐOÁN LỖI CUDNN")
print("=" * 100)

# 1. Check CUDA
print("\n[1/6] CUDA TOOLKIT")
print("-" * 100)

try:
    result = subprocess.run(
        ["nvcc", "--version"], capture_output=True, text=True, timeout=5
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("✗ nvcc not found - CUDA toolkit not installed or not in PATH")
except Exception as e:
    print(f"✗ Error checking nvcc: {e}")

# 2. Check NVIDIA driver
print("\n[2/6] NVIDIA DRIVER")
print("-" * 100)

try:
    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        lines = result.stdout.split("\n")[:10]  # First 10 lines
        for line in lines:
            print(line)
    else:
        print("✗ nvidia-smi not found")
except Exception as e:
    print(f"✗ Error checking nvidia-smi: {e}")

# 3. Check PaddlePaddle GPU
print("\n[3/6] PADDLEPADDLE GPU SUPPORT")
print("-" * 100)

try:
    import paddle

    print(f"PaddlePaddle version: {paddle.__version__}")
    print(f"CUDA available: {paddle.is_compiled_with_cuda()}")
    if paddle.is_compiled_with_cuda():
        print(f"CUDA version (compiled): {paddle.version.cuda()}")
        print(f"cuDNN version (compiled): {paddle.version.cudnn()}")
except Exception as e:
    print(f"✗ Error checking Paddle: {e}")

# 4. Search for cudnn DLL
print("\n[4/6] SEARCH FOR CUDNN DLL")
print("-" * 100)

cudnn_files = []

# Check common locations
search_paths = [
    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA",
    r"C:\Program Files\NVIDIA",
    r"C:\Windows\System32",
    os.path.dirname(sys.executable),  # Python directory
]

for search_path in search_paths:
    if os.path.exists(search_path):
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if "cudnn" in file.lower() and file.endswith(".dll"):
                    full_path = os.path.join(root, file)
                    cudnn_files.append(full_path)

if cudnn_files:
    print(f"Found {len(cudnn_files)} cuDNN DLL(s):")
    for dll in cudnn_files:
        size = os.path.getsize(dll) / (1024 * 1024)
        print(f"  - {dll} ({size:.1f} MB)")
else:
    print("✗ No cuDNN DLL found in common locations")

# 5. Check PATH environment
print("\n[5/6] CHECK PATH ENVIRONMENT")
print("-" * 100)

path_env = os.environ.get("PATH", "")
cuda_paths = [
    p for p in path_env.split(";") if "cuda" in p.lower() or "nvidia" in p.lower()
]

if cuda_paths:
    print("CUDA-related paths in PATH:")
    for p in cuda_paths:
        print(f"  - {p}")
else:
    print("⚠ No CUDA paths found in PATH environment")

# 6. Try GPU initialization
print("\n[6/6] TEST GPU INITIALIZATION")
print("-" * 100)

try:
    import paddle

    paddle.set_device("gpu:0")
    x = paddle.to_tensor([1.0, 2.0, 3.0])
    print(f"✓ GPU tensor created: {x}")
    print(f"✓ Device: {x.place}")
except Exception as e:
    print(f"✗ GPU initialization failed: {e}")
    import traceback

    traceback.print_exc()

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)

print("\nProbable causes if cuDNN error persists:")
print("  1. PaddlePaddle was built with a different CUDA/cuDNN version than installed")
print("  2. cuDNN DLL not in PATH or wrong version")
print("  3. Need to reinstall PaddlePaddle GPU version matching your CUDA version")

print("\nRecommended actions:")
print("  1. Check CUDA version from nvidia-smi")
print(
    "  2. Reinstall paddle with: python -m pip install paddlepaddle-gpu -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html"
)
print("  3. Or use CPU version for now: use_gpu=False")
