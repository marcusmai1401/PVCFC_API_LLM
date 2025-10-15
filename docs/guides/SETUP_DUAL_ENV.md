# Hướng dẫn Setup - Hai Môi trường (Dual Environment)

## Tại sao cần 2 môi trường?

- **PaddleOCR** cần protobuf 3.20.x
- **Weaviate** cần protobuf 4.x
- Không thể cài cả hai trong cùng 1 môi trường

## Kiến trúc

```
.venv (hoặc venv)               → Môi trường CHÍNH
├─ Weaviate ✅                  → Cho API server, queries, toàn bộ hệ thống
├─ FastAPI ✅
├─ OpenSearch ✅
├─ LLM clients ✅
└─ PaddleOCR ❌                 → BỎ để tránh conflict

venv_ingest                     → Môi trường PHỤ (chỉ dùng khi cần OCR)
├─ PaddleOCR ✅                 → Đọc PDF
├─ OpenSearch ✅                → Đưa data vào index
└─ Weaviate ❌                  → Không cần
```

## Setup lần đầu (1 lần duy nhất)

### Bước 1: Tạo môi trường CHÍNH (cho API server)

```powershell
# Tạo virtual environment
python -m venv .venv

# Activate
.\.venv\Scripts\Activate.ps1

# Cài dependencies (KHÔNG có PaddleOCR)
pip install --upgrade pip
pip install -r requirements_main.txt

# Deactivate
deactivate
```

### Bước 2: Tạo môi trường PHỤ (cho ingestion)

```powershell
# Tạo virtual environment
python -m venv venv_ingest

# Activate
.\venv_ingest\Scripts\Activate.ps1

# Cài dependencies (CÓ PaddleOCR)
pip install --upgrade pip
pip install -r requirements_ingest.txt

# Deactivate
deactivate
```

### Bước 3: Xong! 🎉

## Sử dụng hàng ngày

### Chạy API server (99% thời gian)

```powershell
# Script tự động dùng .venv
.\launchers\start_api.ps1
```

Hoặc activate thủ công:
```powershell
.\.venv\Scripts\Activate.ps1
# Làm việc bình thường...
```

### Nạp PDF mới (1% thời gian)

**Cách 1: Dùng script tự động (KHUYÊN DÙNG)**

```powershell
.\scripts\ingest_pdf.ps1 -PdfPath "C:\path\to\document.pdf" -IndexName "pvcfc_docs"
```

Script này tự động:
1. Chuyển sang `venv_ingest`
2. Update mapping OpenSearch
3. Ingest PDF với PaddleOCR
4. Verify tags
5. Quay lại môi trường ban đầu

**Cách 2: Thủ công**

```powershell
# Nếu API đang chạy, tắt nó (Ctrl+C)
deactivate  # Thoát .venv

# Chuyển sang venv_ingest
.\venv_ingest\Scripts\Activate.ps1

# Nạp PDF
python tools\ingest_single_pdf.py --pdf "C:\path\to\file.pdf" --index pvcfc_docs

# Quay lại môi trường chính
deactivate
.\.venv\Scripts\Activate.ps1

# Khởi động lại API
.\launchers\start_api.ps1
```

## Kiểm tra

### Xem đang ở môi trường nào?

```powershell
# Xem Python path
which python
# hoặc
Get-Command python | Select-Object Source

# Xem phiên bản protobuf
pip show protobuf
```

Kết quả mong đợi:
- **Trong `.venv`**: protobuf 4.x, có weaviate-client
- **Trong `venv_ingest`**: protobuf 3.20.3, có paddleocr

## Troubleshooting

### PowerShell báo lỗi không thể chạy script

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### Quên deactivate môi trường cũ

```powershell
deactivate  # Luôn chạy trước khi activate môi trường khác
```

### Muốn rebuild môi trường

```powershell
# Xóa và tạo lại
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements_main.txt
deactivate
```

## Tóm tắt nhanh

| Cần làm gì? | Môi trường | Lệnh |
|-------------|-----------|------|
| Chạy API server | `.venv` | `.\launchers\start_api.ps1` |
| Nạp PDF mới | `venv_ingest` | `.\scripts\ingest_pdf.ps1 -PdfPath "..."` |
| Code/test thông thường | `.venv` | `.\.venv\Scripts\Activate.ps1` |
| Ra khỏi môi trường | - | `deactivate` |

## Files liên quan

- `requirements_main.txt` - Dependencies cho môi trường chính (KHÔNG có PaddleOCR)
- `requirements_ingest.txt` - Dependencies cho môi trường ingestion (CÓ PaddleOCR)
- `scripts/ingest_pdf.ps1` - Script tự động nạp PDF
- `launchers/start_api.ps1` - Script khởi động API server
