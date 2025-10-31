# HƯỚNG DẪN TEST NHANH P&ID FIX

## ✅ ĐÃ FIX

File: `app/rag/indexers/opensearch_tags_retriever.py`
- Fixed 4 search methods để dùng nested paths: `parts.prefix.keyword`, `parts.suffix.keyword`, `parts.unit.keyword`

## 🧪 TEST NGAY (3 BƯỚC)

### Bước 1: Start API (Terminal mới)

```powershell
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# Activate venv nếu cần
.venv\Scripts\Activate.ps1

# Start API
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Đợi thấy log:**
```
✓ Initialized P&ID tags retriever
✓ Initialized Technical Document retriever
✓ Startup completed
```

### Bước 2: Test với Python Script (Terminal mới)

```powershell
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"
python test_pid_e2e.py
```

**Expected:**
- ✅ API healthy
- ✅ Query "04 PI 2504" trả về citations với bbox
- ✅ Page number chính xác

### Bước 3: Test qua UI

```powershell
streamlit run streamlit_app\app.py
```

1. Click **"🗺️ P&ID Diagrams"**
2. Query: **"04 PI 2504 ở trang nào?"**
3. Verify:
   - ✅ Answer: "Tag 04 PI 2504 ở trang 3..."
   - ✅ Citations hiển thị page=3
   - ✅ Có thể click PDF viewer

---

## ⚡ TEST NHANH NHẤT (Không cần API)

```powershell
# Test OpenSearch search trực tiếp
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"
.venv\Scripts\Activate.ps1

python -c "
from app.rag.indexers.opensearch_tags_retriever import OpenSearchTagsRetriever
r = OpenSearchTagsRetriever()
results = r.search_by_components(unit='04', prefix='PI', suffix='2504')
print(f'Found {len(results)} results')
for res in results:
    print(f\"  Tag: {res['text']}, Page: {res['page']}\")
"
```

**Expected:**
```
Found 1 results
  Tag: 04 PI 2504, Page: 3
```

---

## 🎯 KẾT QUẢ MONG ĐỢI

### Trước Fix:
- ❌ Search "04 PI 2504": 0 exact matches
- ❌ Component search: 0 results
- 📉 Accuracy: ~0%

### Sau Fix:
- ✅ Search "04 PI 2504": Exact match tìm thấy
- ✅ Component search: Chính xác
- ✅ Suffix search: Multi-tag grouping
- 📈 Accuracy: **80-95%+**

---

## 📝 FILE ĐÃ SỬA

1. `app/rag/indexers/opensearch_tags_retriever.py` - Search paths
2. `SYSTEM_ARCHITECTURE.md` - Documentation updates

## 📋 FILES TEST (Temporary - có thể xóa sau)

- `test_pid_e2e.py` - E2E test script
- `P&ID_AUDIT_REPORT.md` - Báo cáo chi tiết

---

**CHÚ Ý:** Nếu API không start được, check:
1. Port 8000 đã bị chiếm chưa: `Get-NetTCPConnection -LocalPort 8000`
2. Environment variables đã set đúng chưa
3. Dependencies đã cài đủ chưa: `pip install -r requirements.txt`
