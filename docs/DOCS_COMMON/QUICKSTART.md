# Quick Start Guide - PVCFC RAG System

## Prerequisites
- Python 3.11 installed
- Virtual environment created (venv folder exists)
- `.env` file configured with API keys

## Starting the System

### Method 1: Using PowerShell Scripts (Recommended)

1. **Start the API Server** (Terminal 1)
   ```powershell
   .\start_api.ps1
   ```
   - Server will run on http://localhost:8000
   - Keep this terminal open
   - Press Ctrl+C to stop

2. **Start the UI** (Terminal 2)
   ```powershell
   .\start_ui.ps1
   ```
   - UI will open at http://localhost:8501
   - Will check if API is running first
   - Keep this terminal open
   - Press Ctrl+C to stop

### Method 2: Manual Commands

1. **Start API Server**
   ```bash
   # Load environment
   cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

   # Start server
   .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. **Start Streamlit UI**
   ```bash
   # In a new terminal
   cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

   # Set API URL (optional, defaults to localhost:8000)
   $env:PVCFC_API_BASE_URL = "http://localhost:8000"

   # Start UI
   streamlit run streamlit_app/app.py
   ```

## Testing the System

### 1. Check API Health
Open browser or use curl:
```
http://localhost:8000/healthz
http://localhost:8000/docs (API documentation)
```

### 2. Use Query Lab in UI
1. Open http://localhost:8501
2. Navigate to "Query Lab" in sidebar
3. Enter a test query like:
   - "What is the operating pressure of KT06101?"
   - "Áp suất vận hành của bơm KT06101 là bao nhiêu?"
4. Click "Run Query"

### 3. Quick API Test
```powershell
# Test with curl
curl -X POST http://localhost:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"query": "test question", "max_context": 5, "hyde": false}'
```

## Key Behaviors (Enabled by default)
- Page-Range Expansion: Always on (gộp cụm trang liên tiếp theo doc_id để hiểu đúng ngữ cảnh trước khi trả lời).
- Auto-language: Trả lời theo ngôn ngữ đầu vào (vi/en) tự động.
- Footnote Citations: Trả lời kèm trích dẫn dạng `doc_id; page` ở cuối.

## Common Issues & Solutions

### Issue 1: API won't start
**Error**: `ModuleNotFoundError: No module named 'prometheus_client'`
**Solution**:
```bash
.\venv\Scripts\python.exe -m pip install prometheus-client
```

### Issue 2: UI can't connect to API
**Error**: "Cannot connect to API"
**Solution**:
1. Make sure API is running on port 8000
2. Check Windows Firewall isn't blocking localhost
3. In UI, expand "API Configuration" and verify URL is `http://localhost:8000`

### Issue 3: Port already in use
**Error**: `[Errno 10048] error while attempting to bind on address`
**Solution**:
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

### Issue 4: No search results
**Symptom**: API returns empty results
**Solution**:
1. Check if indices exist in `artifacts/index/`
2. Verify BM25 and FAISS indices are loaded (check API startup logs)
3. Run indexing if needed:
   ```bash
   python tools/ingest.py
   python tools/build_index.py
   ```

## Configuration

### API Configuration (.env file)
Key settings (single production config; tiers/modes removed):
```ini
APP_ENV=local
API_PORT=8000
LLM_PROVIDER=gemini
# Use the same production model for both to maintain compatibility with current code
LLM_MODEL_LIGHT=gemini-2.5-pro
LLM_MODEL_HEAVY=gemini-2.5-pro
GEMINI_API_KEY=your_key_here
```

### UI Configuration
The UI will automatically use `http://localhost:8000` as the API base URL.
You can change it in the UI under "API Configuration" expander.

## Development Tips

1. **API Auto-reload**: The `--reload` flag makes the API restart when code changes
2. **UI Hot-reload**: Streamlit automatically reloads when you save changes
3. **Logs**: Check terminal output for detailed logs
4. **API Docs**: Visit http://localhost:8000/docs for interactive API documentation

## Stopping the System

1. Press `Ctrl+C` in both terminals (API and UI)
2. Or close the terminal windows

## Next Steps

- Test different queries in Query Lab
- Verify page jump (open PDF at correct page) and footnote citations
- Tune retrieval parameters (k_bm25, k_faiss) and observe metrics

## Support

For issues, check:
- API logs in terminal 1
- UI logs in terminal 2
- `docs/` folder for detailed documentation
- `CHANGLOG_README/` for phase reports
