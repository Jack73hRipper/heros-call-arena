@echo off
echo ============================================
echo   Item Forge - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd item-forge
echo.
echo Starting API server + Vite dev server...
echo   API:  http://localhost:5221
echo   UI:   http://localhost:5220
echo.
start /B node server.js
call npx vite
pause
