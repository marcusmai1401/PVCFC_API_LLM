"""
KHẢO SÁT NGÔN NGỮ ĐẦU RA OCR - BASELINE
Phân tích %Latin vs %CJK trên mẫu đại diện từ D:\Data_Raw
"""

import json
import os
import random
import sys
import time
import unicodedata
from pathlib import Path

import paddle
from paddleocr import PaddleOCR


def classify_text(text):
    """Phân loại text thành Latin, CJK, Other"""
    if not text or not text.strip():
        return "EMPTY"

    latin_count = 0
    cjk_count = 0
    other_count = 0

    for char in text:
        if char.isspace():
            continue
        try:
            name = unicodedata.name(char, "")
            if "LATIN" in name or "DIGIT" in name:
                latin_count += 1
            elif any(x in name for x in ["CJK", "HIRAGANA", "KATAKANA", "HANGUL"]):
                cjk_count += 1
            else:
                other_count += 1
        except:
            other_count += 1

    total = latin_count + cjk_count + other_count
    if total == 0:
        return "EMPTY"

    latin_pct = latin_count / total
    cjk_pct = cjk_count / total

    if latin_pct > 0.6:
        return "LATIN"
    elif cjk_pct > 0.6:
        return "CJK"
    else:
        return "MIXED"


def process_pdf_page(pdf_path, page_num=0, dpi=150):
    """Chuyển 1 trang PDF thành image"""
    import fitz

    doc = fitz.open(str(pdf_path))
    num_pages = len(doc)
    if page_num >= num_pages:
        page_num = 0
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)

    temp_img = f"temp_survey_{os.getpid()}_{page_num}.png"
    pix.save(temp_img)
    doc.close()

    return temp_img, num_pages


def process_tif_page(tif_path):
    """Chuyển TIF thành temp file (hoặc dùng trực tiếp)"""
    # PaddleOCR có thể đọc TIF trực tiếp
    return str(tif_path), 1


print("=" * 100)
print("KHẢO SÁT NGÔN NGỮ ĐẦU RA OCR - BASELINE")
print("=" * 100)

# Initialize OCR (CPU mode)
print("\n[1/4] KHỞI TẠO PP-OCRv5")
print("-" * 100)

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"

try:
    ocr = PaddleOCR(
        lang="en",  # Sử dụng PP-OCRv4 English official model
        det_model_dir=rf"{ROOT}\det\PP-OCRv5_server_det_infer",
        cls_model_dir=rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer",
        use_angle_cls=True,
        use_gpu=False,
        use_space_char=True,
        show_log=False,
    )
    print(f"✓ Model: en_PP-OCRv4_rec (English official)")
    print(f"✓ Mode: CPU")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Lấy mẫu files
print("\n[2/4] LẤY MẪU DỮ LIỆU")
print("-" * 100)

data_dir = Path(r"D:\Data_Raw")
pdf_files = list(data_dir.rglob("*.pdf"))
tif_files = list(data_dir.rglob("*.tif")) + list(data_dir.rglob("*.tiff"))

# Lọc bỏ file MacOSX temp
pdf_files = [f for f in pdf_files if not f.name.startswith("._")]
tif_files = [f for f in tif_files if not f.name.startswith("._")]

# Chọn 10 files đại diện (6 PDF + 4 TIF)
random.seed(42)
sample_pdfs = random.sample(pdf_files, min(6, len(pdf_files)))
sample_tifs = random.sample(tif_files, min(4, len(tif_files)))
samples = sample_pdfs + sample_tifs

print(f"✓ Tổng: {len(pdf_files)} PDF, {len(tif_files)} TIF")
print(f"✓ Mẫu: {len(sample_pdfs)} PDF + {len(sample_tifs)} TIF = {len(samples)} files")

# Khảo sát
print("\n[3/4] KHẢO SÁT OCR")
print("-" * 100)

results = []
temp_files = []

for idx, file_path in enumerate(samples, 1):
    print(f"\n[{idx}/{len(samples)}] {file_path.name}")
    print("  ", end="")

    try:
        # Prepare image
        if file_path.suffix.lower() == ".pdf":
            temp_img, total_pages = process_pdf_page(file_path, page_num=0, dpi=150)
            temp_files.append(temp_img)
            file_type = "PDF"
        else:
            temp_img, total_pages = process_tif_page(file_path)
            file_type = "TIF"

        # OCR
        start = time.time()
        result = ocr.ocr(temp_img, cls=True)
        ocr_time = time.time() - start

        # Analyze
        if result and result[0]:
            texts = [line[1][0] for line in result[0]]
            confidences = [line[1][1] for line in result[0]]

            classifications = [classify_text(t) for t in texts]

            latin_count = classifications.count("LATIN")
            cjk_count = classifications.count("CJK")
            mixed_count = classifications.count("MIXED")
            empty_count = classifications.count("EMPTY")

            total_valid = len(classifications) - empty_count

            if total_valid > 0:
                latin_pct = (latin_count / total_valid) * 100
                cjk_pct = (cjk_count / total_valid) * 100
                mixed_pct = (mixed_count / total_valid) * 100
            else:
                latin_pct = cjk_pct = mixed_pct = 0

            avg_conf = sum(confidences) / len(confidences) if confidences else 0

            # Ví dụ tiêu biểu
            latin_samples = [t for t, c in zip(texts, classifications) if c == "LATIN"][
                :2
            ]
            cjk_samples = [t for t, c in zip(texts, classifications) if c == "CJK"][:2]

            result_data = {
                "file": file_path.name,
                "type": file_type,
                "total_regions": len(texts),
                "latin_pct": round(latin_pct, 1),
                "cjk_pct": round(cjk_pct, 1),
                "mixed_pct": round(mixed_pct, 1),
                "avg_confidence": round(avg_conf, 3),
                "ocr_time": round(ocr_time, 2),
                "latin_samples": latin_samples,
                "cjk_samples": cjk_samples,
            }

            results.append(result_data)

            print(
                f"✓ {len(texts)} regions | Latin: {latin_pct:.0f}% | CJK: {cjk_pct:.0f}% | Conf: {avg_conf:.2f} | {ocr_time:.1f}s"
            )
        else:
            print("⚠ No text detected")

    except Exception as e:
        print(f"✗ Error: {e}")

# Cleanup
for temp_file in temp_files:
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except:
            pass

# Tổng kết
print("\n[4/4] TỔNG KẾT")
print("=" * 100)

if results:
    total_regions = sum(r["total_regions"] for r in results)

    # Tính %Latin/%CJK tổng thể (theo số regions)
    total_latin = sum(r["total_regions"] * r["latin_pct"] / 100 for r in results)
    total_cjk = sum(r["total_regions"] * r["cjk_pct"] / 100 for r in results)
    total_mixed = sum(r["total_regions"] * r["mixed_pct"] / 100 for r in results)

    overall_latin_pct = (total_latin / total_regions) * 100
    overall_cjk_pct = (total_cjk / total_regions) * 100
    overall_mixed_pct = (total_mixed / total_regions) * 100

    avg_confidence = sum(r["avg_confidence"] for r in results) / len(results)
    avg_time = sum(r["ocr_time"] for r in results) / len(results)

    print(f"\n📊 TỔNG QUAN ({len(results)} files, {total_regions} regions)")
    print("-" * 100)
    print(
        f"  Latin:       {overall_latin_pct:6.1f}%  {'✓ ĐẠT' if overall_latin_pct >= 60 else '✗ THẤP'}"
    )
    print(f"  CJK:         {overall_cjk_pct:6.1f}%")
    print(f"  Mixed:       {overall_mixed_pct:6.1f}%")
    print(f"  Confidence:  {avg_confidence:6.3f}")
    print(f"  Avg time:    {avg_time:6.2f}s/page")

    print(f"\n📋 CHI TIẾT TỪNG FILE")
    print("-" * 100)
    print(
        f"{'File':<50} {'Type':<6} {'Regions':<8} {'Latin%':<8} {'CJK%':<8} {'Conf':<8}"
    )
    print("-" * 100)
    for r in results:
        print(
            f"{r['file']:<50} {r['type']:<6} {r['total_regions']:<8} {r['latin_pct']:<8.1f} {r['cjk_pct']:<8.1f} {r['avg_confidence']:<8.3f}"
        )

    print(f"\n📝 VÍ DỤ LATIN")
    print("-" * 100)
    all_latin = []
    for r in results:
        all_latin.extend(r["latin_samples"])
    for i, sample in enumerate(all_latin[:5], 1):
        print(f"  {i}. {sample}")

    print(f"\n🈚 VÍ DỤ CJK")
    print("-" * 100)
    all_cjk = []
    for r in results:
        all_cjk.extend(r["cjk_samples"])
    for i, sample in enumerate(all_cjk[:5], 1):
        print(f"  {i}. {sample}")

    # Kết luận
    print("\n" + "=" * 100)
    print("KẾT LUẬN BASELINE")
    print("=" * 100)

    if overall_latin_pct >= 60:
        print(
            f"✅ Latin đạt {overall_latin_pct:.1f}% (≥60%) - Cấu hình hiện tại phù hợp"
        )
        print(
            f"   Model 'latin_PP-OCRv5_mobile_rec_infer' hoạt động tốt cho dữ liệu EN/VI"
        )
    else:
        print(
            f"⚠️  Latin chỉ {overall_latin_pct:.1f}% (<60%) - Cần kiểm tra model hoặc dữ liệu"
        )
        print(
            f"   CJK chiếm {overall_cjk_pct:.1f}% - Có thể model đang nhận dạng sai ngôn ngữ"
        )
        print(f"   Khuyến nghị: Kiểm tra rec_char_dict hoặc thử model khác")

    # Save results
    output_file = "ocr_language_survey_baseline.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": {
                    "latin_pct": round(overall_latin_pct, 1),
                    "cjk_pct": round(overall_cjk_pct, 1),
                    "mixed_pct": round(overall_mixed_pct, 1),
                    "avg_confidence": round(avg_confidence, 3),
                    "avg_time": round(avg_time, 2),
                    "total_files": len(results),
                    "total_regions": total_regions,
                },
                "files": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n💾 Kết quả lưu tại: {output_file}")

else:
    print("⚠️ Không có kết quả để phân tích")
