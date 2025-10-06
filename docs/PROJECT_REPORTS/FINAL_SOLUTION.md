# Giải pháp cuối cùng cho PP-OCRv5

## Tình trạng hiện tại

✅ **Đã hoàn thành:**
- Patch `static_infer.py` để hỗ trợ PIR mode
- Upgrade/downgrade PaddlePaddle đến 2.6.2
- PP-OCRv5 models có cả `.pdmodel` VÀ `.json` format

❌ **Vấn đề:**
- PaddleOCR 3.2.0 **BẮT BUỘC** phải có document preprocessor
- Document preprocessor CHỈ có `.json` format (không có `.pdmodel`)
- `.json` models KHÔNG hoạt động với Paddle 2.6.2

## Giải pháp

### **Option 1: Downgrade PaddleOCR (Khuyến nghị)**

Quay lại PaddleOCR 2.7.x hoặc 2.8.x - phiên bản KHÔNG bắt buộc document preprocessor:

```bash
pip uninstall paddleocr paddlex
pip install paddleocr==2.7.3
```

Sau đó test:

```python
from paddleocr import PaddleOCR

ROOT = r"C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\artifacts\ocr\paddle\ppocrv5"
det_dir = rf"{ROOT}\det\PP-OCRv5_server_det_infer"
rec_dir = rf"{ROOT}\rec\latin_PP-OCRv5_mobile_rec_infer"
cls_dir = rf"{ROOT}\cls\ch_ppocr_mobile_v2.0_cls_infer"

ocr = PaddleOCR(
    det_model_dir=det_dir,
    rec_model_dir=rec_dir,
    cls_model_dir=cls_dir,
    use_angle_cls=True,
    use_gpu=True
)

result = ocr.ocr('image.jpg', cls=True)
```

### **Option 2: Xóa cache document preprocessor**

Xóa hoàn toàn để force PaddleOCR bỏ qua:

```bash
Remove-Item -Recurse -Force "C:\Users\Admin\.paddlex\official_models\PP-LCNet_x1_0_doc_ori"
Remove-Item -Recurse -Force "C:\Users\Admin\.paddlex\official_models\UVDoc"
```

Sau đó chỉnh sửa source code PaddleOCR để skip doc preprocessor (phức tạp).

### **Option 3: Đợi PaddlePaddle 3.0 stable**

Khi Paddle 3.0 stable release, tất cả sẽ hoạt động với patch đã có.

## Khuyến nghị NGAY BÂY GIỜ

**Downgrade PaddleOCR về 2.7.3:**

```powershell
python -m pip uninstall -y paddleocr paddlex
python -m pip install paddleocr==2.7.3
```

Sau đó test với PP-OCRv5 models của bạn!

## Files quan trọng

- ✅ `patch_static_infer_pir.py` - Script đã patch (giữ lại để sau này)
- ✅ PP-OCRv5 models (`.pdmodel` format) đã sẵn sàng
- ⚠️ Cần downgrade PaddleOCR để sử dụng ngay

---
**Cập nhật:** 2025-10-02
**Trạng thái:** Cần downgrade PaddleOCR hoặc đợi Paddle 3.0 stable
