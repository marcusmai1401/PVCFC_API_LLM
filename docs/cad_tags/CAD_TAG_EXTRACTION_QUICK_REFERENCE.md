# CAD Tag Extraction - Quick Reference Card

## 🚀 1-Minute Setup

```powershell
# 1. Enable in .env
echo "ENABLE_PID_TAGS=true" >> .env

# 2. Create index
python scripts\opensearch\create_tags_index.py

# 3. Test
python tools\test_tag_extraction.py --pdf "sample.pdf" --doc-id "test"
```

---

## 📂 Key Files

| What | Where |
|------|-------|
| **Enable/disable** | `.env` → `ENABLE_PID_TAGS` |
| **Gate config** | `config/cadlike_gate.yaml` |
| **Grammar/whitelist** | `config/tag_grammar.yaml` |
| **Tuning tolerances** | `config/tag_grammar.yaml` → assembler section |
| **Extracted tags** | `D:\PVCFC_Artifacts\entities\tags.jsonl` |
| **Telemetry logs** | `D:\PVCFC_Artifacts\logs\tag_extraction_telemetry.jsonl` |
| **Crops** | `D:\PVCFC_Artifacts\crops\*.png` |

---

## 🔧 Common Tasks

### Add new instrument CODE:

```yaml
# config/tag_grammar.yaml
code_whitelist:
  - LSAH  # Add your code here
```

### Relax tolerances (if missing tags):

```yaml
# config/tag_grammar.yaml
x_center_tolerance_ratio: 0.70  # Increase from 0.60
y_gap_ratio_range: [0.6, 2.5]   # Widen from [0.7, 2.0]
pass_threshold: 5               # Lower from 6
```

### Check why doc not CAD-like:

```python
from app.ingestion.cadlike_gate import get_cadlike_gate
from pathlib import Path

gate = get_cadlike_gate()
decision = gate.evaluate(Path("doc.pdf"))
print(f"Score: {decision.score:.2f}, CAD-like: {decision.is_cadlike}")
print(f"Features: {decision.features}")
```

### View telemetry for document:

```powershell
Get-Content "D:\PVCFC_Artifacts\logs\tag_extraction_telemetry.jsonl" |
  ConvertFrom-Json |
  Where-Object { $_.doc_id -eq "your_doc_id" } |
  Format-List
```

---

## ⚡ Commands

| Task | Command |
|------|---------|
| Create index | `python scripts\opensearch\create_tags_index.py` |
| Test single PDF | `python tools\test_tag_extraction.py --pdf "file.pdf"` |
| Bulk upsert tags | `python scripts\opensearch\bulk_upsert_tags.py` |
| Smoke tests | `python tests\smoke_test_tags.py` |
| Check index health | `curl http://localhost:9200/pvcfc_pid_tags/_stats` |

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Tags index not found" | Run `create_tags_index.py` |
| "Zero tags extracted" | Check telemetry warnings → tune tolerances |
| "Too many false positives" | Add exclusion patterns to `page_filters.yaml` |
| "Unknown CODE logged" | Add to whitelist in `tag_grammar.yaml` |
| "Crops not generated" | Check `LAZY_CROP_GENERATION` or run with `--enable-crops` |
| "High OCR ratio warning" | Normal if corpus has scanned PDFs; ignore or investigate |

---

## 📊 Telemetry Warnings

| Warning | Meaning | Action |
|---------|---------|--------|
| "CAD-like but zero tags" | Gate passed but extractor found nothing | Relax tolerances or check if tags exist |
| "High OCR ratio" | Many pages used OCR | OK if scanned PDFs; investigate if should be vector |
| "Low avg triplet score" | Scores barely passing threshold | Relax tolerances |
| "Low tag density" | Few tags despite high CAD score | Check taggy page selection or tolerances |

---

## 🎯 Smoke Test Queries

```
1. "PSAL 2207"           → Direct tag
2. "PAL 2208"            → Direct tag
3. "PI 2046A"            → Trailing letter
4. "FIC 2910"            → Direct tag
5. "PT 2511B"            → Suffix B
6. "04 PSAL 2207"        → Full AREA+CODE+NUM
7. "PAL 2208 A/B/C"      → Suffix A/B/C
8. "PSU 2oo3"            → Voting suffix
9. "PI -201B"            → Negative suffix
10. "cảm biến áp suất 2207"     → Semantic (Vietnamese)
11. "báo động áp suất 2208"     → Semantic (Vietnamese)
12. "flow indicator 2910"        → Semantic (English)
```

**Pass target**: ≥ 90% (11+/12)

---

**Full docs**: `CAD_TAG_EXTRACTION_QUICKSTART.md`
**Implementation summary**: `CAD_TAG_EXTRACTION_IMPLEMENTATION_SUMMARY.md`
