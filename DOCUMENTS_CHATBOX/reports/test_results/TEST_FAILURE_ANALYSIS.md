# Test Failure Analysis & Decision Rationale

**Date:** 2025-10-04
**Test Run:** 3/8 PASSED, 5/8 FAILED
**Status:** Root cause analysis complete, corrections applied

---

## 🔍 Test Results Summary

| Test | Status | Issue | Root Cause |
|------|--------|-------|------------|
| Test 1 | ✅ PASS | ⚠️ Page range 30-60 (expected 1-15) | P&ID override không kích hoạt |
| Test 2 | ❌ FAIL | Citations=1 < 3 | LLM không cite đủ |
| Test 3 | ✅ PASS | - | - |
| Test 4 | ✅ PASS | ⚠️ Page range 8-1086 (bất thường) | Test script tính min/max trên nhiều docs |
| Test 5 | ❌ FAIL | Vision usage=False | Không build được pages_plan |
| Test 6 | ❌ FAIL | Citations=1 < 3 | LLM không cite đủ |
| Test 7 | ❌ FAIL | Citations=1 < 3 | LLM không cite đủ |
| Test 8 | ❌ FAIL | Citations=2 < 3 | LLM không cite đủ |

---

## ❌ Rejected Solution: Padding Citations

### Initial Approach (WRONG):
```python
# Pad citations to minimum 3 when fewer extracted
if citations and len(citations) < 3 and doc_mapping:
    for doc_num in sorted(doc_mapping.keys()):
        if len(citations) >= 3:
            break
        # Add citation from top docs...
```

### Why This is WRONG:

**1. Treats Symptom, Not Cause:**
- Symptom: Test fails vì citations < 3
- Root cause: LLM không tuân thủ instruction "ALWAYS include citations"
- Padding che giấu vấn đề thực sự

**2. Creates Inconsistency:**
```
Answer: "The specification is X [Doc 1]"
Citations: [Doc 1, Doc 2, Doc 3]  ← Doc 2, 3 không được mention trong answer!
```
- User thấy 3 citations nhưng chỉ 1 được cite trong text
- Gây confusion và mất trust

**3. Violates Validation Logic:**
- Citation validation sẽ check xem citation có match với answer không
- Padded citations sẽ fail validation vì không có trong answer text
- Tạo false positive trong metrics

**4. Không Fix Root Problem:**
- Nếu LLM model quality kém → cần improve prompt hoặc model
- Nếu context không đủ → cần improve retrieval
- Padding chỉ làm metric trông đẹp mà không cải thiện thực chất

---

## ✅ Correct Approach

### A. Understand Root Causes

#### Test 2, 6, 7, 8: Citations < 3

**Root Causes:**
1. **LLM không tuân thủ prompt:**
   - Prompt đã có "ALWAYS include inline citations"
   - Nhưng Gemini 2.5 Pro không cite mọi statement
   - Có thể do answer quá ngắn hoặc thông tin quá general

2. **Context quality:**
   - Nếu context không có multiple distinct sources
   - LLM có thể aggregate info và chỉ cite 1 source chung

3. **Test expectation sai:**
   - Min 3 citations là arbitrary number
   - Một answer tốt có thể chỉ cần 1-2 citations nếu answer ngắn gọn
   - Example: "What is the torque specification?" → "25 Nm [Doc 1]" là valid

**Solutions:**
- **Short-term:** Accept that good answers may have fewer citations
- **Medium-term:** Improve prompt engineering
- **Long-term:** Use structured output JSON mode to enforce citation schema

#### Test 5: Vision usage = False

**Root Cause:**
- `pages_plan` empty → Vision không thể chạy
- Có thể do:
  - Retrieved docs không có trong doc_id_map
  - Retrieved docs không có metadata['pdf_path'] (enrichment chưa đủ sớm)
  - Query "Legend của P&ID" retrieve sai docs (không phải P&ID)

**Solutions:**
- ✅ Đã add fallback metadata['pdf_path'] (Fix 4)
- ✅ Đã add diagnostic logs để tìm exact reason
- Need: Check server logs xem docs nào được retrieve

#### Test 1, 4: Page range không đúng mong đợi

**Test 1: Page 30-60 thay vì 1-15**
- P&ID override không kích hoạt
- Cần check diagnostic logs:
  - `tag_pattern_found` có True không?
  - `center` có > 20 không?
  - `is_pid` có detect đúng không?

**Test 4: Page 8-1086**
- Test script tính min/max trên tất cả pages_used
- Nếu Vision render từ nhiều docs, có thể có:
  - Page 8 từ Doc A
  - Page 1086 từ Doc B
- Test script show "8-1086" nhưng thực tế OK
- Need: Check Vision metadata để xác nhận

---

## 🛠️ Changes Applied

### Change 1: REVERT Padding Citations ✅
**File:** `app/rag/generator.py`
**Lines:** 1181-1185 (was 1181-1215)

**Before (WRONG):**
```python
# If citations are fewer than 3, pad with top docs
if citations and len(citations) < 3:
    # ... padding logic ...
```

**After (CORRECT):**
```python
# Log extraction summary for diagnostics
logger.info(
    f"Citation extraction: found {len(citations)} citations from answer "
    f"(doc_mapping size: {len(doc_mapping) if doc_mapping else 0})"
)
```

**Rationale:**
- Không pad artificial citations
- Log để track thực tế có bao nhiêu citations được extract
- Cho phép phân tích root cause (LLM behavior, context quality)

---

### Change 2: Enhance Vision Failure Diagnostics ✅
**File:** `app/rag/generator.py`
**Lines:** 1233-1243

**Added:**
```python
if not pages_plan:
    logger.warning(
        f"[DIAGNOSTIC] Vision gating: OFF (reason={reason}). "
        f"Retrieved docs: {len(retrieved_docs)}, pages_meta: {pages_meta}"
    )
    # Log first few docs to understand why no pages
    for i, doc in enumerate(retrieved_docs[:3]):
        meta = doc.metadata or {}
        logger.warning(
            f"[DIAGNOSTIC] Doc #{i+1} skipped: doc_id={doc.doc_id[:50]}, "
            f"has_metadata_pdf_path={'pdf_path' in meta}, "
            f"in_doc_id_map={doc.doc_id in doc_id_map}"
        )
```

**Rationale:**
- Giúp debug Test 5 (Vision=False)
- Show exactly why docs bị skip
- Check cả doc_id_map và metadata['pdf_path']

---

### Change 3: Keep Previous Fixes ✅
**Already implemented:**
- ✅ Fallback to metadata['pdf_path'] when doc_id not in map
- ✅ Carry doc_id in pages_plan for better citation mapping
- ✅ Enhanced P&ID detection (P&ID, P & I, P_ID patterns)

---

## 📊 Expected Results After Changes

### Tests That Will Still Fail (Acceptable):

**Test 2, 6, 7, 8: Citations < 3**
- ❌ Will likely still fail
- ✅ This is ACCEPTABLE because:
  - Root cause is LLM behavior, not code bug
  - Good answers may have < 3 citations if concise
  - Padding would create fake/inconsistent citations
  - Real solution is prompt engineering or structured output

**Action:** Adjust test expectations to accept fewer citations OR improve LLM prompting

### Tests That Should Pass/Improve:

**Test 5: Vision usage = False**
- ✅ May pass if enrichment + fallback work
- ✅ Diagnostic logs will show exact reason if still fails
- Need to check server logs after rerun

**Test 1, 4: Page range warnings**
- ⚠️ May still show warnings
- Need diagnostic logs to understand P&ID override logic

---

## 🎯 Recommendations

### Short-term (Next Test Run):

1. **Accept Test Failures for Citations < 3:**
   - Tests 2, 6, 7, 8 fail due to LLM behavior, not code bugs
   - Review actual answers to verify quality
   - If answers are good but citations few → test expectation is wrong

2. **Check Test 5 Server Logs:**
   ```powershell
   Select-String "\[DIAGNOSTIC\].*Vision gating: OFF" logs\server.log -Context 3,3
   ```
   - Will show why Vision didn't run
   - Check if docs have pdf_path after enrichment

3. **Check Test 1, 4 Page Selection:**
   ```powershell
   Select-String "\[DIAGNOSTIC\].*P&ID override" logs\server.log
   ```
   - Verify P&ID detection and override logic

### Medium-term:

1. **Improve Prompt Engineering:**
   - Make citation instruction more explicit
   - Use few-shot examples
   - Consider structured output JSON mode

2. **Adjust Test Expectations:**
   - Change min_results from 3 to 1 for citation checks
   - Focus on context_count (already ≥3 in all tests)
   - Or add quality check instead of quantity

3. **Fix P&ID Page Selection:**
   - Once we have diagnostic logs showing why override doesn't trigger
   - May need to adjust center threshold or tag detection

### Long-term:

1. **Use Structured Output (JSON Mode):**
   ```python
   enable_structured_output: bool = True
   ```
   - Enforce citation schema at LLM output level
   - Guarantee minimum citations if sources exist

2. **Improve Context Quality:**
   - Better retrieval to get more diverse sources
   - Better reranking to surface relevant docs

---

## 📝 Test Expectations vs Reality

### Current Test Logic:
```python
if citations_count >= expected["min_results"]:
    test_case.logs.append(f"✅ Citations count: {citations_count}")
else:
    test_case.logs.append(f"❌ Citations count: {citations_count}")
    passed = False
```

### Problem:
- Expects min 3 citations regardless of answer length/complexity
- Doesn't consider answer quality

### Better Approach:
```python
# Check context count (Fix 3 - rerank safety)
if context_count >= 3:
    ✅ Fix 3 working

# Check citations exist (not count)
if citations_count > 0:
    ✅ LLM is citing sources

# Quality check (manual review)
- Is answer accurate?
- Are citations relevant?
- Is answer concise or verbose?
```

---

## 🔄 Next Steps

1. **Run test again:** `python test_vision_citation_fixes.py`

2. **Collect logs:**
   ```powershell
   Select-String "\[DIAGNOSTIC\]" logs\server.log | Out-File diagnostic_full.txt
   ```

3. **Analyze results:**
   - Test 5: Check why Vision OFF (should have diagnostic logs now)
   - Test 2, 6, 7, 8: Review answer quality despite few citations
   - Test 1, 4: Check P&ID page selection logs

4. **Decision matrix:**
   ```
   If Test 5 PASS → Fix 4 (enrichment) working ✅
   If Test 5 FAIL → Check diagnostic logs for root cause

   If Test 2/6/7/8 answers are good → Adjust test expectations
   If Test 2/6/7/8 answers are bad → Improve prompts
   ```

---

**Status:** ✅ Corrected approach implemented
**Philosophy:** Fix root causes, not symptoms
**Principle:** Maintain data integrity over cosmetic metrics
