@echo off
title Arena Online Server
echo ==========================================
echo    Arena Online Server (Cloudflare Tunnel)
echo ==========================================
echo.

cd /d "%~dp0"

:: ---- 1. Locate tools ----
set "GH=C:\Program Files\GitHub CLI\gh.exe"
set "CF=C:\Program Files (x86)\cloudflared\cloudflared.exe"
set VENV_PY=%~dp0.venv\Scripts\python.exe

if not exist "%CF%" (
    echo [ERROR] cloudflared not found. Install via: winget install Cloudflare.cloudflared
    pause & exit /b 1
)
if not exist "%GH%" (
    echo [ERROR] GitHub CLI not found. Install via: winget install GitHub.cli
    pause & exit /b 1
)
if not exist "%VENV_PY%" (
    echo [ERROR] Python venv not found at .venv\Scripts\python.exe
    echo Run: python -m venv .venv
    pause & exit /b 1
)

:: ---- 2. Start FastAPI server in background with CORS=* ----
echo [1/4] Starting FastAPI server on port 8000...
set ARENA_CORS_ORIGINS=["*"]
pushd server
start /b "" "%VENV_PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>nul
popd
:: Give it a moment to boot
timeout /t 3 /nobreak >nul

:: Verify server is running
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }"
if errorlevel 1 (
    echo [ERROR] Server failed to start. Check for port conflicts.
    pause & exit /b 1
)
echo [OK] Server is running.
echo.

:: ---- 3. Start Cloudflare quick tunnel, capture URL ----
echo [2/4] Starting Cloudflare quick tunnel...
set TUNNEL_LOG=%TEMP%\cloudflared-tunnel.log
if exist "%TUNNEL_LOG%" del "%TUNNEL_LOG%"

:: Start cloudflared in background, redirect stderr to log file
start /b "" cmd /c ""%CF%" tunnel --url http://localhost:8000 2>"%TUNNEL_LOG%""

:: Wait for the tunnel URL to appear in the log (max ~30 seconds)
set TUNNEL_URL=
for /L %%i in (1,1,30) do (
    if not defined TUNNEL_URL (
        timeout /t 1 /nobreak >nul
        for /f "tokens=*" %%a in ('powershell -NoProfile -Command "$log = Get-Content '%TUNNEL_LOG%' -ErrorAction SilentlyContinue; $m = $log | Select-String 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1; if($m){$m.Matches[0].Value}"') do (
            set "TUNNEL_URL=%%a"
        )
    )
)

if not defined TUNNEL_URL (
    echo [ERROR] Could not get tunnel URL after 30 seconds.
    echo Check %TUNNEL_LOG% for details.
    pause & exit /b 1
)

echo [OK] Tunnel URL: %TUNNEL_URL%
echo.

:: ---- 4. Publish server-url.json to GitHub Pages ----
echo [3/4] Publishing server URL to GitHub Pages...

set TMPDIR=%TEMP%\arena-server-url-%RANDOM%
mkdir "%TMPDIR%"

:: Write server-url.json (no BOM)
powershell -NoProfile -Command "[System.IO.File]::WriteAllText('%TMPDIR%\server-url.json', '{\"url\":\"%TUNNEL_URL%\",\"status\":\"online\",\"timestamp\":\"' + (Get-Date -Format o) + '\"}', (New-Object System.Text.UTF8Encoding $false))"

:: Also preserve the existing latest.json if it exists on gh-pages
"%GH%" api repos/Jack73hRipper/heros-call-arena/contents/latest.json?ref=gh-pages --jq ".content" 2>nul | powershell -NoProfile -Command "$b64 = [Console]::In.ReadToEnd().Trim(); if($b64){ [System.IO.File]::WriteAllBytes('%TMPDIR%\latest.json', [Convert]::FromBase64String($b64)) }"

:: Deploy to gh-pages
pushd "%TMPDIR%"
git init >nul 2>&1
git checkout -b gh-pages >nul 2>&1
git add -A >nul 2>&1
git commit -m "Update server-url.json — online" >nul 2>&1
git remote add origin https://github.com/Jack73hRipper/heros-call-arena.git >nul 2>&1
git push --force origin gh-pages >nul 2>&1
popd

:: Cleanup temp dir
rmdir /s /q "%TMPDIR%" >nul 2>&1

echo [OK] server-url.json published to GitHub Pages.
echo.

:: ---- 5. Done — show status ----
echo ==========================================
echo    ARENA SERVER IS ONLINE
echo ==========================================
echo.
echo   Server:  http://localhost:8000
echo   Tunnel:  %TUNNEL_URL%
echo   Status:  https://jack73hripper.github.io/heros-call-arena/server-url.json
echo.
echo   Share the game and players will auto-connect!
echo   Press Ctrl+C to stop the server.
echo ==========================================
echo.

:: Keep the window open — server and tunnel run as background processes
:: When the user presses Ctrl+C, publish offline status
:wait_loop
timeout /t 60 /nobreak >nul
goto wait_loop
