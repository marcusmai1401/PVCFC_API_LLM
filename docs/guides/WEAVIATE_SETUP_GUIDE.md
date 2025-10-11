# 🚀 Weaviate Setup Guide - Windows

## ⚠️ **Docker chưa được cài đặt**

Bạn có **2 phương án**:

---

## 📦 **PHƯƠNG ÁN 1: Cài Docker Desktop (Khuyến nghị)**

### **Bước 1: Download Docker Desktop**

1. Truy cập: https://www.docker.com/products/docker-desktop/
2. Download **Docker Desktop for Windows**
3. Chạy installer

### **Bước 2: Cài đặt**

```
1. Chạy Docker Desktop Installer.exe
2. Chọn "Use WSL 2 instead of Hyper-V" (recommended)
3. Hoàn tất cài đặt
4. Restart máy nếu cần
```

### **Bước 3: Verify Docker**

```powershell
# Mở PowerShell mới
docker --version
docker compose version

# Should show:
# Docker version 24.x.x
# Docker Compose version v2.x.x
```

### **Bước 4: Start Weaviate**

```powershell
# Trong thư mục project
docker compose -f docker-compose-weaviate.yml up -d

# Check status
docker compose -f docker-compose-weaviate.yml ps

# Check logs
docker compose -f docker-compose-weaviate.yml logs weaviate

# Verify Weaviate ready
curl http://localhost:8080/v1/.well-known/ready
# Should return: {"Ready":true}
```

**Ưu điểm:**
- ✅ Dễ quản lý (GUI)
- ✅ Data persistent qua container restart
- ✅ Production-ready

**Nhược điểm:**
- ⏱️ Cần 5-10 phút để cài đặt
- 💾 Tốn ~2GB disk space

---

## 🐍 **PHƯƠNG ÁN 2: Weaviate Embedded (Python-only, nhanh)**

Nếu bạn muốn test nhanh mà không cài Docker:

### **Bước 1: Install Weaviate Embedded**

```powershell
pip install weaviate-client[embedded]
```

### **Bước 2: Sử dụng trong code**

```python
import weaviate
from weaviate.embedded import EmbeddedOptions

# Start embedded Weaviate (auto download ~100MB first time)
client = weaviate.WeaviateClient(
    embedded_options=EmbeddedOptions(
        persistence_data_path="./weaviate_data",
        binary_path="./weaviate_binary",
    )
)

client.connect()

# Use normally
# ...

client.close()
```

**Ưu điểm:**
- ✅ Không cần Docker
- ✅ Setup nhanh (1 lệnh pip)
- ✅ Tốt cho development/testing

**Nhược điểm:**
- ❌ Không production-ready
- ❌ Performance không tối ưu
- ❌ Khó scale sau này

---

## 🎯 **KHUYẾN NGHỊ CỦA TÔI**

### **Ngắn hạn (Test ngay):**
→ Dùng **Phương án 2 (Embedded)** để test concept nhanh

### **Dài hạn (Production):**
→ Cài **Phương án 1 (Docker Desktop)** cho ổn định

---

## 📝 **Script Setup Tự Động**

Tôi đã tạo sẵn 2 scripts:

### **1. Setup với Docker (sau khi cài Docker Desktop)**

```powershell
# File: setup_weaviate_docker.ps1
.\setup_weaviate_docker.ps1
```

### **2. Setup với Embedded (không cần Docker)**

```powershell
# File: setup_weaviate_embedded.py
python setup_weaviate_embedded.py
```

---

## ❓ **Bạn muốn phương án nào?**

**Chọn 1 trong 2:**

### **A. Tôi muốn cài Docker Desktop (Production-ready)** ✅

```powershell
# Bạn cài Docker Desktop theo hướng dẫn trên
# Sau đó chạy:
docker compose -f docker-compose-weaviate.yml up -d
python tools/weaviate_setup.py
python tools/ingest_to_weaviate.py
```

### **B. Tôi muốn test nhanh với Embedded (No Docker)** ⚡

```powershell
# Chạy ngay:
pip install "weaviate-client[embedded]"
python setup_weaviate_embedded.py
python tools/ingest_to_weaviate_embedded.py
```

---

## 🔍 **Kiểm tra Docker đã cài chưa**

```powershell
# Check Docker
Get-Command docker -ErrorAction SilentlyContinue

# Nếu không có output → chưa cài
# Nếu có output → đã cài, chạy:
docker --version
```

---

## ⏭️ **Next Steps**

Sau khi chọn phương án và setup xong:

1. ✅ Verify Weaviate running
2. ✅ Create Chunk collection (schema)
3. ✅ Ingest data với metadata
4. ✅ Test retrieval
5. ✅ Implement BGE reranker

**Timeline:**
- Setup: 5-30 phút (tùy phương án)
- Ingest: 20-30 phút
- Total: ~1 giờ

---

**Bạn muốn dùng phương án nào?** Tôi sẽ tạo script setup tương ứng! 🚀
