"""
Run PaddleOCR directly on a PDF page image to inspect raw results
"""

import io
import sys
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from loguru import logger
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.ingestion.paddle_ocr_config import get_paddleocr_instance


def ocr_pdf_page(pdf_path: str, page_index: int = 1):
    pdf = fitz.open(pdf_path)
    page = pdf[page_index - 1]

    # Render to image and save to temp file
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)

    tmp_dir = Path("artifacts/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"ocr_debug_page{page_index}.png"
    pix.save(str(out_path))

    engine = get_paddleocr_instance()
    print(f"Engine: {type(engine)}")

    try:
        # Prefer passing image path
        result = engine.ocr(str(out_path), cls=True)
        print("Raw result type:", type(result))
        print("Result length:", len(result) if result is not None else None)
        print("Result preview:")
        print(result[:1])
    except Exception as e:
        import traceback

        print("Exception calling OCR on path:", e)
        traceback.print_exc()

    # Try numpy array path as well
    try:
        img_data = pix.pil_tobytes(format="PNG")
        image = Image.open(io.BytesIO(img_data))
        img_array = np.array(image)
        result2 = engine.ocr(img_array, cls=True)
        print("Raw result2 type:", type(result2))
        print("Result2 length:", len(result2) if result2 is not None else None)
        print("Result2 preview:")
        print(result2[:1])
    except Exception as e:
        import traceback

        print("Exception calling OCR on numpy array:", e)
        traceback.print_exc()

    # Fallback: use official English rec model (downloaded by PaddleOCR)
    try:
        from paddleocr import PaddleOCR

        print("\nTrying fallback engine: det+cls local, rec=official en...")
        from app.ingestion.paddle_ocr_config import PPOCRV5_CLS_MODEL, PPOCRV5_DET_MODEL

        ocr_en = PaddleOCR(
            det_model_dir=str(PPOCRV5_DET_MODEL),
            cls_model_dir=str(PPOCRV5_CLS_MODEL),
            rec_model_dir=None,  # let it download official en rec
            lang="en",
            use_angle_cls=True,
            use_gpu=True,
            use_space_char=True,
            show_log=False,
        )
        res3 = ocr_en.ocr(str(out_path), cls=True)
        print("Fallback result length:", len(res3) if res3 is not None else None)
        if res3 and res3[0]:
            print("Fallback detected regions:", len(res3[0]))
            print("First line: ", res3[0][0][1])
        else:
            print("Fallback: no text detected")
    except Exception as e:
        import traceback

        print("Fallback engine also failed:", e)
        traceback.print_exc()

    pdf.close()


if __name__ == "__main__":
    pdfs = [
        r"D:\Data_Raw\003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf",
        r"D:\Data_Raw\092_3N4-S4279947_Rev.1 Operation and maintenance manual of gear.pdf",
    ]
    for p in pdfs:
        print("=" * 80)
        print("Testing:", p)
        ocr_pdf_page(p, page_index=1)
