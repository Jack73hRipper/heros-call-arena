@echo off
echo ============================================
echo  Sprite Sheet Cataloger - Arena MMO Tools
echo ============================================
echo.
cd /d "%~dp0tools"
call npm install
cd sprite-cataloger
call npm run dev
pause
