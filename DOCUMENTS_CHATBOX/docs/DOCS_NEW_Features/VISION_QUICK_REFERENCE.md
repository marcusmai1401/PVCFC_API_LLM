# Vision 2.5 Pro - Quick Reference

## 🎯 TL;DR
- **Heavy = gemini-2.5-pro** (multimodal)
- **Light = gemini-2.5-flash** (text-only)
- Vision dùng để **TẠO ĐÁP ÁN** (không verify riêng)
- Max **10 pages** per query, **1-based**, **DPI=200**, **JPEG**

## 📝 Files bàn giao

| File | Mô tả |
|------|-------|
| `VISION_HANDOVER_REPORT.md` | Báo cáo đầy đủ (A/B/C/D/E) |
| `CHANGELOG_VISION_2.5_PRO.md` | Changelog chi tiết |
| `VISION_API_EXAMPLES.md` | Request/response examples |
| `.env.example.vision` | Environment config |
| `docs/DOCS_NEW_Features/Gemini_Vision_Models_Guide.md` | Full guide |
| `tests/test_vision_integration.py` | Unit tests (6/6 PASS) |
| `scripts/vision_logging_smoke.py` | Smoke test script |

## ⚡ Quick commands

```bash
# Run unit tests
python -m pytest tests/test_vision_integration.py -v

# Run smoke test (see logs)
python scripts/vision_logging_smoke.py

# Verify model constants
python -c "from app.core.llm_constants import VISION_MODEL; print(VISION_MODEL)"
```

## 🔍 Key logs to watch

```
# Vision ON
INFO - Vision gating: ON (config enabled)
INFO - Vision pages: used=5, failed=0, total_limit=10; pages=[10, 11, 12, 13, 14]
INFO - Vision generation succeeded with 5 pages

# Vision OFF
INFO - Vision gating: OFF (reason=no_docs_or_mapping)
```

## 📊 Response metadata

```json
{
  "meta": {
    "model": "gemini-2.5-pro",
    "vision_generation": {
      "pages_used": [
        {"pdf_path": "...", "page": 10},
        {"pdf_path": "...", "page": 11}
      ],
      "pages_failed": [],
      "excerpts": []
    }
  }
}
```

## ✅ Checklist hoàn tất

- [x] Model = 2.5 Pro (verified)
- [x] Vision gating logic (tested)
- [x] Page selection (unit tests pass)
- [x] Metadata propagation (verified)
- [x] Logging (smoke test pass)
- [x] Documentation (complete)
- [x] **READY FOR PRODUCTION**

## 📞 Troubleshooting

| Issue | Check |
|-------|-------|
| Vision không chạy | Log có `Vision gating: OFF (reason=...)` |
| Pages = 0 | Check `doc_id_map.json` exists |
| Model sai | Check `VISION_MODEL` env var |
| Render fail | Check `pages_failed` in metadata |

---

**Full details:** See `VISION_HANDOVER_REPORT.md`
