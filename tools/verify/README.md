# ✅ Verification Tools

Scripts để verify và test các components của hệ thống.

## Scripts

- **verify_v5.py** - Main verification script cho PP-OCRv5
- **verify_v5_simple.py** - Simplified version cho quick check
- **verify_v5_no_doc.py** - Verify OCR without document loading
- **verify_paddleocr_v5.py** - Comprehensive PaddleOCR v5 verification
- **verify_page15.py** - Verify specific page (page 15) processing

## Cách sử dụng

### Quick verification
```bash
python tools/verify/verify_v5_simple.py
```

### Full verification (recommended)
```bash
python tools/verify/verify_v5.py
```

### Hoặc dùng launcher script
```bash
.\run_verify_v5.ps1
```
*(Script này tự động set PIR flags và chạy verify_v5.py)*

## Output mong đợi

✅ GPU/CPU initialization
✅ OCR model loading
✅ Text detection và recognition
✅ Confidence scores > 0.85

## Troubleshooting

- **Lỗi cuDNN**: Dùng CPU mode hoặc install cuDNN 8.6.0
- **Model not found**: Check `artifacts/ocr/paddle/ppocrv5/` paths
- **PIR errors**: Dùng `run_verify_v5.ps1` thay vì chạy trực tiếp
