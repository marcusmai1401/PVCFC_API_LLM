# Launcher Scripts

Scripts để khởi động các services của PVCFC RAG.

## Scripts

- `start_api.ps1` - Khởi động FastAPI backend server
- `start_ui.ps1` - Khởi động Streamlit UI
- `start_all.ps1` - Khởi động cả API và UI
- `start.ps1` - Main start script
- `quick_restart.ps1` - Restart nhanh services
- `restart_and_test.ps1` - Restart và chạy tests
- `start_and_test_cove.ps1` - Start và test Chain-of-Verification
- `start_server.bat` - Start server (Windows batch)

## Usage

```powershell
# Khởi động API
.\launchers\start_api.ps1

# Khởi động UI
.\launchers\start_ui.ps1

# Khởi động tất cả
.\launchers\start_all.ps1
```
