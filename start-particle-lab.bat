@echo off
echo ============================================
echo   Particle Effects Lab - Arena MMO Project
echo ============================================
cd /d "%~dp0tools"
call npm install
cd particle-lab
call npm run dev
pause
