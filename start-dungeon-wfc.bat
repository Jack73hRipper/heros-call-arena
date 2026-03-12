@echo off
echo ============================================
echo   WFC Dungeon Lab - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd dungeon-wfc
call npm run dev
pause
