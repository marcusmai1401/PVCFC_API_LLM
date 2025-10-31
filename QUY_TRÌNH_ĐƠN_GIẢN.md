# 📘 QUY TRÌNH INGESTION + INDEXING ĐƠN GIẢN

> **Hướng dẫn 3 bước, ngôn ngữ tự nhiên, dễ hiểu**

---

## 🤔 TẠI SAO CẦN 2 MÔI TRƯỜNG?

**Lý do đơn giản:** 2 công cụ không thể chung sống

- **PaddleOCR** (đọc chữ từ ảnh) cần protobuf version 3.20
- **Weaviate** (tìm kiếm thông minh) cần protobuf version 4.21+

→ Giống như Windows XP và Windows 11 không cài cùng 1 máy

**Giải pháp:** 2 "máy ảo" riêng biệt

---

## 🏗️ 2 MÔI TRƯỜNG LÀ GÌ?

### **venv_ingest** = Máy Quét

```
Làm gì:   Quét PDF, nhận dạng chữ, extract tags
Có gì:    PaddleOCR (OCR engine)
Dùng khi: Xử lý tài liệu mới
```

### **.venv** = Máy Tra Cứu

```
Làm gì:   Lập chỉ mục, API, tìm kiếm
Có gì:    Weaviate, OpenSearch, FastAPI
Dùng khi: Indexing, chạy API, query
```

---

## 📋 QUY TRÌNH 3 BƯỚC (45 Phút)

### **BƯỚC 1: XỬ LÝ PDF** (2-3 phút)

**Môi trường:** `venv_ingest` ⚠️

```powershell
# Kích hoạt môi trường quét
venv_ingest\Scripts\Activate.ps1

# Quét tất cả PDFs
python tools/ingest.py `
    --source-dir "D:\Data_Raw" `
    --output-dir "artifacts\ingestion_production" `
    --enable-ocr `
    --workers 2 `
    --enable-pid-tags
```

**Kết quả:**
- chunks.jsonl (~5,000 đoạn văn)
- tags.jsonl (~200 tags từ P&ID)

---

### **BƯỚC 2: LẬP CHỈ MỤC** (35-40 phút)

**Môi trường:** `.venv` ⚠️ (Khác bước 1!)

```powershell
# Tắt môi trường cũ, bật môi trường mới
deactivate
.venv\Scripts\Activate.ps1

# Tạo database
python scripts\opensearch\create_rag_chunks_index.py --delete-if-exists
python scripts\opensearch\create_tags_index.py --delete-if-exists

# Đưa dữ liệu vào (mất 35 phút)
python scripts\utilities\index_production_chunks.py

# Đưa tags vào (1 phút)
python scripts\opensearch\bulk_upsert_tags.py `
    --tags-file "artifacts\ingestion_production\entities\tags.jsonl"
```

**Kết quả:**
- 3 databases sẵn sàng tìm kiếm

---

### **BƯỚC 3: KHỞI ĐỘNG API** (30 giây)

**Môi trường:** `.venv` (giống bước 2)

```powershell
# Bật server
.\launchers\start_api.ps1
```

**Kết quả:** API ready tại http://localhost:8000

---

## ✅ CHECKLIST ĐƠN GIẢN

```
□ Bước 1: venv_ingest → Process PDFs
□ Bước 2: .venv → Index vào databases
□ Bước 3: .venv → Start API

✓ XONG! Có thể query ngay!
```

---

## 🎯 QUY TẮC VÀNG

```
┌──────────────────────────┐
│ Xử lý PDF → venv_ingest  │
│ Tất cả khác → .venv      │
└──────────────────────────┘
```

**Nhớ điều này là đủ!**

---

**Chi tiết đầy đủ:** Xem `HUONG_DAN_INGESTION.md` Sections 2.0 & 12
