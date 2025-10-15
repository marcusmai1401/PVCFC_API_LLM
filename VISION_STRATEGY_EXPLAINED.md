# TEXT vs VISION STRATEGY - GIẢI THÍCH CHI TIẾT

## 🎯 TÓM TẮT NHANH

**Hiện tại trong Pipeline 1:**
- ✅ Vision **LUÔN BẬT** (không có smart strategy)
- ⚠️ Smart Vision Strategy code tồn tại nhưng **BỊ DISABLED**
- 📝 Lý do: "Always use Vision to combine text + image data for maximum accuracy"

---

## 📊 WORKFLOW HIỆN TẠI (Code thực tế)

```
User Query
    ↓
┌───────────────────────────────────────────┐
│ 1. RETRIEVAL (BM25 + Vector)             │
│    → Top 8-10 chunks/pages                │
└───────────────┬───────────────────────────┘
                ↓
┌───────────────────────────────────────────┐
│ 2. GENERATION STRATEGY CHECK              │
│                                           │
│    enable_vision_generation = True?       │
│    ├─ YES → Try Vision                    │
│    └─ NO  → Skip to Text-only             │
└───────────────┬───────────────────────────┘
                ↓
┌───────────────────────────────────────────┐
│ 3. TRY VISION GENERATION                  │
│                                           │
│  ⚠️ Smart Strategy: DISABLED              │
│     → Vision ALWAYS ON                    │
│                                           │
│  A) Build vision pages list               │
│     ├─ Check retrieved_docs có pdf_path? │
│     ├─ Lookup doc_id_map                  │
│     └─ Max 10 pages                       │
│                                           │
│  B) Render PDF pages → JPEG images        │
│     ├─ DPI: 200                           │
│     ├─ Format: JPEG                       │
│     └─ If ALL fail → fallback Text        │
│                                           │
│  C) Call Gemini 2.5 Pro (Multimodal)     │
│     ├─ Send: Text context + Images       │
│     └─ Get: Answer with citations        │
│                                           │
│  D) Success? → Use Vision Answer ✓        │
│     Fail?    → Fallback to Text ✗         │
└───────────────┬───────────────────────────┘
                ↓
┌───────────────────────────────────────────┐
│ 4. TEXT-ONLY GENERATION (Fallback)       │
│                                           │
│  Call Gemini 2.5 Flash (Text-only)       │
│  ├─ Send: Text context only              │
│  └─ Get: Answer with citations           │
└───────────────┬───────────────────────────┘
                ↓
          Final Answer
```

---

## 🔍 CHI TIẾT TỪNG BƯỚC

### **BƯỚC 1: Check Config**

**File:** \generator.py\ line 509-541

\\\python
if self.config.enable_vision_generation:
    logger.info("Vision gating: ON (config enabled)")
    try:
        vision_result = self._try_vision_generation(...)
        if vision_result:
            # Use vision answer ✓
            vision_answer, vision_citations, vision_meta = vision_result
    except Exception as e:
        logger.warning("Vision failed, falling back to text-only")
else:
    logger.info("Vision gating: OFF (reason=config_disabled)")
\\\

**Config:**
\\\python
GeneratorConfig(
    enable_vision_generation=True,  # Mặc định: ON
)
\\\

---

### **BƯỚC 2: Try Vision Generation**

**File:** \generator.py\ line 1303-1684

#### **2A. Smart Strategy (DISABLED - Line 1316-1319)**

\\\python
# 0) Smart strategy gate DISABLED - Vision always ON
# User requirement: Always use Vision to combine text + image data
strategy_meta = {}
logger.debug("Vision strategy: ALWAYS ON (smart_vision_strategy disabled)")
\\\

**⚠️ Lưu ý:** Code có function \_smart_vision_strategy()\ (line 2361-2435) nhưng **KHÔNG được gọi**!

#### **2B. Build Vision Pages (Line 1339-1362)**

\\\python
pages_plan, pages_meta = self._build_vision_pages(
    retrieved_docs,
    prioritize_visual=False
)

# Check if có pages để render
if not pages_plan:
    # No pages → Skip vision, fallback to text
    logger.warning("Vision gating: OFF (no pages)")
    return None
\\\

**Điều kiện để có pages:**
1. ✅ \etrieved_docs\ có metadata \pdf_path\
2. ✅ Hoặc \doc_id\ có trong \doc_id_map.json\
3. ✅ PDF file tồn tại trên disk
4. ✅ Max 10 pages (\ision_max_pages_total\)

#### **2C. Render PDF Pages (Line 1364-1433)**

\\\python
from tools.pdf_renderer import render_page_to_image

images = []
pages_used = []
pages_failed = []

for item in pages_plan:
    pdf_path = item["pdf_path"]
    page = item["page"]

    try:
        # Render page to JPEG
        img_bytes, meta = render_page_to_image(
            pdf_path, page,
            dpi=200,
            format="jpeg"
        )
        images.append(img_bytes)
        pages_used.append({"pdf_path": pdf_path, "page": page})
    except Exception as e:
        pages_failed.append({"pdf_path": pdf_path, "page": page})

if not images:
    # All renders failed → Skip vision
    logger.info("Vision gating: OFF (all renders failed)")
    return None
\\\

#### **2D. Call Gemini Vision (Line 1525-1637)**

\\\python
from google import genai

# Build prompt with text + images
parts = [
    types.Part(text=prompt_text),  # Text context
    *[types.Part.from_bytes(mime_type="image/jpeg", data=img)
      for img in images]  # Images
]

# Call Gemini 2.5 Pro Multimodal
resp = client.models.generate_content(
    model="models/gemini-2.5-pro",
    contents=[types.Content(role="user", parts=parts)],
    config=types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=2048,
        system_instruction=instruction
    )
)

answer_text = resp.text
citations = self._extract_citations(answer_text, vision_doc_mapping)

return answer_text, citations, vision_meta
\\\

---

### **BƯỚC 3: Fallback to Text (if Vision fails)**

**File:** \generator.py\ line 568-626

\\\python
# Priority: Vision > Structured > Legacy Text
if query.intent == QueryIntent.ASK:
    if vision_answer:
        answer, citations = vision_answer, vision_citations  # ← Use Vision ✓
    elif structured_answer:
        answer, citations = structured_answer, structured_citations
    else:
        # Fallback: Text-only generation
        answer, citations = self._generate_ask_answer_bilingual(
            query, context, doc_mapping, language
        )
\\\

**Text-only generation:**
\\\python
# Call Gemini 2.5 Flash (text-only, faster)
response = llm_client.generate(
    prompt=prompt,  # Text context only, no images
    temperature=0.3,
    max_tokens=2048
)
answer = response.content
citations = self._extract_citations(answer, doc_mapping)
\\\

---

## 🎨 VÍ DỤ CỤ THỂ

### **Ví dụ 1: Vision thành công**

**Input:**
\\\
Query: "Tìm bảng áp suất trong tài liệu K06101"
Retrieved: 5 chunks from doc K06101
\\\

**Processing:**
\\\
1. enable_vision_generation = True ✓
2. Build vision pages:
   - Page 15 (has table)
   - Page 23 (has diagram)
   → 2 pages to render
3. Render PDFs → 2 JPEG images ✓
4. Call Gemini 2.5 Pro:
   - Text: "Context: chunk1, chunk2..."
   - Images: [page15.jpg, page23.jpg]
   → Answer: "Bảng áp suất ở trang 15..." ✓
5. Use Vision Answer ✓
\\\

**Output:**
\\\json
{
  "answer": "Bảng áp suất tối đa là 25 bar [Doc 1, p.15]",
  "citations": [{"doc_id": "K06101", "page": 15}],
  "metadata": {
    "model": "gemini-2.5-pro",
    "vision_generation": {
      "pages_used": [{"page": 15}, {"page": 23}],
      "pages_failed": []
    }
  }
}
\\\

---

### **Ví dụ 2: Vision fail → Fallback Text**

**Input:**
\\\
Query: "Nhiệt độ tối thiểu?"
Retrieved: 5 chunks (NO pdf_path in metadata)
\\\

**Processing:**
\\\
1. enable_vision_generation = True ✓
2. Build vision pages:
   - Check metadata: NO pdf_path ✗
   - Check doc_id_map: No entries found ✗
   → pages_plan = [] (empty)
3. Vision gating: OFF (no pages) ✗
4. Fallback to Text-only:
   - Call Gemini 2.5 Flash
   - Text context only (no images)
   → Answer: "Nhiệt độ tối thiểu là 10°C [Doc 2]" ✓
5. Use Text Answer ✓
\\\

**Output:**
\\\json
{
  "answer": "Nhiệt độ tối thiểu là 10°C [Doc 2]",
  "citations": [{"doc_id": "DOC_456", "page": 8}],
  "metadata": {
    "model": "gemini-2.5-flash",
    "vision_generation": null
  }
}
\\\

---

## ⚙️ CONFIG OPTIONS

**File:** \generator.py\ GeneratorConfig

\\\python
class GeneratorConfig:
    # Vision controls
    enable_vision_generation: bool = True
    vision_model: str = "models/gemini-2.5-pro"
    vision_max_pages_total: int = 10
    pdf_render_dpi: int = 200
    pdf_image_format: str = "jpeg"

    # Smart strategy (HIỆN TẠI BỊ DISABLED)
    enable_smart_vision_strategy: bool = True  # Not used!
    vision_skip_text_only: bool = True         # Not used!
\\\

**Cách thay đổi:**

\\\python
# Tắt Vision hoàn toàn
config = GeneratorConfig(
    enable_vision_generation=False
)

# Thay đổi max pages
config = GeneratorConfig(
    enable_vision_generation=True,
    vision_max_pages_total=5  # Chỉ render 5 pages
)
\\\

---

## 🔍 SMART VISION STRATEGY (Code tồn tại nhưng KHÔNG dùng)

**Location:** \generator.py\ line 2361-2435

**Logic (nếu được enable):**

\\\python
def _smart_vision_strategy(query, retrieved_docs):
    # Check query có từ khóa visual?
    visual_keywords = ["table", "figure", "bảng", "biểu đồ", "diagram"]

    if any(kw in query.lower() for kw in visual_keywords):
        return {"should_use_vision": True, "reason": "visual_keywords"}

    # Check retrieved docs có visual content?
    for doc in retrieved_docs[:5]:
        if any(kw in doc.text.lower() for kw in visual_keywords):
            return {"should_use_vision": True, "reason": "docs_have_visuals"}

    # Không có visual cues
    if vision_skip_text_only:
        return {"should_use_vision": False, "reason": "text_only"}

    return {"should_use_vision": True, "reason": "default_allow"}
\\\

**⚠️ Hiện tại:** Function này **TỒN TẠI** nhưng **KHÔNG được gọi** (line 1316-1319 disabled)

---

## 📋 TÓM TẮT

| Aspect | Hiện trạng |
|--------|------------|
| **Vision Strategy** | ❌ Smart strategy DISABLED |
| **Vision Mode** | ✅ Always ON (nếu có pages) |
| **Fallback** | ✅ Automatic (nếu vision fail) |
| **Model cho Vision** | Gemini 2.5 Pro |
| **Model cho Text** | Gemini 2.5 Flash |
| **Max Pages** | 10 pages |
| **Image Format** | JPEG @ 200 DPI |

---

## 🎯 DECISION TREE THỰC TẾ

\\\
Query
  │
  ├─ enable_vision_generation = False?
  │  └─ NO → Use Text-only (Gemini Flash)
  │
  └─ enable_vision_generation = True?
     │
     ├─ Có pages để render?
     │  ├─ NO → Fallback Text-only
     │  └─ YES → Continue
     │
     ├─ Render thành công?
     │  ├─ NO (all fail) → Fallback Text-only
     │  └─ YES → Continue
     │
     ├─ Call Gemini Vision
     │  ├─ Success → Use Vision Answer ✓
     │  └─ Fail → Fallback Text-only
     │
     └─ Final: Vision Answer hoặc Text Answer
\\\

---

**Generated:** 2025-10-15 00:57:48
