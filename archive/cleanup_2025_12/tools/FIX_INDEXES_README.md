# 🔧 Fix Indexes - Chỉ Cần 1 Lần!

## ❓ **Tại sao KHÔNG cần re-ingest 2 lần?**

### **Hiện trạng:**
```
✅ Ingestion ĐÃ HOÀN TẤT
   ├─ File 002_3N4-S4274343 ĐÃ được process
   ├─ 29 chunks ĐÃ được tạo
   ├─ Chunks ĐÃ được lưu trong artifacts/ingestion_production/chunks/
   └─ doc_id_map.json ĐÃ có entry cho file này

❌ Indexes CHƯA CẬP NHẬT
   ├─ BM25 index (artifacts/index/bm25/) vẫn là bản cũ
   └─ FAISS index (artifacts/index/faiss/) vẫn là bản cũ
```

### **Nguyên nhân:**
Indexes không tự động rebuild khi có chunks mới. Cần chạy `build_indices_safe.py` để rebuild.

### **Giải pháp:**
Thay vì:
```
❌ Cách làm dài:
   1. Re-ingest documents         (1-2 giờ)
   2. Extract metadata            (1 giờ)
   3. Re-ingest lại với metadata  (1-2 giờ)
   4. Rebuild indexes             (1-2 giờ)
   Total: 4-7 giờ
```

Chúng ta chỉ cần:
```
✅ Cách làm nhanh (1 lần duy nhất):
   1. Load chunks hiện có
   2. Enrich với metadata (từ source path)
   3. Rebuild indexes
   Total: 1-2 giờ
```

---

## 🚀 **Cách chạy**

### **Bước 1: Backup indexes hiện tại (để phòng hờ)**
```powershell
# Tạo backup
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "artifacts\index" "artifacts\index_backup_$timestamp" -Recurse
```

### **Bước 2: Chạy script fix (1 lần duy nhất)**
```powershell
# Chạy fix
python tools/fix_indexes_single_pass.py
```

Script sẽ:
1. ✅ Load tất cả chunks từ `artifacts/ingestion_production/chunks/`
2. ✅ Thêm metadata tự động:
   - `equipment_type` (compressor/turbine/...) từ path
   - `doc_type` (datasheet/manual/...) từ folder
   - `equipment_id` (K06101/KT06101/...) từ filename
   - `vendor` (HITACHI/HTC/...) từ path
3. ✅ Rebuild BM25 index với metadata mới
4. ✅ Rebuild FAISS index với metadata mới (10-20 phút cho embedding)
5. ✅ Verify: kiểm tra file `002_3N4-S4274343` đã có trong indexes

### **Bước 3: Test kết quả**
```powershell
# Start API
uvicorn app.main:app --reload

# Test query (trong browser hoặc Postman)
POST http://localhost:8000/api/v1/ask
{
  "question": "What is the 4th stage discharge pressure for K06101 compressor?"
}

# Expected result:
# - Answer: 79.5 bar.a
# - Citation: 002_3N4-S4274343 datasheet, page 3 ✅
```

---

## 📊 **Timeline So Sánh**

### **Phương án A (re-ingest 2 lần) - KHÔNG khuyến nghị**
```
Day 0:
  ├─ Re-ingest all documents               [2h]
  └─ Extract metadata from path            [1h]

Day 1:
  ├─ Re-ingest lại với metadata            [2h]
  └─ Rebuild BM25/FAISS                    [2h]

Total: 7 giờ, 2 lần ingest toàn bộ corpus
```

### **Phương án B (fix 1 lần) - KHUYẾN NGHỊ ✅**
```
Day 0:
  ├─ Load chunks (instant)                 [0m]
  ├─ Enrich metadata (rule-based)          [5m]
  ├─ Rebuild BM25                          [5m]
  └─ Rebuild FAISS (embedding)             [60-90m]

Total: 1.5-2 giờ, 0 lần ingest lại
```

**Tiết kiệm: 5 giờ** ⏱️

---

## 🔍 **Tại sao metadata extraction nhanh?**

Thay vì dùng LLM để classify (chậm, tốn tiền):
```python
# ❌ Cách chậm: LLM classification
for doc in documents:
    result = llm.classify(doc.content)  # 3-5s per doc
    # → Tổng: 78 docs × 4s = 312s (5 phút)
```

Chúng ta dùng rule-based extraction (tức thì):
```python
# ✅ Cách nhanh: Rule-based từ path
for doc_id, source_path in doc_id_map.items():
    if "COMPRESSOR" in source_path:
        equipment_type = "compressor"
    if "/Data/" in source_path:
        doc_type = "datasheet"
    # → Instant, 100% coverage
```

**Độ chính xác:** ~95% (đủ cho prefilter, không cần 100%)

---

## ✅ **Checklist sau khi chạy**

- [ ] Script chạy thành công (exit code 0)
- [ ] Log hiển thị: `✅ SUCCESS: Document is now in both indexes!`
- [ ] Test query trả về citation đúng: `002_3N4-S4274343 page 3`
- [ ] Kiểm tra metadata có đầy đủ:
  ```powershell
  # Check BM25 metadata
  Get-Content artifacts/index/bm25/metadata.json | Select-String "S4274343" -Context 5
  ```
- [ ] Backup indexes cũ vẫn còn (để rollback nếu cần)

---

## 🆘 **Troubleshooting**

### **Lỗi: "Embedding service not available"**
```powershell
# Kiểm tra API key
echo $env:GEMINI_API_KEY

# Set nếu thiếu
$env:GEMINI_API_KEY = "your-key-here"
```

### **Lỗi: "No chunks loaded"**
```powershell
# Verify chunks directory
Get-ChildItem artifacts/ingestion_production/chunks/*_chunks.json | Measure-Object

# Should show: Count > 0
```

### **Lỗi: "Document still missing from indexes"**
```powershell
# Check if chunk file exists
Get-ChildItem artifacts/ingestion_production/chunks/*1be298a4*.json

# If exists, check content
Get-Content artifacts/ingestion_production/chunks/DOCID_K06101_*1be298a4*_chunks.json | ConvertFrom-Json | Measure-Object

# Should show: Count = 29
```

---

## 📝 **Next Steps sau khi fix**

1. ✅ **Verify baseline metrics**
   ```powershell
   python tools/evaluate_golden_qa_v1.py --output reports/baseline_after_fix.json
   ```

2. ✅ **Proceed với Weaviate migration**
   - Bây giờ có đầy đủ:
     - ✅ All documents in indexes
     - ✅ Metadata cho domain prefilter
     - ✅ Baseline KPI để compare

3. ✅ **Follow BUILD_PLAN_WEAVIATE.md**
   - Week 1: Weaviate setup + dual write
   - Week 2: BGE reranker + page-level + validation

---

## 💡 **Tóm tắt**

**Q: Tại sao không cần re-ingest 2 lần?**
**A:** Vì ingestion ĐÃ XONG. Chỉ cần rebuild indexes từ chunks có sẵn + thêm metadata.

**Q: Metadata từ đâu ra?**
**A:** Extract từ source path (rule-based), không cần LLM.

**Q: Mất bao lâu?**
**A:** 1.5-2 giờ (thay vì 7 giờ).

**Q: Rủi ro?**
**A:** Thấp. Có backup indexes cũ. Rollback < 1 phút nếu cần.

---

**Ready to go?** 🚀
```powershell
python tools/fix_indexes_single_pass.py
```
