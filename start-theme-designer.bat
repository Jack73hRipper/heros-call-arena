@echo off
echo ============================================
echo   Dungeon Theme Designer - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd theme-designer
call npm run dev
pause
