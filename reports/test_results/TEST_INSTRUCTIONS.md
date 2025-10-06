# Hướng Dẫn Test Vision Citation Fixes

## 🎯 Mục đích

Test script sẽ verify tất cả 4 fixes:
1. ✅ Fix 1: Vision Always ON
2. ✅ Fix 2: P&ID Page Selection
3. ✅ Fix 3: Rerank Safety Net
4. ✅ Fix 4: Metadata Enrichment

---

## 📋 Chuẩn bị

### 1. Đảm bảo server đang chạy

```powershell
# Kiểm tra server có chạy không
curl http://localhost:8000/health
```

Nếu chưa chạy, khởi động server trước:
```powershell
# (Thay bằng lệnh start server của bạn)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Verify config

```powershell
# Kiểm tra Vision có enabled không
Select-String "VISION_PAGE_SELECTOR_ENABLED" .env
# Hoặc
cat .env | Select-String "VISION"
```

**Expected:** `VISION_PAGE_SELECTOR_ENABLED=true` (hoặc không có = mặc định True)

### 3. Cài đặt dependencies (nếu cần)

```powershell
pip install requests
```

---

## 🚀 Chạy Test

### Option 1: Chạy full test suite (Khuyến nghị)

```powershell
# Di chuyển đến thư mục project
cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC

# Chạy test script
python test_vision_citation_fixes.py
```

### Option 2: Chạy với output redirect (để lưu console log)

```powershell
python test_vision_citation_fixes.py 2>&1 | Tee-Object -FilePath "test_console_output.txt"
```

---

## 📊 Test Coverage

Script sẽ chạy **8 test cases** (mỗi fix có 2+ tests):

### Fix 1 Tests (3 tests):
- ✅ P&ID Query with Tag (Vietnamese) - `04-FIC-2035`
- ✅ English Text-Only Query - `What is the torque specification?`
- ✅ Vietnamese Text Query - `Moment xoắn của bu lông là bao nhiêu?`

### Fix 2 Tests (2 tests):
- ✅ P&ID with Equipment Tag - `Tìm vị trí của 04-FIC-2035 trên P&ID`
- ✅ P&ID Legend Query - `Legend của P&ID Ammonia Unit`

### Fix 3 Tests (2 tests):
- ✅ Complex Technical Query - `CO2 compressor vibration monitoring system specifications`
- ✅ Specific Equipment Query - `K06101 CO2 compressor expected performance curve`

### Fix 4 Tests (1 test):
- ✅ General Query (Check Metadata) - `Steam turbine data sheet specifications`

---

## 📝 Expected Output

### Console Output sẽ hiển thị:

```
================================================================================
Vision Citation Fixes - Comprehensive Test Suite
================================================================================

API Endpoint: http://localhost:8000
Test Time: 2025-10-04 10:00:00
Total Tests: 8

[Test 1/8] Fix 1 - P&ID Query with Tag (Vietnamese)
  Query: '04-FIC-2035'
  Language: vi
  Testing: Fix 1
  Duration: 3500ms
    ✅ Vision usage: True (expected: True)
    ✅ Page range: 8-12 (within 1-15)
    ✅ Citations count: 5 (min: 3)
    ✅ Context count: 8 (min: 3)
    ✅ Answer generated: 450 chars
  ✓ PASSED

... (more tests)

================================================================================
Test Summary
  Total: 8
  Passed: 8
  Failed: 0
================================================================================

Report saved to: test_vision_fixes_report_20251004_100530.txt
```

### Report File sẽ chứa:
- ✅ Test summary by fix
- ✅ Detailed results cho mỗi test
- ✅ API response metadata
- ✅ Vision pages used/failed
- ✅ Performance metrics

---

## ⏱️ Thời gian chạy

**Expected Duration:**
- Mỗi test: 2-5 seconds (với Vision)
- Total: ~20-40 seconds cho 8 tests
- Nếu cache hit: có thể nhanh hơn

**Nếu timeout (>120s per test):**
- Check server logs
- Vision có thể đang render nhiều pages
- Có thể cần increase `API_TIMEOUT` trong script

---

## 📤 Gửi Logs cho Review

### 1. Logs cần thu thập:

#### A. Test Report (tự động tạo):
```
test_vision_fixes_report_TIMESTAMP.txt
```

#### B. Server Logs (quan trọng!):

```powershell
# Option 1: Nếu server chạy trong console, copy output
# Option 2: Nếu server log ra file
Get-Content logs/server.log -Tail 500 | Out-File "server_logs_during_test.txt"

# Option 3: Grep diagnostic logs
Select-String "\[DIAGNOSTIC\]" logs/server.log -Context 2,2 | Out-File "diagnostic_logs.txt"
```

#### C. Console Output (nếu có):
```
test_console_output.txt
```

### 2. Files cần gửi:

**Priority 1 (Bắt buộc):**
- ✅ `test_vision_fixes_report_TIMESTAMP.txt` (test results)
- ✅ Server logs với `[DIAGNOSTIC]` markers

**Priority 2 (Nếu có vấn đề):**
- ⚠️ Console output full
- ⚠️ Server error logs
- ⚠️ Config files (.env)

### 3. Cách gửi:

Paste vào chat:
```
Tôi đã chạy xong test. Đây là kết quả:

=== Test Report ===
(paste nội dung test_vision_fixes_report_TIMESTAMP.txt)

=== Server Diagnostic Logs ===
(paste các dòng [DIAGNOSTIC] từ server logs)

=== Summary ===
- Tests passed: X/8
- Tests failed: Y/8
- Any errors: (mô tả nếu có)
```

---

## 🔍 Troubleshooting

### Lỗi: "Connection refused"
```
❌ API Error: exception
Detail: Connection refused
```
**Fix:** Server chưa chạy. Start server trước khi test.

### Lỗi: "Timeout"
```
❌ API Error: timeout
Detail: Request exceeded 120s
```
**Fix:**
- Check server logs xem có stuck không
- Vision có thể đang process nhiều pages
- Tăng `API_TIMEOUT` trong script nếu cần

### Lỗi: Import module
```
ModuleNotFoundError: No module named 'requests'
```
**Fix:** `pip install requests`

### Test Failed nhưng không rõ lý do
**Actions:**
1. Check server logs chi tiết
2. Re-run test case riêng
3. Check Vision metadata trong response
4. Verify config settings

---

## 📊 Success Criteria

### Ideal Result (All Green):
- ✅ All 8 tests PASSED
- ✅ Vision used in all tests
- ✅ P&ID pages < 15 (early pages)
- ✅ All tests have ≥3 results
- ✅ No errors in server logs

### Acceptable Result:
- ✅ 7+/8 tests PASSED
- ⚠️ Some page ranges may vary (heuristic-based)
- ✅ No critical errors

### Needs Investigation:
- ❌ <6 tests PASSED
- ❌ Vision not used in tests
- ❌ Any test timeout
- ❌ Errors in server logs

---

## 🎯 Key Metrics to Check

### Fix 1 - Vision Always ON:
```
Expected in logs:
  "Vision strategy: ALWAYS ON (smart_vision_strategy disabled)"
```

### Fix 2 - P&ID Page Override:
```
Expected in logs:
  "[DIAGNOSTIC] P&ID override: center 58 -> 10 (doc has tag pattern, forcing early pages)"
  "[DIAGNOSTIC] Final page window: [8-12] (center=10)"
```

### Fix 3 - Rerank Safety:
```
Expected in logs (if triggered):
  "Keeping top 3 regardless of threshold"
  Or: Normal rerank with ≥3 results
```

### Fix 4 - Metadata Enrichment:
```
Expected in logs:
  "Enriched X/Y results with pdf_path"
```

---

## 💡 Tips

1. **Chạy test khi server clean start** (không cache) để kết quả chính xác
2. **Monitor server logs real-time** trong tab khác
3. **Nếu test fail**, chạy lại 1-2 lần để verify (có thể do network)
4. **Save all logs** trước khi restart server

---

## 📞 Support

Nếu gặp vấn đề:
1. Copy error message đầy đủ
2. Share test report file
3. Share relevant server logs
4. Describe what happened vs expected

**Example support message:**
```
Test failed với lỗi:
- Test case: "Fix 2 - P&ID with Equipment Tag"
- Error: Vision used = False (expected True)
- Server log: (paste relevant lines)
- Config: VISION_PAGE_SELECTOR_ENABLED=true
```

---

**Ready to run?** Execute: `python test_vision_citation_fixes.py` 🚀
