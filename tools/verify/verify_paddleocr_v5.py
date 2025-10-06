"""
Script xác minh PaddlePaddle và PaddleOCR với PP-OCRv5
"""
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import sys

import paddle
from paddleocr import PaddleOCR
from paddleocr import __version__ as ocr_version

print("=" * 80)
print("ENVIRONMENT CHECK")
print("=" * 80)
print(f"Python: {sys.version}")
print(f"Paddle version: {paddle.__version__}")
print(f"CUDA compiled: {paddle.is_compiled_with_cuda()}")
print(f"GPU device: {paddle.device.get_device()}")
print(f"PaddleOCR version: {ocr_version}")
print()

print("=" * 80)
print("INITIALIZING PP-OCRv5 (MULTILINGUAL)")
print("=" * 80)

# Khởi tạo với mặc định - PaddleOCR 3.x nên auto-download PP-OCRv5
ocr = PaddleOCR(
    use_angle_cls=True, lang="vi", use_gpu=True, show_log=False  # Vietnamese + English
)

print("✅ PaddleOCR initialized successfully!")
print()

# Kiểm tra model paths
print("=" * 80)
print("MODEL PATH VERIFICATION (CRITICAL: MUST CONTAIN 'v5' or 'PP-OCRv5')")
print("=" * 80)

# Try to access internal model paths
try:
    # Det model
    det_model_dir = getattr(ocr.text_detector, "det_model_dir", "N/A")
    print(f"Detection model: {det_model_dir}")

    # Rec model
    rec_model_dir = getattr(ocr.text_recognizer, "rec_model_dir", "N/A")
    print(f"Recognition model: {rec_model_dir}")

    # Cls model
    cls_model_dir = (
        getattr(ocr.text_classifier, "cls_model_dir", "N/A")
        if hasattr(ocr, "text_classifier")
        else "N/A"
    )
    print(f"Classifier model: {cls_model_dir}")

    print()

    # Verify v5
    has_v5_det = (
        "v5" in str(det_model_dir).lower() or "ppocrv5" in str(det_model_dir).lower()
    )
    has_v5_rec = (
        "v5" in str(rec_model_dir).lower() or "ppocrv5" in str(rec_model_dir).lower()
    )
    has_v5_cls = (
        "v5" in str(cls_model_dir).lower() or "ppocrv5" in str(cls_model_dir).lower()
    )

    print("PP-OCRv5 VERIFICATION:")
    print(f"  Detection v5: {'✅ YES' if has_v5_det else '❌ NO (using older version!)'}")
    print(
        f"  Recognition v5: {'✅ YES' if has_v5_rec else '❌ NO (using older version!)'}"
    )
    print(
        f"  Classifier v5: {'✅ YES' if has_v5_cls else '❌ NO (using older version!)'}"
    )

    if has_v5_det and has_v5_rec:
        print()
        print("🎉 SUCCESS: PP-OCRv5 CONFIRMED!")
    else:
        print()
        print("⚠️  WARNING: Not using PP-OCRv5! Need to manually specify model paths.")

except Exception as e:
    print(f"Could not verify model paths: {e}")
    print("Will check via model config files...")

print()
print("=" * 80)
print("Verification complete. Check paths above.")
print("=" * 80)
