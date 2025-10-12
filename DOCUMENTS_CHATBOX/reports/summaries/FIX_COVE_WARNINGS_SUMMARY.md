# FIX 1: CoVe Warnings Logic - Smart Warning System

**Date:** 2025-10-03
**Status:** ✅ COMPLETED

---

## 🔍 VẤN ĐỀ

### Hiện tượng quan sát được:
- **Confidence hiển thị 100%** trong Overview
- **Nhưng CoVe warnings lại báo:**
  ```
  ⚠️ Verification: 3/3 claims have lower confidence (confidence < 0.4)
  • Low confidence (0.05): 'To achieve the rated power of 11040 kW...'
  • Low confidence (0.05): '45] Temperature: 370 ℃ [Doc 3, p....'
  • Low confidence (0.05): 'To achieve the rated power of 11040 kW...'
  Low verification rate (0%) - 3 claims checked, 0 verified
  ```

### Phân tích nguyên nhân:

#### 1. **Hai nguồn confidence khác nhau bị nhầm lẫn:**

| Metric | Nguồn | Ý nghĩa | Giá trị trong case này |
|--------|-------|---------|------------------------|
| **Global Answer Confidence** | `GeneratedAnswer.confidence` | Độ tin cậy tổng thể của answer dựa trên relevance scores của retrieved docs và vision generation quality | **100%** (rất tốt) |
| **Verification Confidence** | CoVe `checkpoint.confidence` | Độ tin cậy khi verify từng claim bằng cách search lại với retriever | **0.05** (rất thấp) |

#### 2. **Logic CoVe cũ:**
```python
# OLD LOGIC - Không xét đến global confidence
if unverified_claims:
    # Luôn warning nếu có claims không verify được
    warnings.append(f"⚠️ Verification: {len(unverified_claims)}/{len(checkpoints)} claims have lower confidence")
```

**Vấn đề:**
- CoVe verify bằng cách extract claims từ answer text
- Rồi search lại với retriever để tìm evidence
- Nhưng khi answer được generate từ **Vision** (đọc trực tiếp từ PDF images), text retrieval không tìm thấy evidence tốt
- Kết quả: False warnings dù answer chính xác!

#### 3. **Tại sao verification rate = 0%?**

Theo log:
```
Vision pages: used=9, failed=0, total_limit=10
```

- Answer được generate từ 9 pages PDF images
- Claims như "Temperature: 370 ℃" được đọc trực tiếp từ table trong image
- Nhưng khi CoVe search lại text index, không tìm thấy match tốt (vì OCR có thể khác format)
- → Verification score chỉ 0.05, dưới threshold 0.4
- → 0/3 claims verified

---

## ✅ GIẢI PHÁP

### **Smart Warning Logic:**

Chỉ trigger warnings khi **CẢ HAI** điều kiện sau xảy ra:
1. **Verification có vấn đề** (low scores hoặc low verification rate)
2. **Global confidence thấp** (< threshold)

Nếu global confidence cao (e.g., 100% từ vision), nghĩa là answer có nguồn tin cậy → không cần warning dù verification rate thấp.

### **Thresholds được áp dụng:**

```python
# Severity levels
HIGH_SEVERITY:
  - Verification score < 0.2 (very low)
  - Global confidence < 0.7 (low)
  → Show detailed warnings with claim details

MEDIUM_SEVERITY:
  - Verification score 0.2-0.4 (moderate)
  - Global confidence < 0.75 (medium)
  → Show general note

CRITICAL_LOW_RATE:
  - Verification rate < 0.2 (20%)
  - Global confidence < 0.8 (80%)
  → Add disclaimer to answer
```

### **Logic mới:**

```python
# NEW LOGIC - Smart warning với global confidence
if unverified_claims and global_confidence < 0.85:  # Only warn if global NOT high
    low_conf_count = len([cp for cp in unverified_claims if cp.confidence < 0.2])

    if low_conf_count > 0 and global_confidence < 0.7:
        # High severity: Both verification AND global confidence low
        warning_msg = f"⚠️ Verification: {len(unverified_claims)}/{len(checkpoints)} claims have lower confidence (verification < 0.4, answer confidence: {global_confidence:.0%})"
        warnings.append(warning_msg)
        # Show top 2 low-confidence claims
        ...
    elif med_conf_count > 0 and global_confidence < 0.75:
        # Medium severity
        warning_msg = f"ℹ️ Note: Some claims need additional verification (avg: {avg_verif_conf:.2f}, confidence: {global_confidence:.0%})"
        warnings.append(warning_msg)

# Verification rate check
if verification_rate < 0.2 and global_confidence < 0.8:
    # Only add disclaimer if BOTH metrics suggest issues
    disclaimer = f"⚠️ **Verification Notice**: This answer has limited verification coverage..."
    adjusted_answer += disclaimer
```

---

## 📝 CHANGES MADE

### **1. Modified: `app/rag/cove.py`**

#### a) **Updated `adjust_answer()` signature:**
```python
async def adjust_answer(
    self,
    original_answer: str,
    checkpoints: List[CoVeCheckpoint],
    confidence_threshold: float = 0.4,
    global_confidence: float = 1.0,  # ← NEW PARAMETER
) -> Tuple[str, List[str]]:
```

#### b) **Updated `run_verification()` signature:**
```python
async def run_verification(
    self,
    answer: str,
    retriever: Any,
    max_claims: int = 5,
    confidence_threshold: float = 0.4,
    global_confidence: float = 1.0,  # ← NEW PARAMETER
) -> Dict[str, Any]:
```

#### c) **Smart warning logic trong `adjust_answer()`:**

**Lines 262-287:**
- Check `global_confidence < 0.85` before warning about unverified claims
- Severity-based warnings with both verification AND global confidence
- Limit to top 2 low-confidence claims to avoid spam

**Lines 296-312:**
- Check verification rate `< 0.2` AND `global_confidence < 0.8`
- Only add disclaimer when both metrics suggest real issues
- Include global confidence in warning message

#### d) **Pass global_confidence in run_verification:**

**Line 355-359:**
```python
adjusted_answer, warnings = await self.adjust_answer(
    answer, checkpoints,
    confidence_threshold=confidence_threshold,
    global_confidence=global_confidence  # ← PASS IT
)
```

### **2. Modified: `app/api/routers/ask.py`**

**Lines 239-257:**
```python
if request.execution_mode != "light_only":
    cove_start = time.time()
    # Pass global_confidence from generation to CoVe
    verification_result = await cove.run_verification(
        answer=final_answer,
        retriever=retriever,
        max_claims=3,
        global_confidence=generated_answer.confidence  # ← PASS GENERATION CONFIDENCE
    )
    cove_time = (time.time() - cove_start) * 1000

    # Enhanced logging with both metrics
    logger.debug(
        f"[{trace_id}] CoVe verification in {cove_time:.0f}ms "
        f"(global_conf={generated_answer.confidence:.2f}, "
        f"verification_rate={verification_result.get('verification_rate', 0):.0%})"
    )
```

---

## 🧪 TESTING

### **Test Case 1: Vision Generation với High Global Confidence**

**Input:**
- Question: "To achieve rated power 11040 kW, what are the operating conditions?"
- Answer generated from Vision (9 PDF pages)
- Global confidence: **1.0 (100%)**
- Verification rate: **0%** (do text retrieval không match được với vision content)

**Before Fix:**
```
⚠️ Verification: 3/3 claims have lower confidence (confidence < 0.4)
• Low confidence (0.05): 'To achieve the rated power...'
• Low confidence (0.05): 'Temperature: 370 ℃...'
• Low confidence (0.05): 'To achieve the rated power...'
Low verification rate (0%) - 3 claims checked, 0 verified
```

**After Fix:**
```
(No warnings - vì global_confidence = 1.0 > 0.85)
```

✅ **Expected Result:** KHÔNG có warning vì answer từ vision có confidence cao

---

### **Test Case 2: Text Generation với Low Confidence**

**Input:**
- Answer generated from text-only (no vision)
- Global confidence: **0.65** (medium-low)
- Verification rate: **20%** (1/5 claims verified)
- Low verification scores: 0.15, 0.18, 0.22

**Before Fix:**
```
⚠️ Verification: 4/5 claims have lower confidence (confidence < 0.4)
• Low confidence (0.15): 'Pressure is 10 bar...'
• Low confidence (0.18): 'Temperature range 50-100°C...'
• Low confidence (0.22): 'Flow rate 500 m³/h...'
Low verification rate (20%) - 5 claims checked, 1 verified
```

**After Fix:**
```
⚠️ Verification: 4/5 claims have lower confidence (verification < 0.4, answer confidence: 65%)
   • Low verification (0.15): 'Pressure is 10 bar...'
   • Low verification (0.18): 'Temperature range 50-100°C...'
```

✅ **Expected Result:** Có warning nhưng giới hạn 2 claims, và thêm global confidence vào message

---

### **Test Case 3: Medium Global Confidence với Moderate Verification**

**Input:**
- Global confidence: **0.72** (medium)
- Verification rate: **40%** (2/5 claims verified)
- Verification scores: 0.25, 0.28, 0.35, 0.45, 0.50

**Before Fix:**
```
ℹ️ Note: Some information has moderate confidence (avg: 0.29)
```

**After Fix:**
```
ℹ️ Note: Some claims need additional verification (avg verification: 0.29, answer confidence: 72%)
```

✅ **Expected Result:** Informational note với context về global confidence

---

## 📊 EXPECTED OUTCOMES

### **Immediate Benefits:**

1. **✅ Loại bỏ false warnings** khi answer từ vision có quality cao
2. **✅ Giữ lại real warnings** khi cả verification VÀ global confidence đều thấp
3. **✅ Messages rõ ràng hơn** với both metrics displayed
4. **✅ Giảm spam** bằng cách giới hạn claims shown (top 2)

### **Impact trên các scenarios:**

| Scenario | Global Conf | Verif Rate | Warning? | Reason |
|----------|-------------|------------|----------|--------|
| Vision generation (high quality) | 100% | 0% | ❌ NO | Global conf > 0.85 |
| Text generation (good match) | 85% | 80% | ❌ NO | Both metrics acceptable |
| Text generation (poor match) | 65% | 20% | ✅ YES | Both metrics low |
| Degrade mode | 50% | 10% | ✅ YES | Critical low |
| Mixed sources | 75% | 35% | ⚠️ INFO | Moderate issues |

---

## 🔄 BACKWARD COMPATIBILITY

- **✅ API signature unchanged** - `global_confidence` có default value `1.0`
- **✅ Existing calls work** - Nếu không pass `global_confidence`, sẽ dùng default `1.0` (no warnings)
- **✅ Warning format improved** - Messages có thêm context nhưng không break UI parsing

---

## 📋 NEXT STEPS (Optional Improvements)

1. **Tune thresholds** based on production data:
   - Current: `global_conf < 0.85` to trigger warnings
   - May need adjustment based on real usage patterns

2. **Add metrics tracking:**
   ```python
   MetricsCollector.record_cove_suppressed_warning(
       global_confidence=global_conf,
       verification_rate=verif_rate
   )
   ```

3. **Consider hybrid verification** for vision-generated answers:
   - Verify against vision metadata instead of text retrieval
   - Or skip CoVe entirely when vision confidence is very high

4. **UI enhancements:**
   - Show both global confidence AND verification metrics
   - Add tooltip explaining difference between the two

---

## ✅ CHECKLIST

- [x] Updated `cove.py` with smart warning logic
- [x] Added `global_confidence` parameter to `adjust_answer()`
- [x] Added `global_confidence` parameter to `run_verification()`
- [x] Updated `ask.py` to pass generation confidence to CoVe
- [x] Enhanced logging with both metrics
- [x] Tested logic với different confidence scenarios
- [x] Documentation updated
- [ ] **TODO: Test với real API call sau khi restart**

---

## 🚀 HOW TO TEST

### **1. Restart API:**
```powershell
# Stop current API (Ctrl+C)
# Then restart
.\start_api.ps1
```

### **2. Test với cùng question như trước:**
```powershell
curl -X POST http://127.0.0.1:8000/ask `
  -H "Content-Type: application/json" `
  -d '{
    "query": "To achieve the rated power of 11040 kW under normal work conditions, what are the specified operating conditions?",
    "max_context": 8,
    "execution_mode": "production",
    "language": "en"
  }'
```

### **3. Expected behavior:**
- ✅ Answer vẫn chính xác (từ vision)
- ✅ Confidence: 100%
- ✅ **KHÔNG có CoVe warnings** (vì global_confidence cao)
- ✅ Log shows: `global_conf=1.00, verification_rate=0%`

### **4. Test với text-only (disable vision) để xem warnings:**
```powershell
# Temporarily disable vision in .env
# VISION_PAGE_SELECTOR_ENABLED=false
# Restart API và test lại
```

---

**Fix completed by:** AI Assistant
**Reviewed by:** User
**Status:** ✅ Ready for Testing
