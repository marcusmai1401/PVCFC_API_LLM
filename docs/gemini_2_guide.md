# Hướng dẫn sử dụng Gemini 2.0 Flash

## Tổng quan

Gemini 2.0 Flash Experimental là model mới nhất của Google với khả năng reasoning và thinking được cải thiện đáng kể so với phiên bản 1.5.

## Ưu điểm của Gemini 2.0 Flash

### So với Gemini 1.5 Flash:
- ✅ **Reasoning tốt hơn**: Giải quyết bài toán phức tạp với logic rõ ràng
- ✅ **Tính toán chính xác**: Thực hiện phép tính và hiển thị từng bước
- ✅ **Code generation**: Viết code tốt hơn với ít lỗi hơn
- ✅ **Context understanding**: Hiểu ngữ cảnh sâu hơn

### So với Gemini 1.5 Pro:
- ✅ **Nhanh hơn**: Response time nhanh hơn đáng kể
- ✅ **Rẻ hơn**: Chi phí thấp hơn nhiều
- ✅ **Quota cao hơn**: Free tier cho phép nhiều request hơn

## Cấu hình trong .env

```env
# Sử dụng Gemini 2.0 Flash làm light tier (recommended)
LLM_PROVIDER=gemini
LLM_TIER=light
LLM_MODEL_LIGHT=gemini-2.0-flash-exp
LLM_MODEL_HEAVY=gemini-1.5-pro
GEMINI_API_KEY=your_api_key_here
```

## Use Cases phù hợp

### 1. Document Analysis & Extraction
```python
# Gemini 2.0 Flash rất tốt cho việc extract structured data
prompt = """
Extract technical specifications from this datasheet:
[document content]
Format as JSON with fields: model, power, voltage, current
"""
```

### 2. Industrial Calculations
```python
# Tính toán kỹ thuật với reasoning
prompt = """
Motor: 50HP, 380V, 3-phase, efficiency 92%, power factor 0.88
Calculate:
1. Full load current
2. Power consumption in kW
Show calculations step by step.
"""
```

### 3. Technical Q&A
```python
# Trả lời câu hỏi kỹ thuật với giải thích
prompt = """
Explain the difference between Star and Delta motor connection.
Include voltage/current relationships and when to use each.
"""
```

### 4. Code Generation
```python
# Viết code cho industrial automation
prompt = """
Write a Python function to calculate VFD output frequency
based on desired motor RPM and number of poles.
Include error handling and documentation.
"""
```

## API Limits (Free Tier)

### Gemini 2.0 Flash Experimental
- **Requests per minute**: 15
- **Requests per day**: 1,500
- **Input tokens**: ~1M per minute

### Gemini 1.5 Pro (for comparison)
- **Requests per minute**: 2
- **Requests per day**: 50
- **Input tokens**: ~32K per minute

## Best Practices

### 1. Sử dụng Gemini 2.0 Flash cho hầu hết tasks
```python
# Light tier với gemini-2.0-flash-exp
provider = get_provider_for("light")
model = get_model_for("light")  # gemini-2.0-flash-exp
```

### 2. Chỉ dùng Gemini 1.5 Pro khi thực sự cần
```python
# Heavy tier chỉ cho critical tasks
if task_importance == "critical":
    model = get_model_for("heavy")  # gemini-1.5-pro
```

### 3. Handle quota errors gracefully
```python
try:
    response = model.generate_content(prompt)
except Exception as e:
    if "quota" in str(e).lower():
        # Fallback to cached response or queue for later
        return get_cached_response(prompt)
```

## Migration từ Gemini 1.5 sang 2.0

### Không cần thay đổi code
Code hiện tại sẽ hoạt động bình thường, chỉ cần update model name trong .env:

```bash
# Từ
LLM_MODEL_LIGHT=gemini-1.5-flash

# Sang
LLM_MODEL_LIGHT=gemini-2.0-flash-exp
```

### Response format tương tự
Gemini 2.0 Flash giữ nguyên format response, có thể drop-in replacement.

## Monitoring & Testing

### Test script
```bash
# Test cơ bản
python test_gemini_2_flash.py

# Test với real use cases
python example_gemini_usage.py
```

### Check model performance
```python
import time

start = time.time()
response = model.generate_content(prompt)
latency = time.time() - start

print(f"Model: {model_name}")
print(f"Latency: {latency:.2f}s")
print(f"Token count: {response.usage_metadata.total_token_count}")
```

## Troubleshooting

### 1. Model not found
```
Error: 404 Model not found
```
**Solution**: Check model name spelling: `gemini-2.0-flash-exp` (có `-exp` ở cuối)

### 2. Quota exceeded
```
Error: 429 Quota exceeded
```
**Solution**:
- Wait 1 minute and retry
- Use caching for repeated queries
- Consider paid plan for production

### 3. Thinking budget
Gemini 2.0 có "thinking" capability nhưng experimental API chưa expose parameter này.

## Roadmap

- **Current**: Gemini 2.0 Flash Experimental
- **Q1 2025**: Gemini 2.0 Flash Stable (expected)
- **Future**: Gemini 2.0 Pro với advanced reasoning

## Links

- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [Pricing](https://ai.google.dev/pricing)
- [API Console](https://aistudio.google.com/app/apikey)
