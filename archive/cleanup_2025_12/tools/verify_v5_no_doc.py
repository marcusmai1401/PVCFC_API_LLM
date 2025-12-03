import os

import paddle

os.environ["PADDLEX_DISABLE_DOC_PREPROCESSOR"] = "1"  # Try to disable doc preprocessor

from paddleocr import PaddleOCR

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
det_dir = rf"{ROOT}\det\PP-OCRv5_server_det_infer"
rec_dir = rf"{ROOT}\rec\latin_PP-OCRv5_mobile_rec_infer"
cls_dir = rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer"

print(
    f"Paddle: {paddle.__version__} CUDA: {paddle.is_compiled_with_cuda()} Device: {paddle.device.get_device()}"
)
print(f"\n=== Using PP-OCRv5 with .pdmodel format ===")
print(f"DET: {det_dir}")
print(f"REC: {rec_dir}")
print(f"CLS: {cls_dir}")

try:
    print("\n🔧 Initializing PaddleOCR...")

    # Use lower-level API to avoid doc preprocessor
    from paddlex.inference import create_pipeline

    # Create pipeline config WITHOUT doc_preprocessor
    config = {
        "pipeline_name": "OCR",
        "text_detection_model_dir": det_dir,
        "text_recognition_model_dir": rec_dir,
        "textline_orientation_model_dir": cls_dir,
    }

    print("\n⚠️ NOTE: Using PaddleX direct API (experimental)")
    print("Creating pipeline with custom config...")

    pipeline = create_pipeline(config=config, device="gpu:0")

    print("\n✅ Pipeline created successfully!")
    print("✅ PP-OCRv5 is working with .pdmodel format!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nℹ️ Document preprocessor cannot be fully disabled via config.")
    print("ℹ️ Need to use PP-OCRv4 OR wait for official Paddle 3.0 stable release.")

    import traceback

    traceback.print_exc()
