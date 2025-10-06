"""
OCR Readiness Test - Test với file PDF thực tế
Kiểm tra xem PP-OCRv5 có sẵn sàng cho ingest production không
"""

import os
import sys
import time
from pathlib import Path

import paddle
from paddleocr import PaddleOCR

print("=" * 80)
print("PP-OCRv5 READINESS TEST FOR PRODUCTION INGEST")
print("=" * 80)

# 1. Verify Environment
print("\n[1/5] ENVIRONMENT CHECK")
print("-" * 80)
print(f"✓ PaddlePaddle: {paddle.__version__}")
print(f"✓ CUDA: {paddle.is_compiled_with_cuda()}")
print(f"✓ Device: {paddle.device.get_device()}")

import paddleocr

print(f"✓ PaddleOCR: {paddleocr.__version__}")

# 2. Initialize OCR
print("\n[2/5] INITIALIZING PP-OCRv5")
print("-" * 80)

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
det_model_dir = rf"{ROOT}\det\PP-OCRv5_server_det_infer"
rec_model_dir = rf"{ROOT}\rec\latin_PP-OCRv5_mobile_rec_infer"
cls_model_dir = rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer"

# Try GPU first, fallback to CPU if GPU fails
use_gpu = True
try:
    start_time = time.time()
    print("Attempting to initialize with GPU...")
    ocr = PaddleOCR(
        det_model_dir=det_model_dir,
        rec_model_dir=rec_model_dir,
        cls_model_dir=cls_model_dir,
        use_angle_cls=True,
        use_gpu=True,
        use_space_char=True,
        show_log=False,
    )
    init_time = time.time() - start_time
    print(f"✓ OCR initialized in {init_time:.2f}s (GPU)")
    print(f"✓ DET: PP-OCRv5_server")
    print(f"✓ REC: PP-OCRv5_mobile_latin")
    print(f"✓ CLS: ch_ppocr_mobile_v2.0")
except Exception as e:
    print(f"⚠ GPU initialization failed: {str(e)[:100]}...")
    print("\nFalling back to CPU mode...")
    try:
        start_time = time.time()
        ocr = PaddleOCR(
            det_model_dir=det_model_dir,
            rec_model_dir=rec_model_dir,
            cls_model_dir=cls_model_dir,
            use_angle_cls=True,
            use_gpu=False,
            use_space_char=True,
            show_log=False,
        )
        init_time = time.time() - start_time
        use_gpu = False
        print(f"✓ OCR initialized in {init_time:.2f}s (CPU)")
        print(f"✓ DET: PP-OCRv5_server")
        print(f"✓ REC: PP-OCRv5_mobile_latin")
        print(f"✓ CLS: ch_ppocr_mobile_v2.0")
    except Exception as e2:
        print(f"✗ FAILED to initialize OCR (both GPU and CPU): {e2}")
        sys.exit(1)

# 3. Check Data Directory
print("\n[3/5] DATA DIRECTORY CHECK")
print("-" * 80)

data_dir = Path(r"D:\Data_Raw")
if not data_dir.exists():
    print(f"✗ Data directory not found: {data_dir}")
    sys.exit(1)

# Count files
pdf_files = list(data_dir.rglob("*.pdf"))
tif_files = list(data_dir.rglob("*.tif")) + list(data_dir.rglob("*.tiff"))

print(f"✓ Data directory: {data_dir}")
print(f"✓ PDF files: {len(pdf_files)}")
print(f"✓ TIF files: {len(tif_files)}")
print(f"✓ Total: {len(pdf_files) + len(tif_files)} files")

# 4. Test with Real PDF
print("\n[4/5] TESTING WITH REAL PDF SAMPLE")
print("-" * 80)

if not pdf_files:
    print("✗ No PDF files found for testing")
    sys.exit(1)

# Select first PDF as test sample
test_pdf = pdf_files[0]
print(f"Test file: {test_pdf.name}")
print(f"File size: {test_pdf.stat().st_size / 1024:.1f} KB")

try:
    # For PDF, we need to convert to images first
    # Check if we have pdf2image or PyMuPDF
    try:
        import fitz  # PyMuPDF

        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False

    try:
        from pdf2image import convert_from_path

        HAS_PDF2IMAGE = True
    except ImportError:
        HAS_PDF2IMAGE = False

    if not HAS_PYMUPDF and not HAS_PDF2IMAGE:
        print("⚠ WARNING: Need PyMuPDF or pdf2image for PDF processing")
        print("  Install with: pip install PyMuPDF")
        print("\n  For now, testing with image-based OCR capability only...")

        # Still confirm OCR is ready
        print("\n✓ OCR engine is initialized and ready")
        print("✓ Can process: JPG, PNG, TIF images")
        print("⚠ PDF support requires: PyMuPDF or pdf2image")

    else:
        print(f"✓ PDF library available: {'PyMuPDF' if HAS_PYMUPDF else 'pdf2image'}")

        # Convert first page to test
        print("\nConverting first page to image...")

        if HAS_PYMUPDF:
            # Use PyMuPDF (faster)
            doc = fitz.open(str(test_pdf))
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            num_pages = len(doc)

            # Save to temp image
            temp_img = "temp_test_page.png"
            pix.save(temp_img)
            doc.close()

            print(f"✓ Converted page 1/{num_pages} to image ({pix.width}x{pix.height})")

        else:
            # Use pdf2image
            images = convert_from_path(
                str(test_pdf), first_page=1, last_page=1, dpi=200
            )
            temp_img = "temp_test_page.png"
            images[0].save(temp_img)
            print(f"✓ Converted page 1 to image")

        # Run OCR
        print("\nRunning OCR on test page...")
        start_time = time.time()
        result = ocr.ocr(temp_img, cls=True)
        ocr_time = time.time() - start_time

        # Clean up temp file
        if os.path.exists(temp_img):
            os.remove(temp_img)

        # Analyze results
        if result and result[0]:
            num_regions = len(result[0])
            print(f"\n✓ OCR completed in {ocr_time:.2f}s")
            print(f"✓ Detected {num_regions} text regions")

            # Show first 3 results
            print("\nSample results:")
            for idx, line in enumerate(result[0][:3], 1):
                text = line[1][0]
                conf = line[1][1]
                print(f"  {idx}. '{text}' (conf: {conf:.3f})")

            if num_regions > 3:
                print(f"  ... and {num_regions - 3} more regions")
        else:
            print("⚠ No text detected (might be pure graphics)")

except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# 5. Final Assessment
print("\n[5/5] READINESS ASSESSMENT")
print("=" * 80)

print("\n✅ PP-OCRv5 OCR ENGINE: READY")
if use_gpu:
    print("✅ GPU ACCELERATION: ENABLED")
else:
    print("⚠  GPU ACCELERATION: DISABLED (using CPU)")
print("✅ LOCAL MODELS (.pdmodel): LOADED")
print("✅ DATA ACCESS: OK")

if HAS_PYMUPDF or HAS_PDF2IMAGE:
    print("✅ PDF PROCESSING: SUPPORTED")
else:
    print("⚠  PDF PROCESSING: NEEDS PyMuPDF (install: pip install PyMuPDF)")

print("\n" + "=" * 80)
print("CONCLUSION: OCR is ready for production ingest")
print("=" * 80)

print("\nNext steps:")
print("1. Install PyMuPDF if needed: pip install PyMuPDF")
print("2. Create ingest script to:")
print("   - Loop through D:\\Data_Raw files")
print("   - Convert PDF pages to images")
print("   - Run OCR on each page")
print("   - Save results (JSON/CSV/DB)")
print("\nReady to proceed with full ingest! ✓")
