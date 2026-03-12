@echo off
echo ============================================
echo   Arena Analyst - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd arena-analyst
echo.
echo Starting API server + Vite dev server...
echo   API:  http://localhost:5241
echo   UI:   http://localhost:5240
echo.
start /B node server.js
call npx vite
pause
