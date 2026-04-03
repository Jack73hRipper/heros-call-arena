@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   PVPVE Agent Mode - Copilot Plays
echo ============================================
echo.
echo Copilot will control Team A's leader.
echo State is written to server\agent_turn\state.json each turn.
echo Write your action to server\agent_turn\action.json.
echo.
cd /d "%~dp0server"
call ..\.venv\Scripts\activate 2>nul
python -X utf8 batch_pvpve_agent.py %*
pause
