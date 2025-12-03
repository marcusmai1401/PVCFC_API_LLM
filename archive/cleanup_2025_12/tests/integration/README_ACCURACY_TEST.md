# RAG API Accuracy Test Suite

## Overview

This test suite validates the end-to-end accuracy of the RAG API with:
- **4 real-world test cases** (alternating Vietnamese/English)
- **Query classification validation** (P&ID vs Technical Doc)
- **Answer accuracy evaluation** using LLM-as-judge
- **Citation correctness checking**

## Test Cases

### Q1: Vietnamese - P&ID Query
**Question:** Trong Urea Unit, đối với turbine hơi dẫn động máy nén CO₂ (mã KT06101), điều kiện hơi vào turbine ở chế độ normal là bao nhiêu?

**Expected:** 39 bar(a) and 370 °C from Data Sheet

**Type:** P&ID (equipment tag query)

---

### Q2: English - Technical Doc Query
**Question:** According to the operation and maintenance manual for the HCD025 gear unit, what are the specified setpoints for lubricating oil pressure?

**Expected:** Normal: 2.0 barG, Alarm: 1.2 barG, Trip: 0.8 barG

**Type:** Technical Document

---

### Q3: Vietnamese - Technical Doc Query
**Question:** Theo biểu đồ hiệu suất dự kiến của máy nén CO2, tốc độ vận hành 100% là bao nhiêu RPM?

**Expected:** 7800 / 13277 RPM

**Type:** Technical Document

---

### Q4: English - P&ID Query
**Question:** For Tag No. 06-TE-0256 A/B, what is the measurement point and high-temperature alarm setpoint?

**Expected:** Measurement Point: Rear Journal Bearing, Alarm: 105 °C

**Type:** P&ID

## Running the Tests

### Prerequisites

1. **API Server must be running:**
   ```powershell
   .\launchers\start_api.ps1
   ```

2. **Virtual environment activated:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

### Run Tests

**Option 1: Using launcher (recommended)**
```powershell
.\launchers\run_accuracy_test.ps1
```

**Option 2: Direct Python**
```powershell
python tests\integration\test_query_classification_accuracy.py
```

## Output

### Console Output
The script will print:
- Progress for each test case
- Answer scores and validation results
- Citation matching status
- Query classification accuracy
- Final summary report

### JSON Report
Detailed results saved to:
```
artifacts/test_reports/rag_accuracy_test_YYYYMMDD_HHMMSS.json
```

### Example Output
```
============================================================
Starting RAG Accuracy Test Suite (4 tests)
============================================================

[1/4] Running: Q1_VN_PID
  Language: vi
  Question: Trong Urea Unit, đối với turbine hơi...
  ✓ Query executed: Q1_VN_PID (15234ms)
  Answer Score: 0.95 - ✓ PASS
  Citation Score: 1.00 - ✓ MATCH
  Classification: pid

[2/4] Running: Q2_EN_TECH
  ...

============================================================
TEST SUMMARY
============================================================
Total Tests:              4
Successful Queries:       4
Answer Accuracy:          100.0% (4/4)
Citation Accuracy:        100.0% (4/4)
Classification Accuracy:  100.0% (4/4)
Avg Answer Score:         0.94/1.00
Avg Citation Score:       0.88/1.00
Avg Response Time:        12500ms
============================================================
```

## Evaluation Criteria

### Answer Accuracy
- **Method:** LLM-as-judge (Gemini 2.5 Pro)
- **Criteria:** Semantic match - actual answer must contain key facts from expected answer
- **Threshold:** Score ≥ 0.6 for PASS
- **Fallback:** Keyword matching if LLM judge fails

### Citation Correctness
- **Method:** Fuzzy document name matching
- **Criteria:** At least one citation must reference the expected document
- **Score:** 0.5 per relevant citation (max 1.0 for 2+ citations)

### Classification Accuracy
- **Method:** Exact match
- **Criteria:** Query type must match expected (pid/technical_doc)
- **Note:** "auto" is always accepted

## Pass/Fail Criteria

**Test suite PASSES if:**
- Answer accuracy ≥ 75%
- Exit code: 0

**Test suite FAILS if:**
- Answer accuracy < 75%
- Any API connection errors
- Exit code: 1

## Troubleshooting

### API Not Available
```
Error: Cannot connect to API at http://localhost:8000
```
**Solution:** Start the API server first with `.\launchers\start_api.ps1`

### LLM Judge Failures
If LLM-as-judge fails, the test automatically falls back to keyword matching.
Check Gemini API key and rate limits.

### Timeout Errors
Default timeout is 120 seconds per query. For slow systems, increase in script:
```python
timeout=180  # Line 165
```

## Extending the Test Suite

To add new test cases, edit `test_query_classification_accuracy.py`:

```python
TestCase(
    id="Q5_VN_NEW",
    question="Your question here",
    language="vi",
    expected_answer="Expected answer",
    expected_source="Source reference",
    expected_doc_name="Document name",
    expected_query_type="pid",  # or "technical_doc"
)
```

## Architecture

```
test_query_classification_accuracy.py
├── TestCase: Test data structure
├── TestResult: Result container
└── RAGTester: Test orchestration
    ├── create_test_cases(): Define tests
    ├── run_query(): Execute API call
    ├── evaluate_answer(): LLM-as-judge
    ├── evaluate_citations(): Doc matching
    ├── evaluate_classification(): Type check
    └── generate_report(): JSON output
```

## Dependencies

- `requests`: HTTP client
- `loguru`: Logging
- `app.services.llm_client`: LLM judge (Gemini 2.5 Pro)

All dependencies included in project venv.
