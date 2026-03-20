@echo off
echo ============================================
echo   Batch PVPVE Dungeon Simulator
echo ============================================
echo.
cd /d "%~dp0server"
call ..\.venv\Scripts\activate 2>nul
python batch_pvpve.py %*
echo.
pause
