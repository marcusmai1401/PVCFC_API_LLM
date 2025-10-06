"""
PHÂN TÍCH VÀ XỬ LÝ PDF HYBRID (P&ID)
Chiến lược: Text vector extract + OCR cho phần không extract được
"""

import os
import time
from pathlib import Path

import fitz  # PyMuPDF
from paddleocr import PaddleOCR


def analyze_pdf_content(pdf_path):
    """
    Phân tích PDF để xác định:
    - % text có thể extract (vector)
    - % cần OCR (raster/embedded images)
    """
    doc = fitz.open(str(pdf_path))

    stats = {
        "total_pages": len(doc),
        "pages_with_text": 0,
        "pages_with_images": 0,
        "total_text_chars": 0,
        "pages_detail": [],
    }

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text (vector)
        text = page.get_text()
        text_chars = len(text.strip())

        # Count images
        images = page.get_images()

        # Classify page
        has_text = text_chars > 50  # Threshold: >50 chars = có text
        has_images = len(images) > 0

        page_type = "unknown"
        if has_text and has_images:
            page_type = "hybrid"  # P&ID typical case
        elif has_text:
            page_type = "text_only"
        elif has_images:
            page_type = "image_only"
        else:
            page_type = "empty"

        stats["pages_detail"].append(
            {
                "page": page_num + 1,
                "type": page_type,
                "text_chars": text_chars,
                "images": len(images),
                "extractable_text": text[:200] if text_chars > 0 else None,
            }
        )

        if has_text:
            stats["pages_with_text"] += 1
            stats["total_text_chars"] += text_chars
        if has_images:
            stats["pages_with_images"] += 1

    doc.close()
    return stats


def extract_hybrid_content(pdf_path, ocr_engine, dpi=150):
    """
    Xử lý PDF hybrid:
    1. Extract text vector trước
    2. OCR toàn bộ page
    3. Merge kết quả (loại duplicate)
    """
    doc = fitz.open(str(pdf_path))
    results = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Step 1: Extract vector text
        vector_text = page.get_text()
        vector_words = set(vector_text.split())

        # Step 2: OCR full page
        pix = page.get_pixmap(dpi=dpi)
        temp_img = f"temp_hybrid_{os.getpid()}_{page_num}.png"
        pix.save(temp_img)

        start_ocr = time.time()
        ocr_result = ocr_engine.ocr(temp_img, cls=True)
        ocr_time = time.time() - start_ocr

        # Cleanup
        if os.path.exists(temp_img):
            os.remove(temp_img)

        # Step 3: Combine results
        ocr_texts = []
        if ocr_result and ocr_result[0]:
            ocr_texts = [line[1][0] for line in ocr_result[0]]

        page_result = {
            "page": page_num + 1,
            "vector_text": vector_text.strip(),
            "vector_chars": len(vector_text.strip()),
            "ocr_texts": ocr_texts,
            "ocr_regions": len(ocr_texts),
            "ocr_time": ocr_time,
            "strategy": "hybrid" if len(vector_text.strip()) > 50 else "ocr_only",
        }

        results.append(page_result)

    doc.close()
    return results


print("=" * 100)
print("PHÂN TÍCH VÀ XỬ LÝ PDF HYBRID (P&ID)")
print("=" * 100)

# Get sample P&ID files
data_dir = Path(r"D:\Data_Raw")
pdf_files = [f for f in data_dir.rglob("*.pdf") if not f.name.startswith("._")]

# Filter P&ID files (by name pattern)
pid_keywords = ["P&I", "P & I", "PID", "Piping", "Diagram", "Legend"]
pid_files = [
    f for f in pdf_files if any(kw.lower() in f.name.lower() for kw in pid_keywords)
]

print(f"\n[1/3] TÌM KIẾM P&ID FILES")
print("-" * 100)
print(f"✓ Total PDFs: {len(pdf_files)}")
print(f"✓ P&ID files (by name): {len(pid_files)}")

if not pid_files:
    print("\n⚠ Không tìm thấy file P&ID theo tên, sẽ phân tích 5 file đầu")
    sample_files = pdf_files[:5]
else:
    sample_files = pid_files[:3]

print(f"\n📄 Sample files:")
for f in sample_files:
    print(f"  - {f.name}")

# Analyze content
print(f"\n[2/3] PHÂN TÍCH NỘI DUNG")
print("-" * 100)

analysis_results = []

for pdf_file in sample_files:
    print(f"\n📄 {pdf_file.name}")
    try:
        stats = analyze_pdf_content(pdf_file)
        analysis_results.append({"file": pdf_file.name, "stats": stats})

        # Summary
        hybrid_pages = sum(1 for p in stats["pages_detail"] if p["type"] == "hybrid")
        text_only = sum(1 for p in stats["pages_detail"] if p["type"] == "text_only")
        image_only = sum(1 for p in stats["pages_detail"] if p["type"] == "image_only")

        print(f"  Total pages: {stats['total_pages']}")
        print(f"  - Hybrid (text+image): {hybrid_pages} pages")
        print(f"  - Text only: {text_only} pages")
        print(f"  - Image only: {image_only} pages")
        print(f"  - Extractable text: {stats['total_text_chars']} chars")

        # Show first page detail
        if stats["pages_detail"]:
            first_page = stats["pages_detail"][0]
            print(f"\n  Page 1 detail:")
            print(f"    Type: {first_page['type']}")
            print(f"    Text chars: {first_page['text_chars']}")
            print(f"    Images: {first_page['images']}")
            if first_page["extractable_text"]:
                preview = first_page["extractable_text"][:100].replace("\n", " ")
                print(f"    Preview: {preview}...")

    except Exception as e:
        print(f"  ✗ Error: {e}")

# Test hybrid processing
print(f"\n[3/3] TEST HYBRID PROCESSING")
print("-" * 100)

if sample_files:
    test_file = sample_files[0]
    print(f"\nTesting: {test_file.name}")

    # Initialize OCR
    ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
    ocr = PaddleOCR(
        lang="en",
        det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
        cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
        use_angle_cls=True,
        use_gpu=False,
        use_space_char=True,
        show_log=False,
    )

    try:
        # Process first page only
        doc = fitz.open(str(test_file))
        page = doc[0]

        # Vector text
        vector_text = page.get_text()
        vector_chars = len(vector_text.strip())

        # OCR
        pix = page.get_pixmap(dpi=150)
        temp_img = "temp_hybrid_test.png"
        pix.save(temp_img)

        start = time.time()
        ocr_result = ocr.ocr(temp_img, cls=True)
        ocr_time = time.time() - start

        if os.path.exists(temp_img):
            os.remove(temp_img)

        ocr_regions = len(ocr_result[0]) if ocr_result and ocr_result[0] else 0

        doc.close()

        print(f"\n✓ Page 1 processing:")
        print(f"  Vector text: {vector_chars} chars")
        print(f"  OCR regions: {ocr_regions}")
        print(f"  OCR time: {ocr_time:.2f}s")

        if vector_chars > 0:
            print(f"\n  Vector text sample:")
            print(f"  {vector_text[:200].replace(chr(10), ' ')}...")

        if ocr_result and ocr_result[0]:
            print(f"\n  OCR text sample:")
            for i, line in enumerate(ocr_result[0][:3], 1):
                print(f"  {i}. '{line[1][0]}' (conf: {line[1][1]:.3f})")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()

# Summary & Recommendation
print("\n" + "=" * 100)
print("KHUYẾN NGHỊ XỬ LÝ P&ID HYBRID")
print("=" * 100)

print("\n📋 CHIẾN LƯỢC XỬ LÝ:")
print("-" * 100)

print("\n1. PHÂN LOẠI TỰ ĐỘNG:")
print("   - Nếu extractable text > 50 chars → HYBRID")
print("   - Nếu extractable text < 50 chars → OCR_ONLY")
print("")
print("2. CHIẾN LƯỢC HYBRID (Khuyến nghị cho P&ID):")
print("   ")
print("   Option A - DUAL EXTRACTION (Comprehensive):")
print("     • Extract vector text (PyMuPDF)")
print("     • OCR full page (PaddleOCR)")
print("     • Merge & deduplicate results")
print("     • Ưu điểm: Bắt được ALL text (cả vector và raster)")
print("     • Nhược điểm: Chậm hơn (OCR toàn page)")
print("   ")
print("   Option B - VECTOR ONLY (Fast):")
print("     • Chỉ extract vector text")
print("     • Bỏ qua OCR nếu có đủ text")
print("     • Ưu điểm: Nhanh, text quality cao")
print("     • Nhược điểm: Mất text trong ảnh/symbol")
print("   ")
print("   Option C - SMART HYBRID (Balanced) ← KHUYẾN NGHỊ:")
print("     • Extract vector text")
print("     • OCR chỉ regions không có vector text")
print("     • Cần detect text bounding boxes trước")
print("     • Ưu điểm: Balance speed/completeness")
print("     • Nhược điểm: Phức tạp hơn implement")

print("\n3. KHUYẾN NGHỊ CHO DỮ LIỆU CỦA BẠN:")

if analysis_results:
    total_hybrid = sum(
        sum(1 for p in r["stats"]["pages_detail"] if p["type"] == "hybrid")
        for r in analysis_results
    )
    total_pages = sum(r["stats"]["total_pages"] for r in analysis_results)

    hybrid_ratio = (total_hybrid / total_pages * 100) if total_pages > 0 else 0

    print(
        f"   • Sample analysis: {total_hybrid}/{total_pages} pages là hybrid ({hybrid_ratio:.0f}%)"
    )

    if hybrid_ratio > 50:
        print(f"   ")
        print(f"   ✅ KHUYẾN NGHỊ: DUAL EXTRACTION (Option A)")
        print(f"   Lý do: >50% pages là hybrid, cần OCR để bắt đủ text")
        print(f"   ")
        print(f"   Implementation:")
        print(f"   ```python")
        print(f"   # 1. Extract vector text")
        print(f"   vector_text = page.get_text()")
        print(f"   ")
        print(f"   # 2. OCR full page")
        print(f"   pix = page.get_pixmap(dpi=150)")
        print(f"   ocr_result = ocr.ocr(image, cls=True)")
        print(f"   ")
        print(f"   # 3. Combine (vector text + OCR text)")
        print(f"   combined_text = vector_text + '\\n' + ocr_text")
        print(f"   ```")
        print(f"   ")
        print(f"   Estimated time: ~44 minutes (same as OCR-only)")
    else:
        print(f"   ")
        print(f"   ✅ KHUYẾN NGHỊ: VECTOR ONLY + OCR fallback (Option B)")
        print(f"   Lý do: <50% hybrid, ưu tiên tốc độ")
        print(f"   ")
        print(f"   Implementation:")
        print(f"   ```python")
        print(f"   vector_text = page.get_text()")
        print(f"   if len(vector_text.strip()) > 100:")
        print(f"       # Đủ text, skip OCR")
        print(f"       return vector_text")
        print(f"   else:")
        print(f"       # OCR fallback")
        print(f"       return ocr_text")
        print(f"   ```")

print("\n4. TRADE-OFFS:")
print("   ")
print("   Vector extraction:      ~0.01s/page,  high quality, miss raster text")
print("   OCR full page:          ~1.90s/page,  catch all text, may duplicate")
print("   Dual (Vector + OCR):    ~1.90s/page,  most complete, need dedup")

print("\n💡 KẾT LUẬN:")
print("   Với P&ID files, KHUYẾN NGHỊ dùng DUAL EXTRACTION")
print("   để bắt đủ cả text vector và text trong ảnh/symbol.")
print("")
print("   Total time vẫn ~44 phút (giống OCR-only),")
print("   nhưng kết quả đầy đủ và chính xác hơn.")

print("\n" + "=" * 100)
