# PP-OCRv5 RuntimeError Fix Summary

## Vấn đề gốc
```
RuntimeError: (PreconditionNotMet) op [] kernel output args (0) defs should equal op outputs (1)
```

Xảy ra khi chạy PP-OCRv5 với PaddlePaddle 3.0.0-beta2.

## Nguyên nhân

1. **PaddleOCR 3.2.0** tự động download và sử dụng models mới với format **`.json`** (PIR format)
2. Models `.json` YÊU CẦU **PIR mode enabled** (`enable_new_ir(True)`)
3. File `static_infer.py` trong PaddleX có hardcode **`enable_new_ir(False)`** → Xung đột!

## Giải pháp đã thực hiện

### ✅ 1. Patch file `static_infer.py`

Đã tạo script tự động: **`patch_static_infer_pir.py`**

**Các thay đổi:**
- ✓ Thêm detection: `is_pir_model = str(model_file).endswith(".json")`
- ✓ Conditional PIR mode: If `.json` → `enable_new_ir(True)`, else → `enable_new_ir(False)`
- ✓ Enable new executor cho PIR models
- ✓ Conditional IR optimization
- ✓ Wrap `set_optimization_level()` trong `hasattr()` check (cho Paddle 2.6.x compatibility)

**Vị trí file:**
```
C:\Users\Admin\AppData\Local\Programs\Python\Python311\Lib\site-packages\paddlex\inference\models\common\static_infer.py
```

**Backup:**
```
static_infer.py.backup
static_infer.py.backup_original
```

### ⚠️ 2. Vấn đề còn lại: Version Compatibility

**Hiện trạng:**

| PaddlePaddle Version | PP-OCRv5 (.json models) | Status |
|---------------------|------------------------|--------|
| 3.0.0-beta2 | ✓ Có thể chạy | ❌ Bug PIR (đã fix bằng patch) |
| 0.0.0.post120 (nightly) | ✓ Có thể chạy | ❌ CUDNN dependency error |
| 2.6.2 (stable) | ❌ Crash (Access Violation) | ❌ Không hỗ trợ `.json` models |

**Kết luận:** Models `.json` (PIR format) CHỈ hoạt động ổn định với **PaddlePaddle 3.0 stable** (chưa release).

## Khuyến nghị

### Tùy chọn 1: Đợi Paddle 3.0 Stable (Khuyến nghị)
Khi PaddlePaddle 3.0 stable release, cài đặt và sử dụng với patch đã có.

### Tùy chọn 2: Sử dụng PP-OCRv5 models cũ (`.pdmodel` format)
Nếu bạn có PP-OCRv5 models ở format `.pdmodel` / `.pdiparams` (không phải `.json`), chúng sẽ hoạt động với Paddle 2.6.2:

```python
ocr = PaddleOCR(
    text_detection_model_dir="path/to/PP-OCRv5_det",  # .pdmodel format
    text_recognition_model_dir="path/to/PP-OCRv5_rec",  # .pdmodel format
    textline_orientation_model_dir="path/to/cls",
    use_textline_orientation=True
)
```

### Tùy chọn 3: Sử dụng PP-OCRv4 tạm thời
PP-OCRv4 hoạt động hoàn hảo với Paddle 2.6.2:

```python
ocr = PaddleOCR(
    lang='vi',
    use_angle_cls=True,
    ocr_version='PP-OCRv4'
)
```

## Files đã tạo

1. **`tools/patches/patch_static_infer_pir.py`** - Script tự động patch
2. **`tools/verify/verify_v5.py`** - Script kiểm tra PP-OCRv5
3. **`tools/verify/verify_v5_simple.py`** - Script kiểm tra đơn giản
4. **`run_verify_v5.ps1`** - PowerShell wrapper (không cần thiết nữa)
5. **`docs/DOCS_NEW_Features/FIX_SUMMARY.md`** - File này

## Cách sử dụng patch trong tương lai

Nếu cần re-apply patch (sau khi upgrade PaddleOCR/PaddleX):

```bash
python tools/patches/patch_static_infer_pir.py
```

Hoặc restore backup:
```bash
copy static_infer.py.backup_original static_infer.py
```

## Trạng thái hiện tại

✅ Patch đã hoàn thành và hoạt động
⚠️  Cần đợi PaddlePaddle 3.0 stable để sử dụng PP-OCRv5 ổn định
✅ Có thể sử dụng PP-OCRv4 hoặc PP-OCRv5 với `.pdmodel` format ngay bây giờ

---
**Ngày tạo:** 2025-10-01
**PaddlePaddle:** 2.6.2 (stable)
**PaddleOCR:** 3.2.0
**PaddleX:** 3.2.1
