@echo off
title Hero's Call Arena — Launcher (Dev)
echo ====================================
echo   Hero's Call Arena — Launcher
echo ====================================
echo.

cd /d "%~dp0launcher"

if not exist node_modules (
    echo Installing dependencies...
    call npm install
    echo.
)

echo Starting launcher...
call npx electron .
