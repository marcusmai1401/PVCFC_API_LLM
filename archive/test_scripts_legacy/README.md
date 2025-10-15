# 🧪 Test Scripts Collection

Tập hợp các script test và debug được di chuyển từ root directory.

---

## 📁 DANH SÁCH FILES

### 🔍 **Retrieval & Search Testing**
- **`debug_retrieval_vi.py`** - Debug retrieval với Vietnamese queries
  - Test QueryTransformer với HyDE
  - So sánh kết quả VI vs EN
  - Status: ✅ ACTIVE (dùng cho debugging)

### 🌐 **API Testing**
- **`test_api.py`** - Test API connectivity và start server
  - Tự động start API server
  - Test /healthz và /ask endpoints
  - Status: ⚠️ CŨ (nên dùng test_api_live.py)

- **`test_api_debug.py`** - Debug /ask endpoint validation
  - Test nhiều payload variants
  - Hiển thị validation errors chi tiết
  - Status: ✅ ACTIVE (debug validation)

- **`test_api_live.py`** - Test live API endpoints (comprehensive)
  - Test tất cả endpoints: /healthz, /metrics, /index-stats, /ask, /locate, /report
  - Không tự start server (cần server chạy trước)
  - Status: ✅ **RECOMMENDED** (main API test)

### 🧠 **LLM & Gemini Testing**
- **`test_gemini_direct.py`** - Test Gemini API trực tiếp
  - Bypass app logic, test raw API
  - Debug response structure
  - Status: ✅ ACTIVE (debug Gemini issues)

### 🖼️ **OCR Testing**
- **`test_ocr.py`** - Test OCR functionality
  - Kiểm tra Tesseract installation
  - Test PDF processing với OCR
  - Status: ✅ ACTIVE

- **`test_ocr_status.py`** - OCR status comprehensive check
  - Display OCR config status
  - Test PDF processing với/không OCR
  - Status: ✅ **RECOMMENDED** (main OCR test)

### 📄 **PDF & Document Testing**
- **`test_page_loading.py`** - Test load full page PDF
  - Kiểm tra doc_id_map
  - Test PDF loading trực tiếp
  - Test retriever upgrade
  - Status: ✅ ACTIVE (debug page loading)

- **`test_fix_indoc.py`** - Test fix cho in-document questions
  - Test queries trong document
  - Test out-of-document queries
  - Status: ⚠️ CŨ (issue đã fix)

### 🖥️ **UI & System Testing**
- **`test_phase_completion.py`** - Test Phase 0 & 1 completion
  - Check app.py structure
  - Verify navigation và routing
  - Status: ⚠️ CŨ (phases đã hoàn thành)

- **`test_system_status.py`** - Test System Status component
  - Test API endpoints
  - Test UI component existence
  - Status: ✅ ACTIVE

- **`test_system_status_api.py`** - System Status API integration
  - Test backend running/down scenarios
  - Status: ✅ ACTIVE

- **`test_ui_citations_complete.py`** - Test UI Citations features
  - Verify pdf_path usage
  - Check expander và buttons
  - Status: ⚠️ CŨ (feature đã hoàn thành)

### 📝 **Logging Testing**
- **`test_logging_system.py`** - Test UI event logging
  - Test session IDs
  - Test event logging
  - Test sensitive data redaction
  - Status: ✅ ACTIVE

### 🌏 **Vietnamese/Language Testing**
- **`test_vietnamese_debug.py`** - Debug Vietnamese queries
  - Test Vietnamese vs English comparison
  - Rich output formatting
  - Status: ✅ ACTIVE

---

## 📊 STATUS SUMMARY

### ✅ **ACTIVE - Nên giữ lại**
```
✅ debug_retrieval_vi.py       - Debug retrieval logic
✅ test_api_debug.py            - Debug API validation
✅ test_api_live.py             - Main API testing (RECOMMENDED)
✅ test_gemini_direct.py        - Debug Gemini issues
✅ test_ocr.py                  - OCR basic test
✅ test_ocr_status.py           - OCR comprehensive (RECOMMENDED)
✅ test_page_loading.py         - Debug page loading
✅ test_system_status.py        - System status check
✅ test_system_status_api.py    - API integration test
✅ test_logging_system.py       - Logging test
✅ test_vietnamese_debug.py     - Vietnamese debug
```

### ⚠️ **CŨ - Có thể archive/xóa**
```
⚠️ test_api.py                  - Thay bằng test_api_live.py
⚠️ test_fix_indoc.py            - Issue đã được fix
⚠️ test_phase_completion.py     - Phases đã hoàn thành
⚠️ test_ui_citations_complete.py - Feature đã hoàn thành
```

---

## 🚀 CÁCH SỬ DỤNG

### Test API (RECOMMENDED)
```bash
# 1. Start API server trước
python -m uvicorn app.main:app --port 8000

# 2. Chạy test (terminal khác)
python scripts/test_scripts/test_api_live.py
```

### Debug Retrieval
```bash
python scripts/test_scripts/debug_retrieval_vi.py
```

### Test OCR Status
```bash
python scripts/test_scripts/test_ocr_status.py
```

### Debug Vietnamese Queries
```bash
pip install rich  # nếu chưa có
python scripts/test_scripts/test_vietnamese_debug.py
```

### Test Gemini Direct
```bash
python scripts/test_scripts/test_gemini_direct.py
```

---

## 🧹 CLEANUP RECOMMENDATIONS

### Có thể xóa ngay
```bash
# Những file này đã outdated và không còn cần thiết
Remove-Item scripts/test_scripts/test_api.py
Remove-Item scripts/test_scripts/test_fix_indoc.py
Remove-Item scripts/test_scripts/test_phase_completion.py
Remove-Item scripts/test_scripts/test_ui_citations_complete.py
```

### Nên giữ lại
- Tất cả các file ACTIVE khác vẫn hữu ích cho debugging

---

## 📂 STRUCTURE

```
scripts/
├── test_scripts/              ← Bạn đang ở đây
│   ├── README.md             ← File này
│   ├── debug_retrieval_vi.py
│   ├── test_api_*.py
│   ├── test_ocr*.py
│   ├── test_gemini_direct.py
│   ├── test_logging_system.py
│   ├── test_page_loading.py
│   ├── test_system_status*.py
│   └── test_vietnamese_debug.py
│
├── examples/                  ← Example scripts
│   └── example_gemini_usage.py
│
└── utilities/                 ← Utility scripts
    └── fix_hosts.py
```

---

## 💡 TIPS

1. **Khi gặp lỗi API**: Chạy `test_api_live.py` để check tất cả endpoints
2. **Khi gặp lỗi Retrieval**: Chạy `debug_retrieval_vi.py` để xem query transform
3. **Khi gặp lỗi Vietnamese**: Chạy `test_vietnamese_debug.py` với rich output
4. **Khi gặp lỗi OCR**: Chạy `test_ocr_status.py` để check setup
5. **Khi gặp lỗi Gemini**: Chạy `test_gemini_direct.py` để bypass app logic

---

**Tổng hợp**: 15 files test được di chuyển từ root
**Ngày tổng hợp**: 2025-10-01
**Status**: ✅ Đã tổ chức gọn gàng
