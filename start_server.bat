@echo off
echo ============================================================
echo   Starting PVCFC RAG API Server
echo ============================================================
echo.
echo Configuration:
echo   - Port: 8000
echo   - Environment: local
echo   - Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.
python -m app.main
