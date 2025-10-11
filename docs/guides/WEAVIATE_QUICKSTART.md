# ⚡ Weaviate Quick Start

## 🎯 **Chọn 1 trong 2 phương án:**

### **A. Embedded Mode (Test nhanh - KHÔNG CẦN DOCKER)** ⚡

```powershell
# 1. Install
pip install "weaviate-client[embedded]"

# 2. Setup (1 lệnh, ~2 phút)
python setup_weaviate_embedded.py

# 3. Done! ✅
# Weaviate chạy tại: http://localhost:8079
```

**Khi nào dùng:** Development, testing, POC
**Ưu điểm:** Setup instant, không cần Docker
**Nhược điểm:** Không production-ready

---

### **B. Docker Mode (Production)** 🐳

```powershell
# 1. Cài Docker Desktop (nếu chưa có)
# Download: https://www.docker.com/products/docker-desktop/

# 2. Start Weaviate
docker compose -f docker-compose-weaviate.yml up -d

# 3. Create schema
python tools/weaviate_setup_docker.py

# 4. Done! ✅
# Weaviate chạy tại: http://localhost:8080
```

**Khi nào dùng:** Production deployment
**Ưu điểm:** Stable, scalable, production-ready
**Nhược điểm:** Cần cài Docker (~5-10 phút)

---

## 📊 **So sánh:**

| Feature | Embedded | Docker |
|---------|----------|--------|
| Setup time | 2 phút | 10 phút |
| Cần Docker? | ❌ No | ✅ Yes |
| Port | 8079 | 8080 |
| Production? | ❌ No | ✅ Yes |
| Data persistence | ✅ Yes | ✅ Yes |
| Performance | Medium | High |

---

## 🚀 **Khuyến nghị:**

```
Để BẮT ĐẦU NHANH:
→ Dùng Embedded mode (Phương án A)

Sau khi đã test xong & OK:
→ Chuyển sang Docker mode (Phương án B)
```

---

## ✅ **Next Steps sau khi setup:**

1. **Ingest data** (20-30 phút):
   ```powershell
   python tools/ingest_to_weaviate.py
   ```

2. **Test retrieval**:
   ```powershell
   python tools/test_weaviate_retrieval.py \
     --query "What is the 4th stage discharge pressure for K06101?"
   ```

3. **Implement BGE reranker** (theo BUILD_PLAN)

---

**Bạn muốn phương án nào?** 🤔
- **A (Embedded)** → Chạy ngay: `python setup_weaviate_embedded.py`
- **B (Docker)** → Cài Docker trước, rồi chạy `docker compose up`
