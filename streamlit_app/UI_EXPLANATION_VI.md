# Giải thích UI và Khái niệm RAG System

## 📚 Giải thích các khái niệm trong UI

### 1. HyDE (Hypothetical Document Expansion)
**Tên tiếng Việt**: Mở rộng tài liệu giả định

**Cách hoạt động**:
- Thay vì tìm kiếm trực tiếp bằng câu hỏi của người dùng, hệ thống sẽ:
  1. Sử dụng LLM để tạo ra một "tài liệu giả định" - một đoạn văn mẫu có thể trả lời câu hỏi đó
  2. Tìm kiếm bằng tài liệu giả định này thay vì câu hỏi gốc
  3. Tài liệu giả định có cấu trúc giống tài liệu thực → dễ match hơn trong semantic search

**Ví dụ cụ thể**:
```
Câu hỏi: "Quy trình an toàn khi xử lý ammonia là gì?"

HyDE tạo tài liệu giả định:
"Quy trình an toàn khi xử lý ammonia bao gồm các bước sau:
1. Mặc đồ bảo hộ đầy đủ (găng tay, kính, áo chống hóa chất)
2. Đảm bảo hệ thống thông gió hoạt động tốt
3. Kiểm tra nồng độ khí trong không khí
4. Chuẩn bị thiết bị xử lý sự cố..."

→ Hệ thống tìm kiếm bằng đoạn văn này thay vì câu hỏi ngắn
→ Kết quả chính xác hơn vì match với cấu trúc tài liệu kỹ thuật
```

**Khi nào dùng**:
- ✅ Câu hỏi phức tạp, cần thông tin chi tiết
- ✅ Tài liệu kỹ thuật có cấu trúc rõ ràng
- ❌ Câu hỏi đơn giản (tốn thời gian, token)
- ❌ Khi cần tốc độ nhanh

**Trade-off**:
- ➕ Độ chính xác cao hơn
- ➖ Chậm hơn (phải gọi LLM thêm 1 lần)
- ➖ Tốn token/chi phí hơn

---

### 2. Max Context Chunks
**Tên tiếng Việt**: Số lượng đoạn văn bản ngữ cảnh tối đa

**Giải thích**:
- Tài liệu PDF được chia thành nhiều "chunks" (đoạn văn bản nhỏ, thường 500-1000 từ)
- Giá trị này quyết định lấy **bao nhiêu chunks có liên quan nhất** để cung cấp cho LLM đọc và trả lời
- LLM sẽ đọc tất cả chunks này để tổng hợp câu trả lời

**Ví dụ**:
```
Giá trị = 8:
- Hệ thống tìm kiếm và xếp hạng tất cả chunks
- Lấy 8 chunks có điểm cao nhất
- Gửi 8 chunks này cho LLM
- LLM đọc 8 chunks và tổng hợp câu trả lời với citation

Nội dung thực tế gửi cho LLM:
[Chunk 1 từ file A.pdf trang 5]
[Chunk 2 từ file A.pdf trang 7]
[Chunk 3 từ file B.pdf trang 12]
... (tổng 8 chunks)
```

**Cách chọn giá trị**:
| Giá trị | Khi nào dùng | Ưu điểm | Nhược điểm |
|---------|--------------|---------|------------|
| **3-5** | Câu hỏi đơn giản, cần trả lời nhanh | Nhanh, tiết kiệm token | Có thể thiếu thông tin |
| **8-10** (mặc định) | Câu hỏi trung bình | Cân bằng tốt | Phù hợp hầu hết trường hợp |
| **15-20** | Câu hỏi phức tạp, cần nhiều nguồn | Đầy đủ thông tin | Chậm, tốn token, có thể nhiễu |

**Trade-off**:
- ➕ Giá trị cao = Nhiều ngữ cảnh = Câu trả lời đầy đủ hơn
- ➖ Giá trị cao = Chậm hơn + Tốn token + Có thể có thông tin nhiễu
- ➕ Giá trị thấp = Nhanh + Tiết kiệm
- ➖ Giá trị thấp = Có thể thiếu thông tin quan trọng

---

### 3. Vision Generation
**Tên tiếng Việt**: Tạo câu trả lời bằng Vision (Đa phương thức)

**Giải thích**:
- Sử dụng mô hình AI có khả năng "nhìn" ảnh (multimodal) như Gemini Vision
- Thay vì chỉ đọc text được OCR, AI sẽ xem trực tiếp hình ảnh trang PDF
- Đặc biệt hữu ích với:
  - Bảng biểu phức tạp
  - Sơ đồ kỹ thuật
  - Hình ảnh có chú thích
  - Văn bản scan chất lượng thấp

**Lợi ích**:
- ✅ Hiểu chính xác bảng biểu, sơ đồ
- ✅ Bắt được thông tin từ hình ảnh
- ✅ Xử lý tốt scan kém chất lượng

---

### 4. Re-ranking
**Tên tiếng Việt**: Xếp hạng lại kết quả

**Giải thích**:
- Sau khi lấy kết quả từ BM25 (keyword search) và FAISS (semantic search)
- Hệ thống dùng mô hình re-ranker (BGE cross-encoder) để "đọc kỹ" và chấm điểm lại
- Re-ranker so sánh chi tiết giữa câu hỏi và từng chunk → điểm chính xác hơn

**Pipeline**:
```
1. BM25: Tìm 50 chunks theo từ khóa
2. FAISS: Tìm 50 chunks theo ngữ nghĩa
3. Merge: Kết hợp 2 danh sách
4. Re-ranking: BGE cross-encoder đọc từng chunk và chấm điểm lại
5. Lấy top K chunks có điểm cao nhất
```

**Lợi ích**:
- ✅ Loại bỏ kết quả không liên quan
- ✅ Đưa kết quả tốt nhất lên đầu
- ✅ Độ chính xác cao hơn

---

## 🔧 Thay đổi UI (Cập nhật mới)

### Những gì đã ẩn và luôn bật mặc định:

#### 1. **Enable Vision Generation**
- **Trước**: Có checkbox cho người dùng bật/tắt
- **Bây giờ**: ✅ **Luôn bật** (hardcoded = True)
- **Lý do**: Vision cải thiện độ chính xác đáng kể, nên luôn dùng

#### 2. **Enable Re-ranking**
- **Trước**: Có checkbox trong Advanced Options
- **Bây giờ**: ✅ **Luôn bật** (hardcoded = True)
- **Lý do**: Re-ranking cải thiện chất lượng kết quả, nên luôn bật

### UI hiện tại (Sau khi chỉnh sửa):

```
┌─────────────────────────────────────────────────────┐
│ RAG Question Answering                              │
│ Ask questions and receive grounded answers...      │
├─────────────────────────────────────────────────────┤
│ [Text Area: Enter your question - Height: 220px]   │
├─────────────────────────────────────────────────────┤
│ Language          │ Max Context Chunks              │
│ [vi ▼]           │ [8]                             │
├─────────────────────────────────────────────────────┤
│ ⚙️ Advanced Options [Click to expand ▼]            │
│   ├─ Retrieval Settings                            │
│   │   ├─ Use HyDE                                  │
│   │   ├─ BM25 Top-K [50]                          │
│   │   └─ FAISS Top-K [50]                         │
│   └─ Citation Settings                             │
│       └─ Use IEEE-style Citations                  │
├─────────────────────────────────────────────────────┤
│         [🚀 Run Query - Full Width Button]         │
└─────────────────────────────────────────────────────┘

Note: Vision và Re-ranking luôn ENABLED ở background
```

---

## 📊 So sánh Before/After

| Tính năng | Trước đây | Bây giờ |
|-----------|-----------|---------|
| **Vision Generation** | Checkbox visible (col3) | ✅ Always enabled (hidden) |
| **Re-ranking** | Checkbox trong Advanced | ✅ Always enabled (hidden) |
| **Layout chính** | 3 cột (Language, Max Context, Vision) | 2 cột (Language, Max Context) |
| **Số tùy chọn hiển thị** | 5 controls | 3 controls |
| **UI Simplicity** | Trung bình | ✅ Đơn giản hơn |

---

## 💡 Khuyến nghị sử dụng

### Cho câu hỏi thường ngày:
- **Language**: vi
- **Max Context Chunks**: 8 (mặc định)
- **HyDE**: ❌ Tắt (không cần thiết)
- **Vision**: ✅ Luôn bật (tự động)
- **Re-ranking**: ✅ Luôn bật (tự động)

### Cho câu hỏi phức tạp:
- **Language**: vi
- **Max Context Chunks**: 12-15
- **HyDE**: ✅ Bật (để tìm kiếm chính xác hơn)
- **Vision**: ✅ Luôn bật (tự động)
- **Re-ranking**: ✅ Luôn bật (tự động)

### Khi cần tốc độ cao:
- **Language**: vi
- **Max Context Chunks**: 5
- **HyDE**: ❌ Tắt (tiết kiệm thời gian)
- **Vision**: ✅ Luôn bật (tự động)
- **Re-ranking**: ✅ Luôn bật (tự động)

---

## 🔍 Chi tiết kỹ thuật

### Code Changes Summary:
```python
# BEFORE
col1, col2, col3 = st.columns(3)
with col3:
    enable_vision = st.checkbox("Enable Vision Generation", value=True)

with col_adv2:
    use_rerank = st.checkbox("Enable Re-ranking", value=True)

# AFTER
col1, col2 = st.columns(2)  # Remove col3
# Vision and Re-ranking are ALWAYS enabled (hardcoded)
enable_vision = True
use_rerank = True
```

### Location:
- File: `streamlit_app/components/query_lab_improved.py`
- Lines: 800-822, 837-838

---

## ✅ Verification

Đã kiểm tra:
- ✅ File compile thành công
- ✅ Module import thành công
- ✅ Không có syntax error
- ✅ Vision và Re-ranking luôn enabled trong background
- ✅ UI đơn giản hơn, chỉ 2 cột chính

---

**Date**: 2025-10-13
**Modified by**: AI Assistant
**Purpose**: Simplify UI, always enable Vision & Re-ranking for better accuracy
