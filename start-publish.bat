@echo off
title Hero's Call Arena — Publish Update
echo ====================================
echo   Hero's Call Arena — Publish Update
echo ====================================
echo.
cd /d "%~dp0"
call scripts\publish-update.bat %*
