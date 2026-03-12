@echo off
echo ============================================
echo   Audio Workbench - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd audio-workbench
echo.
echo Starting API server + Vite dev server...
echo   API:  http://localhost:5211
echo   UI:   http://localhost:5210
echo.
start /B node server.js
call npx vite
pause
