# Citation Investigation - Setup Complete ✅

**Date**: 2025-10-07
**Status**: Ready for testing

## 📦 Deliverables Created

### 1. Golden Dataset
**File**: `scripts/test_scripts/online_audit/golden_citation_dataset.json`
- ✅ 5 verified Q&A pairs with ground truth citations
- ✅ Mix of VI/EN queries
- ✅ 3 different source documents
- ✅ Structured format with doc_id patterns and page numbers

### 2. Test Script
**File**: `scripts/test_scripts/online_audit/test_citation_accuracy_golden.py`
- ✅ Automated test runner for 5 questions
- ✅ Tests with vision ON and OFF variants (10 total requests)
- ✅ Ground truth comparison (doc + page matching)
- ✅ Detailed logging and error handling
- ✅ JSON output with full API responses for analysis
- ✅ Exit codes: 0 if pass rate ≥60%, 1 if <60%

### 3. Documentation
**Files**:
- ✅ `scripts/test_scripts/online_audit/README.md` - Updated with new test
- ✅ `scripts/test_scripts/online_audit/RUN_CITATION_TEST.md` - Quick start guide

## 🎯 Test Coverage

### Questions Tested
1. **Q1 (VI)**: CO2 compressor stage 3 operating conditions → Page 8
2. **Q2 (EN)**: Polytropic efficiency at specific capacity → Page 5
3. **Q3 (VI)**: Ammonia pump convention inspection parts → Page 1
4. **Q4 (EN)**: Shaft repair action for runout ≥0.15mm → Page 2
5. **Q5 (EN)**: 4th stage rated operating conditions → Page 3

### Documents Covered
- `003_3N4-S4274345 Expected Performance Curve of Compressor_Rev.01.pdf`
- `Ammonia Maintenance Schedule.pdf`
- `002_3N4-S4274343 datasheet for K06101_Rev.02.pdf`

### Test Variants
- Vision enabled (5 requests)
- Vision disabled (5 requests)
- **Total**: 10 requests per run

## 🚀 How to Run

### Prerequisites
```powershell
# 1. Start API server
.\start_api.ps1

# 2. Verify health
curl http://localhost:8000/health
```

### Run Test
```powershell
# Full test (vision on + off)
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py

# Quick test (vision off only)
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py --no-vision
```

### Expected Runtime
- Full test: 5-10 minutes
- Quick test: 3-5 minutes

## 📊 Success Criteria

### Pass Threshold
- **Pass rate ≥ 60%**: At least 3/5 questions with correct doc+page
- Exit code 0 if passed, 1 if failed

### Verdicts
- `✓ PASS` - Correct doc AND exact page
- `~ PARTIAL` - Correct doc, page off by 1
- `✗ FAIL` - Correct doc, page off by 2+
- `✗✗ FAIL` - Wrong doc entirely

## 📁 Output Files

### Console
- Real-time progress for each question
- Verdict for each test case
- Summary statistics at end

### JSON Report
**Location**: `reports/test_results/citation_accuracy_golden_{timestamp}.json`

**Contains**:
- Full API responses (answer, citations, metadata)
- Retrieval results (top 10 docs with scores)
- Doc mapping (enum → doc_id)
- Validation metadata (confidence, corrected_count)
- Vision metadata (pages_used, pages_failed)
- Ground truth comparison (doc match, page distance)

## 🔍 Next Steps Based on Results

### If Pass Rate ≥ 60% ✅
1. Review partial/fail cases in detail
2. Check `page_distance` for patterns
3. Run **Step 2**: Artifact consistency check
4. Continue with steps 3-9 as needed

### If Pass Rate < 60% ⚠️
1. **CRITICAL**: Major citation issues detected
2. Run full investigation plan (steps 2-9)
3. Prioritize:
   - Step 2: Doc map consistency
   - Step 3: Page flow tracing
   - Step 4: Metadata quality
4. Generate detailed root cause analysis

## 🔧 Investigation Plan Status

✅ **Step 0: Test harness** - COMPLETE
- Golden dataset created
- Test script ready
- Documentation complete

⏳ **Step 1-9: Investigation** - READY TO RUN
- Awaiting test results
- Scripts prepared for analysis
- Report templates ready

## 📝 Notes

### Key Features
- **No code modifications**: Pure audit/investigation
- **Reproducible**: Same 5 questions every time
- **Comprehensive**: Full response dumps for deep dive
- **Actionable**: Clear verdicts and next steps

### Limitations
- Requires API server running
- Needs indices loaded
- Assumes doc_id_map.json exists
- Ground truth is manual (5 questions only)

### Future Enhancements
- Expand to 10-20 questions
- Add automated root cause detection
- Integrate with CI/CD
- Add performance benchmarks

---

## ✅ Ready for Testing

**Command to start**:
```powershell
python scripts/test_scripts/online_audit/test_citation_accuracy_golden.py
```

**See details in**: `scripts/test_scripts/online_audit/RUN_CITATION_TEST.md`

---

**Setup by**: AI Investigation Team
**Date**: 2025-10-07
**Status**: ✅ Complete and ready
