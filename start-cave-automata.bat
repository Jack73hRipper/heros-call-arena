@echo off
echo ============================================
echo   Cave Automata Lab - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd cave-automata
call npm run dev
pause
