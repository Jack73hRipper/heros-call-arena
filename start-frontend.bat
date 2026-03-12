@echo off
title Arena Frontend Server
echo ==========================================
echo    Arena Frontend Server (Vite + React)
echo ==========================================
echo.

cd /d "%~dp0client"

echo Installing dependencies (first time may take a moment)...
call npm install >nul 2>&1

echo.
echo Starting frontend on http://localhost:5173 ...
echo Press Ctrl+C to stop.
echo.

call npm run dev

pause
