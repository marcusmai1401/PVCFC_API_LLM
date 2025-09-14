# Gemini 2.5 Setup và Testing

## Tổng quan
- Gemini 2.5 là phiên bản mới nhất từ Google với hiệu suất và tốc độ cải thiện.
- Hai model chính:
  - **gemini-2.5-flash**: nhanh, rẻ → dùng cho LLM tầng nhẹ
  - **gemini-2.5-pro**: chất lượng cao → dùng cho LLM tầng nặng

## Cách lấy API key
1. Truy cập: https://aistudio.google.com/app/apikey
2. Tạo API key mới
3. Copy key (dạng: `AIzaSy...`)

## Cấu hình trong dự án

### Cách 1: Environment variable (khuyến nghị)
```powershell
# PowerShell - chỉ cho session hiện tại
$env:GEMINI_API_KEY="AIzaSyCPHMNzw-nfAc1G2S4GXxhskLVrqnzg-Vg"

# Kiểm tra
echo $env:GEMINI_API_KEY
```

### Cách 2: File .env (persistent)
```env
# .env file
GEMINI_API_KEY=AIzaSyCPHMNzw-nfAc1G2S4GXxhskLVrqnzg-Vg
LLM_PROVIDER=gemini
LLM_TIER=light
LLM_MODEL_LIGHT=gemini-2.5-flash
LLM_MODEL_HEAVY=gemini-2.5-pro
```

## Test kết nối

### Cài đặt dependencies
```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Install Gemini client
pip install google-genai
```

### Chạy test
```powershell
# Set API key (nếu chưa có trong .env)
$env:GEMINI_API_KEY="your_key_here"

# Test cả 2 models
python tools/test_gemini_2_5.py
```

### Kết quả mong đợi
```
🧪 Gemini 2.5 Models Test
==================================================
Testing gemini-2.5-flash
==================================================
📝 Prompt: Explain what RAG is in one sentence.
🤖 Response from gemini-2.5-flash:
RAG combines information retrieval with text generation...
------------------------------
✅ gemini-2.5-flash working! Response length: 89 chars

==================================================
Testing gemini-2.5-pro
==================================================
📝 Prompt: Explain what RAG is in one sentence.
🤖 Response from gemini-2.5-pro:
Retrieval-Augmented Generation (RAG) enhances...
------------------------------
✅ gemini-2.5-pro working! Response length: 127 chars

==================================================
📊 TEST SUMMARY
==================================================
gemini-2.5-flash: ✅ PASS
gemini-2.5-pro: ✅ PASS

Results: 2/2 models working
🎉 All Gemini 2.5 models are working!

💡 You can now use:
   LLM_MODEL_LIGHT=gemini-2.5-flash
   LLM_MODEL_HEAVY=gemini-2.5-pro
```

## Tích hợp với app

### Health check
```powershell
# Start app
python -m uvicorn app.main:app --reload --port 8000

# Check status
curl http://localhost:8000/healthz
```

### Sử dụng trong code
```python
from app.services.llm import get_provider_for, get_model_for, get_api_key_for

# Light tier
provider = get_provider_for("light")  # "gemini"
model = get_model_for("light")        # "gemini-2.5-flash"
api_key = get_api_key_for(provider)   # "AIzaSy..."

# Heavy tier
provider = get_provider_for("heavy")  # "gemini"
model = get_model_for("heavy")        # "gemini-2.5-pro"
```

## Troubleshooting

### API key không hoạt động
- Kiểm tra key có đúng format: `AIzaSy...`
- Verify trên AI Studio: https://aistudio.google.com/app/apikey
- Thử tạo key mới

### Model không tồn tại
- Gemini 2.5 có thể chưa available ở một số regions
- Fallback về gemini-1.5-pro/flash nếu cần
- Check model list: https://ai.google.dev/models/gemini

### Rate limiting
- Free tier có giới hạn requests/minute
- Upgrade plan nếu cần throughput cao hơn

## So sánh với OpenAI

| Aspect | Gemini 2.5 Flash | GPT-4o-mini | Gemini 2.5 Pro | GPT-4o |
|--------|------------------|-------------|----------------|---------|
| Speed | ⚡⚡⚡ | ⚡⚡ | ⚡⚡ | ⚡ |
| Cost | 💰 | 💰💰 | 💰💰 | 💰💰💰 |
| Quality | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Context | 1M tokens | 128K tokens | 2M tokens | 128K tokens |

## Khuyến nghị sử dụng
- **Dev/Test**: `gemini-2.5-flash` (nhanh, rẻ)
- **Production**: `gemini-2.5-pro` (chất lượng cao)
- **Mixed setup**: Flash cho query processing, Pro cho final answers
