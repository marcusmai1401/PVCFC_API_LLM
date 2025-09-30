# Gemini Vision Models (PVCFC RAG) — Dùng Gemini 2.5 Pro multimodal để TẠO ĐÁP ÁN

## 1) TL;DR
- Hai tier cố định: Heavy = Gemini 2.5 Pro (multimodal), Light = Gemini 2.5 Flash.
- Vision được dùng để tạo đáp án (multimodal reasoning) từ NGỮ CẢNH VĂN BẢN + ẢNH TRANG PDF.
- Luôn dùng Gemini 2.5 Pro cho Vision. 2.5 Flash chỉ cho text-only.
- Không dùng pipeline hai bước “caption → phân tích”; gọi trực tiếp multimodal 2.5 Pro với text + ảnh.
- Legacy (1.5, pro-vision) chỉ để tương thích, không dùng mặc định.

## 2) Khi nào bật Vision
- Bật Vision khi retrieval có tài liệu map được pdf_path (doc_id_map).
- Nếu retrieval rỗng (không có tài liệu) → KHÔNG gọi Vision, trả lời text-only như hiện tại.

## 3) Mô hình & alias
- Alias map sang định danh “models/...” trước khi gọi API:
  - Heavy: gemini-2.5-pro → models/gemini-2.5-pro
  - Light: gemini-2.5-flash → models/gemini-2.5-flash
  - Vision: VISION_MODEL = models/gemini-2.5-pro

## 4) Cấu hình .env (đọc nếu có, fallback default)
```ini
GEMINI_API_KEY=...
VISION_MODEL=models/gemini-2.5-pro
VISION_MAX_PAGES_TOTAL=10
PDF_RENDER_DPI=200
PDF_IMAGE_FORMAT=jpeg
VISION_TIMEOUT_SEC=20
VISION_RETRY=2
```

## 5) Multimodal generation (google-genai, Gemini 2.5 Pro)
- Phối hợp text context + ảnh trang PDF.
- API ảnh: GET /api/pdf/render-page?pdf_path=...&page_num=...&dpi=200&format=jpeg
- Nội dung gửi cho model: [system_instruction] + [prompt text (có context + mapping Doc/page)] + [1..N ảnh]

Ví dụ rút gọn:
```python
from google import genai
from google.genai import types

client = genai.Client(api_key=GEMINI_API_KEY)
model_name = "models/gemini-2.5-pro"

instruction = "Use the provided text context and attached PDF page images. Always cite [Doc X, p.Y]."
prompt_text = "Question: ...\nContext:\n...\nDoc mapping: Doc 1 -> <docid1>, Doc 2 -> <docid2>\nAttached pages: (Doc 1, p.12), (Doc 2, p.3)\nAnswer:"

parts = [types.Part.from_text(prompt_text)]
for img_bytes in images:
    parts.append(types.Part.from_bytes(mime_type="image/jpeg", data=img_bytes))

cfg = types.GenerateContentConfig(temperature=0.2, max_output_tokens=1200, system_instruction=instruction)
resp = client.models.generate_content(model=model_name, contents=[types.Content(role="user", parts=parts)], config=cfg)
print(resp.text)
```

## 6) Lựa chọn trang & giới hạn
- Quy ước trang 1-based.
- VISION_MAX_PAGES_TOTAL = 10.
- Nếu có page_start/page_end → lấy toàn bộ range (cắt bớt nếu vượt quota).
- Nếu chỉ có page đơn → lấy cửa sổ ±2 quanh page (cắt bớt theo quota). Khi có tổng trang PDF, hãy clamp về [1..total_pages].

## 7) Tích hợp vào generator (flow)
1) Sau retrieval: build context text như hiện tại.
2) Từ top kết quả → chọn trang theo (6) → render ảnh qua tools.pdf_renderer hoặc endpoint /api/pdf/render-page.
3) Gọi models/gemini-2.5-pro kèm: instruction + prompt (context + mapping) + ảnh.
4) Nhận final answer (không verify rời). Trích citation inline theo [Doc X, p.Y].
5) Ghi metadata vào response:
```json
"vision_generation": {
  "pages_used": [{"pdf_path": "D:\\...\\manual.pdf", "page": 12}],
  "pages_failed": [{"pdf_path":"D:\\...\\file.pdf","page":4,"reason":"timeout"}],
  "excerpts": []
}
```

## 8) UI/Backend ghi chú
- Không thay đổi ingest/index.
- Không ép ngôn ngữ: trả lời theo ngôn ngữ truy vấn.
- Nếu không có tài liệu/map pdf_path → bỏ qua Vision, trả lời text-only.

## 9) Acceptance Criteria
- RECOMMENDED_MODELS: 2.5 Pro/Flash; Vision = 2.5 Pro.
- AskRequest có enable_vision_generation=True mặc định.
- Khi có tài liệu: generator gọi 2.5 Pro multimodal (context text + ảnh trang, ≤10 trang).
- Ảnh lỗi được bỏ qua, log vào pages_failed.
- Response.meta chứa vision_generation.
- Không dùng model 1.5/pro-vision làm mặc định (chỉ legacy/compat).
- “Các model 1.5 và `gemini-pro-vision` thuộc legacy; không dùng làm mặc định trong PVCFC RAG.”
