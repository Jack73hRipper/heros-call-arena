@echo off
echo ============================================
echo   Enemy Forge - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd enemy-forge
echo.
echo Starting API server + Vite dev server...
echo   API:  http://localhost:5231
echo   UI:   http://localhost:5230
echo.
start /B node server.js
call npx vite
pause
