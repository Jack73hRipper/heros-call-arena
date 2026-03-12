@echo off
title Arena - Full Stack
echo ==========================================
echo    Arena - Starting Both Servers
echo ==========================================
echo.
echo This will open TWO windows:
echo   1. Backend  (FastAPI)  - http://localhost:8000
echo   2. Frontend (Vite)     - http://localhost:5173
echo.
echo After both start, open http://localhost:5173 in your browser.
echo Close both windows to stop the servers.
echo ==========================================
echo.

start "Arena Backend" cmd /k "cd /d "%~dp0server" && pip install -r requirements.txt >nul 2>&1 && echo Starting backend... && python -m uvicorn app.main:app --reload --port 8000"

:: Wait for backend to actually be ready (poll until it responds)
echo Waiting for backend to start on port 8000...
:waitloop
timeout /t 2 /nobreak >nul
curl -s -o nul -w "" http://localhost:8000/docs >nul 2>&1
if errorlevel 1 (
    echo   Still waiting for backend...
    goto waitloop
)
echo Backend is ready!

start "Arena Frontend" cmd /k "cd /d "%~dp0client" && npm install >nul 2>&1 && echo Starting frontend... && npm run dev"

:: Wait for frontend to be ready then open browser
timeout /t 5 /nobreak >nul
start http://localhost:5173

echo.
echo Both servers starting! Browser will open shortly.
echo Close the two server windows to stop everything.
echo.
pause
