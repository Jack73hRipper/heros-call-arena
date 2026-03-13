@echo off
title Arena Server — Set Offline
echo Setting server status to offline...

cd /d "%~dp0"

set "GH=C:\Program Files\GitHub CLI\gh.exe"

set TMPDIR=%TEMP%\arena-server-offline-%RANDOM%
mkdir "%TMPDIR%"

:: Write offline server-url.json
powershell -NoProfile -Command "[System.IO.File]::WriteAllText('%TMPDIR%\server-url.json', '{\"url\":\"\",\"status\":\"offline\",\"timestamp\":\"' + (Get-Date -Format o) + '\"}', (New-Object System.Text.UTF8Encoding $false))"

:: Preserve latest.json
"%GH%" api repos/Jack73hRipper/heros-call-arena/contents/latest.json?ref=gh-pages --jq ".content" 2>nul | powershell -NoProfile -Command "$b64 = [Console]::In.ReadToEnd().Trim(); if($b64){ [System.IO.File]::WriteAllBytes('%TMPDIR%\latest.json', [Convert]::FromBase64String($b64)) }"

pushd "%TMPDIR%"
git init >nul 2>&1
git checkout -b gh-pages >nul 2>&1
git add -A >nul 2>&1
git commit -m "Update server-url.json — offline" >nul 2>&1
git remote add origin https://github.com/Jack73hRipper/heros-call-arena.git >nul 2>&1
git push --force origin gh-pages >nul 2>&1
popd

rmdir /s /q "%TMPDIR%" >nul 2>&1

echo [OK] Server status set to OFFLINE.
echo Players will use local fallback on next connect.
pause
