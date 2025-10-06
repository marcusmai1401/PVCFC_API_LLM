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

# KHỞI TẠO THEO API MỚI (KHÔNG DÙNG use_gpu)
ocr = PaddleOCR(
    text_detection_model_dir=det_dir,
    text_recognition_model_dir=rec_dir,
    textline_orientation_model_dir=cls_dir,
    use_textline_orientation=True,  # thay cho use_angle_cls
    lang="vi",  # latin/vi đều ok cho tiếng Việt/Anh
)

print("Initialized OK")
print(" DET:", det_dir)
print(" REC:", rec_dir)
print(" CLS:", cls_dir)
print(" DET is v5:", "v5" in det_dir.lower())
print(" REC is v5:", "v5" in rec_dir.lower())
