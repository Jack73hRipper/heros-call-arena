@echo off
title Arena Backend Server
echo ==========================================
echo    Arena Backend Server (FastAPI)
echo ==========================================
echo.

cd /d "%~dp0server"

echo Installing dependencies (first time may take a moment)...
pip install -r requirements.txt >nul 2>&1

echo.
echo Starting backend on http://localhost:8000 ...
echo Press Ctrl+C to stop.
echo.

python -m uvicorn app.main:app --reload --port 8000

pause
