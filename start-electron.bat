@echo off
title Hero's Call - Electron Desktop App
echo ==========================================
echo    Hero's Call Arena - Desktop Mode
echo ==========================================
echo.
echo This will open THREE windows:
echo   1. Backend  (FastAPI)    - http://localhost:8000
echo   2. Frontend (Vite Dev)   - http://localhost:5173
echo   3. Desktop  (Electron)   - Native Window
echo.
echo The Electron window will open automatically once Vite is ready.
echo Close all windows to stop everything.
echo ==========================================
echo.

:: Start the Python backend
start "Arena Backend" cmd /k "cd /d "%~dp0server" && pip install -r requirements.txt >nul 2>&1 && echo [Backend] Starting FastAPI on port 8000... && python -m uvicorn app.main:app --reload --port 8000"

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

:: Start Vite + Electron together using concurrently
start "Arena Electron" cmd /k "cd /d "%~dp0client" && npm install >nul 2>&1 && echo [Electron] Starting Vite + Electron... && npm run electron:dev"

echo.
echo All services starting! The desktop window will appear shortly.
echo.
pause
