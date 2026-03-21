@echo off
echo ============================================
echo   PVPVE Analyst - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd pvpve-analyst
echo.
echo Starting API server + Vite dev server...
echo   API:  http://localhost:5242
echo   UI:   http://localhost:5243
echo.
start /B node server.js
call npx vite
pause
