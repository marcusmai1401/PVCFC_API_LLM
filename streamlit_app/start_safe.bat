@echo off
echo ========================================
echo  RAG Pipeline Demo - Safe Start
echo ========================================
echo.

echo Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.8+
    pause
    exit /b 1
)

echo.
echo Starting Streamlit in safe mode...
echo.
echo Using stable version to avoid crashes
echo Navigate to: http://localhost:8501
echo Press Ctrl+C to stop
echo ========================================
echo.

REM Use the stable version by default
streamlit run app_stable.py --server.maxUploadSize 200 --server.maxMessageSize 200

if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo If Streamlit is not installed, run:
    echo   pip install -r requirements.txt
    echo ========================================
    pause
)
