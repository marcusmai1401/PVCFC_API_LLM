# 📚 Example Scripts

Các script mẫu và ví dụ cách sử dụng các tính năng của hệ thống.

---

## 📁 FILES

### **`example_gemini_usage.py`**

**Mô tả**: Ví dụ toàn diện về cách sử dụng Gemini API trong application

**Tính năng**:
- Hiển thị tier configuration (light vs heavy)
- Simple chat example với cả 2 tiers
- Industrial Q&A examples
- Document analysis use case
- Cost optimization strategy

**Sử dụng**:
```bash
python scripts/examples/example_gemini_usage.py
```

**Output mẫu**:
```
🚀 GEMINI API USAGE EXAMPLES

============================================================
TIER CONFIGURATION
============================================================
Light Tier:
  Provider: gemini
  Model: gemini-1.5-flash

Heavy Tier:
  Provider: gemini
  Model: gemini-1.5-pro

API Key: GEMINI_API... (configured)

============================================================
SIMPLE CHAT EXAMPLE
============================================================

1. LIGHT TIER (gemini-1.5-flash):
----------------------------------------
Response: A PLC (Programmable Logic Controller) is an industrial computer...

2. HEAVY TIER (gemini-1.5-pro):
----------------------------------------
Response: A Programmable Logic Controller (PLC) is a ruggedized computer...
```

**Status**: ✅ ACTIVE

---

## 🎯 Khi nào nên dùng

### Example này hữu ích khi:
1. **Bạn mới bắt đầu** với Gemini API
2. **Cần hiểu tier strategy**: Khi nào dùng light, khi nào dùng heavy
3. **Debug Gemini integration**: Kiểm tra API key và connection
4. **Tham khảo use cases**: Học cách implement các tình huống thực tế
5. **Cost optimization**: Hiểu cách tiết kiệm chi phí với multi-tier

---

## 📖 LEARNING PATH

### 1. Chạy example đầu tiên
```bash
python scripts/examples/example_gemini_usage.py
```

### 2. Đọc code để hiểu structure
```python
# app/services/llm.py
- get_provider_for(tier)
- get_model_for(tier)
- get_api_key_for(provider)
```

### 3. Áp dụng vào code của bạn
```python
from app.services.llm import get_model_for
from google import genai

client = genai.Client(api_key=get_api_key_for("gemini"))
model = genai.GenerativeModel(get_model_for("light"))
response = model.generate_content("Your prompt here")
```

---

## 💡 BEST PRACTICES (từ example)

### Cost Optimization
```
1. LIGHT TIER (gemini-1.5-flash) - Use for:
   ✓ Document parsing and extraction
   ✓ Simple Q&A and lookups
   ✓ Data formatting and transformation
   ✓ Development and testing
   Cost: ~$0.075 per 1M input tokens

2. HEAVY TIER (gemini-1.5-pro) - Use for:
   ✓ Complex technical analysis
   ✓ Final customer-facing responses
   ✓ Critical decision support
   ✓ Multi-step reasoning tasks
   Cost: ~$3.50 per 1M input tokens

💡 Using tiers appropriately can reduce costs by 80-90%!
```

---

## 🚀 NEXT STEPS

### Thêm examples mới
Nếu bạn tạo example scripts mới, đặt chúng trong folder này:

```bash
scripts/examples/
├── README.md                    ← File này
├── example_gemini_usage.py      ← Example hiện tại
├── example_rag_pipeline.py      ← (Future) End-to-end RAG
├── example_pdf_processing.py    ← (Future) PDF ingestion
└── example_streamlit_ui.py      ← (Future) UI components
```

### Format cho examples mới
```python
#!/usr/bin/env python3
\"\"\"
Brief description of what this example demonstrates
\"\"\"

def example_function_1():
    \"\"\"Clear docstring\"\"\"
    pass

def example_function_2():
    \"\"\"Another example\"\"\"
    pass

def main():
    \"\"\"Run all examples with clear output\"\"\"
    print("=" * 60)
    print("EXAMPLE TITLE")
    print("=" * 60)

    example_function_1()
    example_function_2()

    print("\\n✅ All examples completed!")

if __name__ == "__main__":
    main()
```

---

**Status**: ✅ Ready to use
**Last updated**: 2025-10-01
