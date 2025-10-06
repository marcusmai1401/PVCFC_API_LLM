"""
FIX LATIN MODEL - Download model Latin chính thống từ PaddleOCR
"""

import os
from pathlib import Path

from paddleocr import PaddleOCR

print("=" * 100)
print("FIX LATIN MODEL - SỬ DỤNG MODEL PP-OCRv5 EN CHÍNH THỐNG")
print("=" * 100)

# Model PP-OCRv5 English từ PaddleOCR hub
# Khi để rec_model_dir=None và lang='en', PaddleOCR sẽ tự động download PP-OCRv5 English

print("\n[1/2] DOWNLOAD & INIT PP-OCRv5 ENGLISH MODEL")
print("-" * 100)

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"

try:
    # Sử dụng PP-OCRv5 English official model
    ocr_en = PaddleOCR(
        lang="en",  # Tự động download PP-OCRv5 English
        det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
        cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
        use_angle_cls=True,
        use_gpu=False,
        use_space_char=True,
        show_log=True,  # Show download progress
    )
    print("✓ PP-OCRv5 English model loaded")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

# Test với 1 file
print("\n[2/2] TEST WITH SAMPLE FILE")
print("-" * 100)

data_dir = Path(r"D:\Data_Raw")
pdf_files = [f for f in data_dir.rglob("*.pdf") if not f.name.startswith("._")]

if pdf_files:
    test_pdf = pdf_files[0]
    print(f"Testing: {test_pdf.name}")

    try:
        import fitz

        doc = fitz.open(str(test_pdf))
        page = doc[0]
        pix = page.get_pixmap(dpi=150)

        temp_img = "temp_en_test.png"
        pix.save(temp_img)
        doc.close()

        print(f"✓ Image converted")

        # Run OCR
        result = ocr_en.ocr(temp_img, cls=True)

        if result and result[0]:
            print(f"✓ Detected {len(result[0])} regions")
            print("\nFirst 5 results:")
            for idx, line in enumerate(result[0][:5], 1):
                text = line[1][0]
                conf = line[1][1]
                print(f"  {idx}. '{text}' (conf: {conf:.3f})")
        else:
            print("⚠ No text detected")

        # Cleanup
        if os.path.exists(temp_img):
            os.remove(temp_img)

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()

print("\n" + "=" * 100)
print("Model PP-OCRv5 English được cache tại: ~/.paddleocr/")
print("Thư mục model: ~/.paddleocr/whl/rec/en/")
print("=" * 100)
