# 🚀 PVCFC RAG Launcher Guide

Hướng dẫn sử dụng các script để khởi động API và UI.

---

## 📋 SCRIPTS CÓ SẴN

### 1. **`start.ps1`** ⭐ **RECOMMENDED**

**Mô tả**: Script đơn giản nhất - mở API và UI trong 2 terminal riêng biệt

**Sử dụng**:
```powershell
.\start.ps1
```

**Ưu điểm**:
- ✅ **Đơn giản nhất** - chỉ 1 lệnh
- ✅ Tự động mở 2 terminal windows
- ✅ Tự động check services đã sẵn sàng chưa
- ✅ Dễ debug - mỗi service có terminal riêng
- ✅ Dễ stop - đóng terminal hoặc Ctrl+C

**Output**:
```
========================================
  PVCFC RAG - Quick Launcher
========================================

[1/2] Starting API server...
      Opening in new terminal window...
[OK] API terminal opened

Waiting 5 seconds for API to initialize...

[2/2] Starting UI...
      Opening in new terminal window...
[OK] UI terminal opened

Checking services...
[OK] API is running at http://localhost:8000
[OK] UI is running at http://localhost:8502

========================================
  Services launched successfully!
========================================

URLs:
  API:      http://localhost:8000
  API Docs: http://localhost:8000/docs
  UI:       http://localhost:8502

Two terminal windows have been opened:
  1. API terminal (port 8000)
  2. UI terminal (port 8502)

To stop services:
  - Press Ctrl+C in each terminal window
  - Or close the terminal windows
```

---

### 2. **`start_all.ps1`** (Advanced)

**Mô tả**: Script nâng cao - chạy cả 2 services trong cùng 1 terminal bằng background jobs

**Sử dụng**:
```powershell
.\start_all.ps1
```

**Ưu điểm**:
- ✅ Chỉ cần 1 terminal
- ✅ Tự động monitor cả 2 services
- ✅ Tự động cleanup khi thoát
- ✅ Hiển thị logs của cả 2 services

**Nhược điểm**:
- ⚠️ Phức tạp hơn
- ⚠️ Output từ 2 services sẽ xen kẽ nhau
- ⚠️ Khó debug hơn

**Khi nào dùng**:
- Khi bạn muốn chạy tất cả trong 1 terminal
- Khi deploy hoặc automation
- Khi bạn muốn log tất cả vào 1 chỗ

---

### 3. **`start_api.ps1`** (Manual)

**Mô tả**: Chỉ start API server

**Sử dụng**:
```powershell
.\start_api.ps1
```

**Khi nào dùng**:
- Khi bạn chỉ cần test API
- Khi bạn đang develop backend
- Khi UI không cần thiết

---

### 4. **`start_ui.ps1`** (Manual)

**Mô tả**: Chỉ start UI (yêu cầu API đã chạy)

**Sử dụng**:
```powershell
.\start_ui.ps1
```

**Khi nào dùng**:
- Khi API đã chạy từ trước
- Khi bạn đang develop frontend
- Khi restart UI mà không muốn restart API

---

## 🎯 SO SÁNH SCRIPTS

| Feature | `start.ps1` | `start_all.ps1` | Manual (API + UI) |
|---------|-------------|-----------------|-------------------|
| **Số lệnh cần chạy** | 1 | 1 | 2 |
| **Số terminal** | 3 (launcher + 2 services) | 1 | 2 |
| **Dễ debug** | ✅ Cao | ⚠️ Trung bình | ✅ Cao |
| **Tự động cleanup** | ⚠️ Manual | ✅ Tự động | ⚠️ Manual |
| **Logs riêng biệt** | ✅ Có | ❌ Không | ✅ Có |
| **Monitoring** | ⚠️ Cơ bản | ✅ Tự động | ❌ Không |
| **Độ phức tạp** | ⭐ Đơn giản | ⭐⭐⭐ Phức tạp | ⭐⭐ Trung bình |

---

## 💡 KHUYẾN NGHỊ SỬ DỤNG

### Cho Development (hàng ngày)
```powershell
# Option 1: Đơn giản nhất (RECOMMENDED)
.\start.ps1

# Option 2: Manual control
.\start_api.ps1    # Terminal 1
.\start_ui.ps1     # Terminal 2
```

### Cho Testing
```powershell
# Full stack testing
.\start.ps1

# API only
.\start_api.ps1

# UI only (after API is running)
.\start_ui.ps1
```

### Cho Production/Demo
```powershell
# All-in-one monitoring
.\start_all.ps1
```

---

## 🔧 TROUBLESHOOTING

### Vấn đề: API không start được

**Kiểm tra**:
```powershell
# Check venv exists
Test-Path .\venv\Scripts\python.exe

# Check port 8000 có đang dùng không
netstat -ano | findstr :8000

# Kill process nếu cần
Stop-Process -Id <PID> -Force
```

### Vấn đề: UI không connect được API

**Kiểm tra**:
```powershell
# Test API health
Invoke-WebRequest http://localhost:8000/healthz

# Check API logs trong terminal
# Xem có error không
```

### Vấn đề: Port đã được sử dụng

**Solution**:
```powershell
# Kill process trên port 8000 (API)
$process = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $process.OwningProcess -Force
}

# Kill process trên port 8502 (UI)
$process = Get-NetTCPConnection -LocalPort 8502 -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $process.OwningProcess -Force
}
```

### Vấn đề: Services không stop được

**Solution**:
```powershell
# Force kill all Python processes (careful!)
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Force kill all Streamlit processes
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## 📚 WORKFLOW EXAMPLES

### Workflow 1: Bắt đầu ngày làm việc
```powershell
# Mở project folder
cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC

# Start everything
.\start.ps1

# Browser tự động mở http://localhost:8502
# Bắt đầu dev/test
```

### Workflow 2: Development với hot-reload
```powershell
# Terminal 1: API với --reload
.\start_api.ps1

# Terminal 2: UI (restart khi cần)
.\start_ui.ps1

# Edit code → API tự reload
# Edit UI → Ctrl+C terminal 2 và chạy lại start_ui.ps1
```

### Workflow 3: Quick test
```powershell
# Start all
.\start.ps1

# Test feature
# ...

# Stop: Close 2 terminal windows hoặc Ctrl+C
```

---

## 🎨 CUSTOMIZATION

### Thay đổi ports

**Edit** `start_api.ps1`:
```powershell
# Line 36: Change port
--port 8000  →  --port 9000
```

**Edit** `start_ui.ps1`:
```powershell
# Line 10-11: Update API URL
[Environment]::SetEnvironmentVariable("API_BASE_URL", "http://localhost:9000", "Process")

# Line 40: Change UI port
--server.port 8502  →  --server.port 9502
```

### Thêm arguments

**Ví dụ**: Disable auto-reload cho API
```powershell
# In start_api.ps1, line 36
& ".\venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Remove --reload flag
```

---

## 📖 QUICK REFERENCE

```powershell
# 🚀 Quick start (recommended)
.\start.ps1

# 🔧 Advanced (all-in-one)
.\start_all.ps1

# 🎯 API only
.\start_api.ps1

# 🖼️ UI only
.\start_ui.ps1

# 🛑 Stop everything
# → Close terminal windows or Ctrl+C

# 🔍 Check services
Invoke-WebRequest http://localhost:8000/healthz   # API
Invoke-WebRequest http://localhost:8502           # UI

# 📊 View logs
# → Check terminal windows
```

---

## ✨ TIPS & TRICKS

1. **Tạo shortcut**: Right-click `start.ps1` → Send to → Desktop (create shortcut)

2. **Pin to taskbar**: Create a `.bat` file:
   ```batch
   @echo off
   cd C:\Users\Admin\Desktop\Code - API_LLM_PVCFC
   powershell -ExecutionPolicy Bypass -File .\start.ps1
   pause
   ```

3. **Add to Windows Terminal**: Edit Windows Terminal settings:
   ```json
   {
       "name": "PVCFC RAG",
       "commandline": "powershell -NoExit -Command \"cd C:\\Users\\Admin\\Desktop\\Code - API_LLM_PVCFC; .\\start.ps1\"",
       "icon": "🚀"
   }
   ```

4. **Auto-start on login**: Add to Windows Startup folder:
   - Press `Win+R`, type `shell:startup`
   - Create shortcut to `start.ps1`

---

**Last updated**: 2025-10-01
**Scripts version**: 1.0
**Recommended**: Use `start.ps1` for daily development
