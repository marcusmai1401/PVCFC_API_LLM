# CHANGELOG - Vision Generation (Gemini 2.5 Pro)

## Tổng quan
Triển khai multimodal answer generation với Gemini 2.5 Pro. Vision dùng để TẠO ĐÁP ÁN (không verify riêng).

## Files đã sửa

### 1. `app/core/llm_constants.py`
- **Line 7**: Thêm `VISION_MODEL = "models/gemini-2.5-pro"`
- **Lines 118-171**: Cập nhật `RECOMMENDED_MODELS` → Heavy=2.5-pro, Light=2.5-flash
- **Lines 175-186**: Sửa docstring function `is_valid_model()` (thiếu)

### 2. `app/rag/schemas.py`
- **Lines 28-33**: Thêm field `enable_vision_generation: bool = True` vào `AskRequest`

### 3. `app/api/routers/ask.py`
- **Line 96**: Đọc `enable_vision_generation` từ request an toàn
- **Lines 386-390**: Propagate `vision_generation` metadata vào response

### 4. `app/rag/generator.py`
- **Lines 305-311**: Thêm vision config vào `GeneratorConfig`
- **Lines 328-343**: ENV override cho vision settings + log resolved model
- **Lines 398-420**: Vision gating logic với logging rõ ràng (ON/OFF + reason)
- **Lines 1026-1214**: `_try_vision_generation()` - multimodal generation pipeline
- **Lines 1216-1292**: `_build_vision_pages()` - page selection với validation:
  - Validate `page_start/end` cả 2 phải có và không None
  - Window ±2 cho single page (fix bug `max(start, center+2)`)
  - Clamp theo total_pages nếu có
  - Dedup (pdf_path, page)
- **Lines 1096-1104**: Validate `doc_mapping` và `images` trước khi gọi Gemini
- **Line 1193**: Exception handling có logging ERROR với message

### 5. `docs/DOCS_NEW_Features/Gemini_Vision_Models_Guide.md`
- **Toàn bộ file**: Viết lại hoàn toàn cho Vision = 2.5 Pro multimodal generation

### 6. `tests/test_vision_integration.py`
- **New file**: Unit tests cho page selection (4 cases) + vision gating (2 cases)

### 7. `scripts/vision_logging_smoke.py`
- **New file**: Smoke test để validate logging paths (Vision ON/OFF)

## Lý do thay đổi
1. Chuyển từ 1.5-pro sang 2.5-pro (model mới, tốt hơn)
2. Vision dùng cho generation (không verify), giảm latency
3. Page selection cần validation chặt chẽ để tránh bug
4. Logging rõ ràng để debug production
5. Metadata đầy đủ cho monitoring

## Breaking changes
- Không có (backward compatible, flag mặc định `true`)
