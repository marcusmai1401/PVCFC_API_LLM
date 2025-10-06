import os

import paddle
from paddleocr import PaddleOCR

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
det_dir = rf"{ROOT}\det\PP-OCRv5_server_det_infer"
rec_dir = rf"{ROOT}\rec\latin_PP-OCRv5_mobile_rec_infer"
cls_dir = rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer"

print(
    f"Paddle: {paddle.__version__} CUDA: {paddle.is_compiled_with_cuda()} Device: {paddle.device.get_device()}"
)

# Test with custom models only (disable document preprocessor)
print("\n=== Initializing PP-OCRv5 (without doc preprocessor) ===")
try:
    ocr = PaddleOCR(
        text_detection_model_dir=det_dir,
        text_recognition_model_dir=rec_dir,
        textline_orientation_model_dir=cls_dir,
        use_textline_orientation=True,
        lang="vi",
    )
    print("\n✅ Initialized successfully!")
    print(" DET:", det_dir)
    print(" REC:", rec_dir)
    print(" CLS:", cls_dir)
    print(" DET is v5:", "v5" in det_dir.lower())
    print(" REC is v5:", "v5" in rec_dir.lower())

    # Try a simple OCR test
    print("\n=== Testing OCR ===")
    test_image = "test_image.jpg"  # You need to provide a test image
    if os.path.exists(test_image):
        result = ocr.ocr(test_image, cls=True)
        print(
            f"✅ OCR completed! Found {len(result[0]) if result and result[0] else 0} text regions"
        )
    else:
        print(f"⚠ Test image not found: {test_image}")
        print("✅ But initialization was successful!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
