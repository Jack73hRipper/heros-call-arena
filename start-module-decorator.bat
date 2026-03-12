@echo off
echo ============================================
echo   Module Sprite Decorator - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd module-decorator
call npm run dev
pause
