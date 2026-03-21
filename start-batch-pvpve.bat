@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Batch PVPVE Dungeon Simulator
echo ============================================
echo.
cd /d "%~dp0server"
call ..\.venv\Scripts\activate 2>nul
python -X utf8 batch_pvpve.py %*
echo.
pause
