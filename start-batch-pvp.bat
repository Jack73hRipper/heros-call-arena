@echo off
echo ============================================
echo   Batch PvP Simulator
echo ============================================
echo.
cd /d "%~dp0server"
call ..\.venv\Scripts\activate 2>nul
python batch_pvp.py %*
echo.
pause
