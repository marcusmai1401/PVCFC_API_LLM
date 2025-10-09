@echo off
echo ====================================
echo  Starting Page-First RAG System
echo ====================================
echo.

REM Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo Please copy .env.example to .env and add your API keys
    pause
    exit /b 1
)

echo [1/3] Starting API Backend...
start "API Backend" cmd /k "python -m uvicorn app.api.page_first_api:app --host 0.0.0.0 --port 8000 --reload"

echo [2/3] Waiting for API to initialize...
timeout /t 10 /nobreak

echo [3/3] Starting Streamlit UI...
start "Streamlit UI" cmd /k "streamlit run streamlit_app/app.py"

echo.
echo ====================================
echo  System Started Successfully!
echo ====================================
echo.
echo API Backend:  http://localhost:8000
echo Swagger Docs: http://localhost:8000/docs
echo Streamlit UI: http://localhost:8501
echo.
echo Press any key to open browser...
pause > nul

start http://localhost:8501

echo.
echo To stop the system, close the terminal windows.
echo.
pause
