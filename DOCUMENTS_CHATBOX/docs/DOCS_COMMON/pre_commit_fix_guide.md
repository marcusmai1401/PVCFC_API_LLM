# Pre-commit Fix Guide

## Vấn đề đã khắc phục
1. **Bandit lỗi `pbr`**: Thêm `additional_dependencies: ['pbr']`
2. **Pytest lỗi môi trường**: Chuyển sang `language: system` và chỉ chạy khi push

## Các bước để chạy lại pre-commit

### 1. Kích hoạt ExecutionPolicy (một lần duy nhất)
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 2. Kích hoạt virtual environment
```powershell
# Cách 1: PowerShell
.\venv\Scripts\Activate.ps1

# Cách 2: CMD (nếu PowerShell không được)
venv\Scripts\activate.bat
```

### 3. Clean và reinstall pre-commit hooks
```powershell
pre-commit clean
pre-commit install
pre-commit install --hook-type pre-push
```

### 4. Add các file đã được sửa và chạy lại
```powershell
git add -A
pre-commit run --all-files
```

### 5. Nếu tất cả PASS, commit và push
```powershell
git commit -m "chore: format code and fix pre-commit hooks"
git push origin main
```

## Giải thích thay đổi

### Bandit fix
- **Trước**: Hook bandit thiếu dependency `pbr`
- **Sau**: Thêm `additional_dependencies: ['pbr']` để pre-commit tự cài pbr

### Pytest fix
- **Trước**: `language: python` - chạy trong env riêng của pre-commit (không có pytest)
- **Sau**: `language: system` + `stages: [push]` - dùng pytest từ venv của bạn, chỉ chạy khi push

## Workflow hàng ngày

### Commit thường (nhanh)
```powershell
git add -A
git commit -m "your message"  # Chỉ chạy format hooks (black, isort, etc.)
```

### Push (có test)
```powershell
git push origin main  # Chạy thêm pytest
```

## Troubleshooting

### Nếu bandit vẫn lỗi
```powershell
pre-commit clean
pre-commit run bandit --all-files
```

### Nếu pytest không tìm thấy
```powershell
# Đảm bảo pytest có trong venv
pip install pytest pytest-asyncio

# Hoặc check PATH
which pytest  # Linux/Mac
where pytest  # Windows
```

### Skip hook tạm thời (không khuyến nghị)
```powershell
git commit -m "message" --no-verify
git push origin main --no-verify
```

## Kết quả mong đợi

Khi chạy thành công, bạn sẽ thấy:
```
Trim Trailing Whitespace.................................................Passed
Fix End of Files.........................................................Passed
Check YAML...............................................................Passed
Check for merge conflicts................................................Passed
Check for large files....................................................Passed
Detect Private Keys......................................................Passed
Check for case conflicts.................................................Passed
Format with Black........................................................Passed
Sort imports with isort..................................................Passed
Security check with Bandit...............................................Passed
```

Pytest chỉ chạy khi push:
```
Run tests................................................................Passed
```
