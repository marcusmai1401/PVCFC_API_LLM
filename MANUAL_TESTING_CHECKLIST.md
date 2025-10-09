# 📋 Manual Testing Checklist - Week 3 & 4

**Phần cần BẠN làm sau khi tôi hoàn tất auto implementation**

---

## ✅ Các Phần Đã Tự Động Implement (Không Cần Test)

- ✅ FastAPI endpoints (POST /ask, GET /health, GET /metrics)
- ✅ Request/Response models với Pydantic validation
- ✅ Error handling và status codes
- ✅ OpenAPI/Swagger documentation
- ✅ Docker configuration (Dockerfile + docker-compose.yml)
- ✅ Environment configuration (.env.example)
- ✅ Deployment scripts (bash + PowerShell)

---

## 🧪 Phần Cần Test Thủ Công (CẦN BẠN LÀM)

### 1. ⚙️ Setup & Configuration

#### 1.1 Tạo `.env` File
```bash
# Copy example file
cp .env.example .env

# Edit .env và thêm API keys
# - OPENAI_API_KEY=sk-...
# - GEMINI_API_KEY=...
```

**Checklist**:
- [ ] Đã tạo file `.env`
- [ ] Đã thêm OPENAI_API_KEY hợp lệ
- [ ] Đã thêm GEMINI_API_KEY hợp lệ
- [ ] Các config khác đã điều chỉnh nếu cần

---

### 2. 🚀 Start API Server

#### Option A: Direct Python (Recommended for Testing)
```powershell
# Windows PowerShell
.\scripts\start_api.ps1
```

```bash
# Linux/Mac
chmod +x scripts/start_api.sh
./scripts/start_api.sh
```

**Checklist**:
- [ ] Script chạy không lỗi
- [ ] Agent initialized successfully
- [ ] Server started trên http://localhost:8000
- [ ] Không có error trong console logs

#### Option B: Docker (For Production-like Environment)
```bash
chmod +x scripts/docker_deploy.sh
./scripts/docker_deploy.sh
```

**Checklist**:
- [ ] Docker image build thành công
- [ ] Container started và healthy
- [ ] Health check passes
- [ ] Có thể access API qua port 8000

---

### 3. 🌐 Test API Endpoints via Browser

#### 3.1 Test Root Endpoint
**URL**: http://localhost:8000

**Expected Response**:
```json
{
  "message": "Page-First RAG Agent API",
  "version": "2.0.0",
  "docs": "/docs",
  "health": "/api/v1/health"
}
```

**Checklist**:
- [ ] Root endpoint trả về JSON hợp lệ
- [ ] Version hiển thị đúng (2.0.0)

#### 3.2 Test Health Check
**URL**: http://localhost:8000/api/v1/health

**Expected Response**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "agent_ready": true,
  "components": {
    "agent": "healthy",
    "reranker": "healthy",
    "nli_validator": "healthy"
  },
  "timestamp": 1728...
}
```

**Checklist**:
- [ ] Status là "healthy"
- [ ] agent_ready là true
- [ ] Tất cả components healthy
- [ ] Timestamp hợp lệ

#### 3.3 Test Metrics
**URL**: http://localhost:8000/api/v1/metrics

**Expected Response**:
```json
{
  "requests_total": 0,
  "requests_success": 0,
  "requests_error": 0,
  "avg_latency_ms": 0.0,
  "cache_hit_rate": null,
  "uptime_seconds": 12.5
}
```

**Checklist**:
- [ ] Metrics hiển thị đúng
- [ ] uptime_seconds tăng theo thời gian

---

### 4. 📚 Test Swagger UI

#### 4.1 Open Swagger Documentation
**URL**: http://localhost:8000/docs

**Checklist**:
- [ ] Swagger UI load thành công
- [ ] Thấy 4 endpoints: GET /, POST /ask, GET /health, GET /metrics
- [ ] Mỗi endpoint có description rõ ràng
- [ ] Request/Response schemas được hiển thị

#### 4.2 Test "Try it out" trong Swagger

**Test POST /api/v1/ask**:
1. Click vào endpoint POST /api/v1/ask
2. Click "Try it out"
3. Nhập request body:
```json
{
  "question": "Quy định về áp suất tối đa cho turbine là gì?"
}
```
4. Click "Execute"

**Expected**:
- Status Code: 200
- Response body chứa:
  - `answer`: Câu trả lời tiếng Việt
  - `citations`: Array các citations
  - `language`: "vi"
  - `metrics`: groundedness, coverage, latency
  - `retrieval_info`: bm25_hits, vector_hits, etc.

**Checklist**:
- [ ] Request thành công (200)
- [ ] Answer được generate
- [ ] Citations có confidence scores
- [ ] Language detection đúng ("vi")
- [ ] Metrics hợp lệ (groundedness 0-1, latency > 0)
- [ ] Retrieval info hiển thị đúng số lượng hits

---

### 5. 🧪 Test với Postman/cURL

#### 5.1 Test với cURL (Vietnamese Question)
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quy định về bảo hiểm xã hội là gì?"
  }'
```

**Checklist**:
- [ ] Command chạy thành công
- [ ] Response JSON valid
- [ ] Answer trong tiếng Việt
- [ ] Citations có quote và doc_id
- [ ] Language detected là "vi"

#### 5.2 Test với cURL (English Question)
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the maximum pressure for turbine?"
  }'
```

**Checklist**:
- [ ] Response thành công
- [ ] Answer trong tiếng Anh
- [ ] Language detected là "en"

#### 5.3 Test Error Handling (Empty Question)
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": ""
  }'
```

**Expected**: Status 422 (Validation Error)

**Checklist**:
- [ ] Trả về 422 status code
- [ ] Error message rõ ràng về validation

---

### 6. 📊 Test Performance & Load

#### 6.1 Sequential Requests
Gửi 5 requests liên tiếp và check:

**Checklist**:
- [ ] Tất cả requests thành công
- [ ] Latency request thứ 2-5 thấp hơn request đầu (cache working)
- [ ] Metrics endpoint show:
  - requests_total = 5
  - requests_success = 5
  - avg_latency_ms giảm dần
  - cache_hit_rate > 0

#### 6.2 Monitor Resource Usage
```bash
# Check Docker container stats (nếu dùng Docker)
docker stats page-first-rag-api

# Hoặc check process với Task Manager (Windows)
```

**Checklist**:
- [ ] Memory usage < 4GB
- [ ] CPU usage reasonable
- [ ] No memory leaks sau nhiều requests

---

### 7. 🌍 Test CORS (Nếu có Frontend)

**Nếu bạn có frontend app**, test CORS bằng cách:

```javascript
// Trong browser console
fetch('http://localhost:8000/api/v1/health')
  .then(r => r.json())
  .then(console.log)
```

**Checklist**:
- [ ] No CORS errors trong browser console
- [ ] Response received thành công

---

### 8. 🐛 Test Error Scenarios

#### 8.1 Test khi không có OPENAI_API_KEY
1. Stop API server
2. Remove OPENAI_API_KEY từ .env
3. Start lại server

**Expected**: Server fails to start hoặc LLM calls fail

**Checklist**:
- [ ] Error message rõ ràng về missing API key
- [ ] Service degraded hoặc unhealthy

#### 8.2 Test với Invalid Question
```json
{
  "question": "a"
}
```

**Expected**: Validation error (min_length=3)

**Checklist**:
- [ ] Trả về 422 validation error
- [ ] Error message rõ ràng

---

### 9. 📝 Test Logging

**Checklist**:
- [ ] Logs được ghi vào console/file
- [ ] Log levels phù hợp (INFO, WARNING, ERROR)
- [ ] Sensitive data (API keys) KHÔNG xuất hiện trong logs
- [ ] Request/response được log đầy đủ

---

### 10. 🔒 Security Checks (Production)

**Chỉ cần nếu deploy production**:

**Checklist**:
- [ ] CORS origins được config đúng (không phải *)
- [ ] API keys không xuất hiện trong response
- [ ] Error messages không leak sensitive info
- [ ] Rate limiting working (nếu implement)

---

## 📸 Screenshots Cần Chụp

Để tôi kiểm tra, vui lòng chụp screenshots sau:

1. **Terminal output** khi start API (show Agent initialized)
2. **Browser**: http://localhost:8000/api/v1/health
3. **Swagger UI**: http://localhost:8000/docs
4. **Swagger "Try it out"** cho POST /ask với câu hỏi tiếng Việt
5. **Response** của câu hỏi test với citations
6. **Metrics endpoint**: http://localhost:8000/api/v1/metrics sau vài requests

---

## ✅ Summary Checklist

### Must-Have (Bắt Buộc)
- [ ] API server starts successfully
- [ ] Health check returns healthy
- [ ] POST /ask returns valid answer với citations
- [ ] Swagger UI accessible và functional
- [ ] Language detection works (vi/en)
- [ ] Citations have confidence scores

### Nice-to-Have (Tốt Nếu Có)
- [ ] Docker deployment works
- [ ] Caching improves latency
- [ ] Metrics tracking accurate
- [ ] Error handling robust
- [ ] Logs readable và helpful

---

## 🚨 Nếu Gặp Lỗi

### Common Issues & Solutions

#### 1. "Agent not initialized"
- ✅ Check: Artifacts directory tồn tại
- ✅ Check: API keys hợp lệ trong .env

#### 2. "Module not found"
- ✅ Run: `pip install -r requirements.txt`

#### 3. "Port 8000 already in use"
- ✅ Change API_PORT trong .env
- ✅ Hoặc kill process đang dùng port 8000

#### 4. "Vector search fails"
- ✅ Check GEMINI_API_KEY
- ✅ API vẫn hoạt động với BM25-only mode

#### 5. "LLM call fails"
- ✅ Check OPENAI_API_KEY
- ✅ Check API quota/limits

---

## 📞 Report Results

Sau khi test xong, gửi cho tôi:

1. ✅ **Summary**: Pass/Fail cho từng section
2. 📸 **Screenshots**: 6 screenshots liệt kê ở trên
3. 🐛 **Issues Found**: Danh sách lỗi gặp phải (nếu có)
4. 💡 **Suggestions**: Cải tiến hoặc tính năng bổ sung

---

**Happy Testing! 🧪🚀**

_Tạo bởi: AI Assistant_
_Date: October 9, 2025_
