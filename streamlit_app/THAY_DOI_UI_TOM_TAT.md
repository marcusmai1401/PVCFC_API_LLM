# Tóm tắt Thay đổi UI - Query Lab

## ✅ Đã thực hiện

### 1. Giải thích các khái niệm

#### **HyDE (Hypothetical Document Expansion)**
- **Nghĩa**: Tạo "tài liệu giả định" để tìm kiếm thay vì dùng câu hỏi trực tiếp
- **Khi dùng**: Câu hỏi phức tạp, cần độ chính xác cao
- **Trade-off**: Chậm hơn nhưng chính xác hơn

#### **Max Context Chunks**
- **Nghĩa**: Số đoạn văn bản (chunks) lấy từ tài liệu để LLM đọc và trả lời
- **Mặc định**: 8 chunks
- **Khuyến nghị**:
  - 3-5: Câu hỏi đơn giản
  - 8-10: Câu hỏi thường
  - 15-20: Câu hỏi phức tạp

---

### 2. Ẩn và bật mặc định Vision & Re-ranking

| Tính năng | Trước | Sau |
|-----------|-------|-----|
| **Vision Generation** | Checkbox cho user | ✅ Luôn bật (ẩn) |
| **Re-ranking** | Checkbox trong Advanced | ✅ Luôn bật (ẩn) |
| **Layout** | 3 cột | 2 cột |

---

## 📝 Code Changes

```python
# File: streamlit_app/components/query_lab_improved.py
# Lines: 800-822, 837-838

# Đã xóa:
- Checkbox "Enable Vision Generation" (col3)
- Checkbox "Enable Re-ranking" (Advanced Options)

# Đã thêm:
enable_vision = True  # Hardcoded, luôn bật
use_rerank = True     # Hardcoded, luôn bật
```

---

## 🎯 UI Mới

```
[Câu hỏi - Text Area lớn]

[Language ▼]  [Max Context Chunks: 8]

⚙️ Advanced Options (Thu gọn)
  ├─ Use HyDE
  ├─ BM25 Top-K
  ├─ FAISS Top-K
  └─ IEEE-style Citations

[🚀 Run Query]
```

**Note**: Vision và Re-ranking tự động BẬT ở background

---

## ✅ Kiểm tra

- ✅ Syntax OK
- ✅ Import OK
- ✅ Vision & Re-ranking luôn enabled
- ✅ UI đơn giản hơn

---

**Xem chi tiết**: `UI_EXPLANATION_VI.md`
