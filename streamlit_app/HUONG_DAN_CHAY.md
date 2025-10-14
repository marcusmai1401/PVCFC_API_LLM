# Hướng dẫn Chạy Streamlit App

## 🚀 Cách chạy ứng dụng

### 1. Mở PowerShell/Terminal tại thư mục streamlit_app:
```powershell
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC\streamlit_app"
```

### 2. Chạy Streamlit:
```powershell
python -m streamlit run app.py
```

hoặc

```powershell
streamlit run app.py
```

### 3. Mở trình duyệt:
Ứng dụng sẽ tự động mở tại: `http://localhost:8501`

---

## 🔧 Cấu hình (Tùy chọn)

### Thiết lập API Base URL:
```powershell
# Windows PowerShell
$env:PVCFC_API_BASE_URL = "http://localhost:8000"

# Hoặc thêm vào file .env
PVCFC_API_BASE_URL=http://localhost:8000
```

### Chạy headless (không mở browser):
```powershell
streamlit run app.py --server.headless true
```

### Chạy trên port khác:
```powershell
streamlit run app.py --server.port 8502
```

---

## 📋 Các tính năng đã bật sẵn

✅ **Vision Generation**: Luôn bật (tự động nhận diện ảnh/bảng biểu)
✅ **Re-ranking**: Luôn bật (cải thiện độ chính xác)
✅ **Citation với source**: Tự động hiển thị nguồn trích dẫn

---

## 🎯 Sử dụng cơ bản

1. **Nhập câu hỏi** vào text area lớn
2. **Chọn ngôn ngữ**: vi (Tiếng Việt) hoặc en (English)
3. **Điều chỉnh Max Context Chunks**:
   - Mặc định: 8 (đủ cho hầu hết câu hỏi)
   - Câu hỏi phức tạp: 12-15
   - Câu hỏi đơn giản: 5
4. **Tùy chọn Advanced** (nếu cần):
   - HyDE: Bật cho câu hỏi phức tạp
   - BM25/FAISS Top-K: Giữ mặc định 50
   - IEEE Citations: Bật cho citation style chuẩn
5. **Click 🚀 Run Query**

---

## 🐛 Troubleshooting

### Lỗi "Cannot import name..."
```powershell
# Kiểm tra syntax
python -m py_compile components/query_lab_improved.py
```

### App không kết nối được API
```powershell
# Kiểm tra backend đang chạy
curl http://localhost:8000/health

# Hoặc kiểm tra trong app, xem console log
```

### Port đã được sử dụng
```powershell
# Dừng process đang chạy hoặc dùng port khác
streamlit run app.py --server.port 8502
```

---

## 📚 Tài liệu bổ sung

- **Giải thích chi tiết**: `UI_EXPLANATION_VI.md`
- **Tóm tắt thay đổi**: `THAY_DOI_UI_TOM_TAT.md`
- **Fix indentation**: `INDENTATION_FIX.md`
- **Commit message**: `COMMIT_MESSAGE.txt`

---

## ✅ Kiểm tra phiên bản hiện tại

```powershell
# Kiểm tra app có compile OK không
python -m py_compile app.py components/query_lab_improved.py

# Kiểm tra import
python -c "import sys; sys.path.insert(0, '.'); from components.query_lab_improved import render; print('OK')"
```

---

**Cập nhật**: 2025-10-13
**Phiên bản**: Simplified UI with Vision & Re-ranking always enabled
