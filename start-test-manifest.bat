@echo off
REM Serve test-manifest/ on http://localhost:8088 for launcher dev testing
echo Serving launcher test manifest on http://localhost:8088 ...
echo Press Ctrl+C to stop.
cd /d "%~dp0launcher\test-manifest"
npx -y http-server -p 8088 --cors -c-1
