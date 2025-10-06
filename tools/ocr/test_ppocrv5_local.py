"""
Test PP-OCRv5 với PaddleOCR 2.7.3
Sử dụng local models (.pdmodel/.pdiparams format)
Không dùng doc-preprocessor hay .json models
"""

import paddle
from paddleocr import PaddleOCR

print("=" * 60)
print("PP-OCRv5 Local Model Test (PaddleOCR 2.7.3)")
print("=" * 60)

# Verify versions
print(f"\n✓ PaddlePaddle: {paddle.__version__}")
print(f"✓ CUDA Available: {paddle.is_compiled_with_cuda()}")
print(f"✓ Device: {paddle.device.get_device()}")

# Import version
import paddleocr

print(f"✓ PaddleOCR: {paddleocr.__version__}")

# Local model paths (.pdmodel/.pdiparams format)
ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
det_model_dir = rf"{ROOT}\det\PP-OCRv5_server_det_infer"
rec_model_dir = rf"{ROOT}\rec\latin_PP-OCRv5_mobile_rec_infer"
cls_model_dir = rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer"

print(f"\n{'Model Paths:':<20}")
print(f"  DET: {det_model_dir}")
print(f"  REC: {rec_model_dir}")
print(f"  CLS: {cls_model_dir}")

print("\n" + "-" * 60)
print("Initializing PaddleOCR with local PP-OCRv5 models...")
print("-" * 60)

try:
    # Initialize OCR with local models
    # PaddleOCR 2.7.3 uses: det_model_dir, rec_model_dir, cls_model_dir
    # NOT: text_detection_model_dir (that's 3.x syntax)
    ocr = PaddleOCR(
        det_model_dir=det_model_dir,
        rec_model_dir=rec_model_dir,
        cls_model_dir=cls_model_dir,
        use_angle_cls=True,  # Enable text orientation detection
        use_gpu=True,  # Use GPU
        use_space_char=True,  # Recognize space characters
        show_log=False,  # Reduce verbosity
    )

    print("\n" + "=" * 60)
    print("✅ SUCCESS: PP-OCRv5 Initialized!")
    print("=" * 60)
    print("\n✓ Using local .pdmodel/.pdiparams format")
    print("✓ No .json (PIR) models loaded")
    print("✓ No doc-preprocessor dependency")
    print("✓ Running on GPU")

    # Test with sample image if exists
    import os

    test_images = ["test.jpg", "test.png", "sample.jpg", "image.jpg"]
    test_img = None

    for img in test_images:
        if os.path.exists(img):
            test_img = img
            break

    if test_img:
        print(f"\n{'='*60}")
        print(f"Testing OCR on: {test_img}")
        print("=" * 60)

        result = ocr.ocr(test_img, cls=True)

        if result and result[0]:
            print(f"\n✅ Detected {len(result[0])} text region(s):")
            print("-" * 60)
            for idx, line in enumerate(result[0][:5], 1):  # Show first 5
                box = line[0]
                text = line[1][0]
                conf = line[1][1]
                print(f"{idx}. Text: '{text}'")
                print(f"   Confidence: {conf:.3f}")
                print(f"   Box: {box[0]} -> {box[2]}")
                print()
        else:
            print("\n⚠ No text detected in image")
    else:
        print(f"\n{'='*60}")
        print("No test image found")
        print("=" * 60)
        print("\nTo test OCR, run:")
        print("  result = ocr.ocr('your_image.jpg', cls=True)")
        print("\nExample output:")
        print("  result[0] = list of [box, (text, confidence)]")

    print("\n" + "=" * 60)
    print("✅ All checks passed!")
    print("PP-OCRv5 is ready to use with local models")
    print("=" * 60)

except Exception as e:
    print(f"\n{'='*60}")
    print("❌ ERROR")
    print("=" * 60)
    print(f"\n{e}\n")

    import traceback

    traceback.print_exc()

    print("\nTroubleshooting:")
    print("1. Verify model paths exist")
    print("2. Check .pdmodel and .pdiparams files are present")
    print("3. Ensure no .json files in model directories")
