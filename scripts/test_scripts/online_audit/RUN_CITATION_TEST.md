# Hướng dẫn chạy Citation Accuracy Test

## Chuẩn bị

### 1. Start API Server
```powershell
# Mở terminal 1 - Start API
cd c:\Users\Admin\Desktop\Code - API_LLM_PVCFC
.\start_api.ps1

# Đợi thấy: "Application startup complete"
```

### 2. Verify API hoạt động
```powershell
# Mở terminal 2 - Check health
curl http://localhost:8000/health

# Nếu OK → thấy: {"status":"healthy"}
```

## Chạy Test

### Option A: Test đầy đủ (Vision ON + OFF)
```powershell
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py
```

**Sẽ chạy**: 5 câu hỏi × 2 variants = **10 requests** (khoảng 5-10 phút)

### Option B: Test nhanh (chỉ Vision OFF)
```powershell
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py --no-vision
```

**Sẽ chạy**: 5 câu hỏi × 1 variant = **5 requests** (khoảng 3-5 phút)

### Option C: Test chỉ Vision ON
```powershell
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py --vision-only
```

## Đọc kết quả

### Console output
Sẽ thấy từng câu hỏi:
```
================================================================================
Testing: q1_vi_co2_stage3 (vision=True)
Query: Để đánh giá hiệu suất của máy nén CO2...
Expected: 003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf, page 8
Result: ✓ PASS (exact page)
Citations found: 2
  - Matched: DOCID_3N4_S4274345_Compressor_abc123, page 8 (diff: 0)
```

### Verdicts
- `✓ PASS (exact page)` - Đúng cả doc và page
- `~ PARTIAL (page off by 1)` - Đúng doc, lệch 1 trang
- `✗ FAIL (doc OK, page wrong)` - Đúng doc, sai trang nhiều
- `✗✗ FAIL (wrong doc)` - Sai doc

### Summary cuối
```
Test Summary:
  Total tests: 10
  ✓ Correct doc+page: 7
  ~ Correct doc, wrong page: 2
  ✗ Wrong doc: 1
  ✗ No answer/citation: 0
  Pass rate: 70.0%
  Doc match rate: 90.0%
```

### File kết quả
```
reports/test_results/citation_accuracy_golden_20251007_143052.json
```

**Chứa**:
- Full API responses
- Chi tiết so sánh với ground truth
- Retrieval results (top 10)
- Citations (doc_id, page, pdf_path)
- Validation metadata
- Vision metadata (nếu có)

## Phân tích kết quả

### Pass rate ≥ 60%
- ✅ Hệ thống đạt mức chấp nhận được
- Tiếp tục phân tích chi tiết patterns

### Pass rate < 60%
- ⚠️ Có vấn đề nghiêm trọng về citation
- Cần điều tra sâu hơn (steps 2-9 trong plan)

## Next Steps

### Nếu test PASS (≥60%)
1. Mở file JSON result
2. Tìm các case `FAIL` hoặc `PARTIAL`
3. Xem `comparison.page_distance` và `comparison.matched_citations`
4. Chạy **Step 2**: Kiểm tra đồng bộ doc_id_map

### Nếu test FAIL (<60%)
1. Lưu file JSON result
2. Chạy tất cả steps 2-9 trong investigation plan
3. Tìm root cause (doc map, metadata, validator)
4. Lập báo cáo với khuyến nghị cải thiện

## Troubleshooting

### Error: "Cannot connect to API"
```powershell
# Check port
netstat -ano | findstr :8000

# Restart API
.\start_api.ps1
```

### Error: "API timeout after 120s"
- Query quá phức tạp hoặc vision render chậm
- Tăng timeout: edit test script, line 94: `timeout=180`

### Error: "No doc_id match"
- Kiểm tra doc_id_map.json có file này không
- Xem pattern match trong dataset có đúng không

## Files liên quan
- `golden_citation_dataset.json` - 5 câu hỏi + ground truth
- `test_citation_accuracy_golden.py` - Test runner
- `question_example.md` - Source questions (for reference)

---

**Created**: 2025-10-07
**Author**: AI Investigation Team
**Status**: Ready to run
