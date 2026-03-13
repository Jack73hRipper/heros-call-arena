@echo off
REM ============================================================
REM  bump-version.bat — Bump the game version number
REM
REM  Usage:  scripts\bump-version.bat patch    (0.1.0 -> 0.1.1)
REM          scripts\bump-version.bat minor    (0.1.0 -> 0.2.0)
REM          scripts\bump-version.bat major    (0.1.0 -> 1.0.0)
REM
REM  Updates: client/package.json
REM  Run from repo root.
REM ============================================================

setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

REM ── Validate argument ───────────────────────────────────────
set "BUMP_TYPE=%~1"
if "%BUMP_TYPE%"=="" (
    echo Usage: scripts\bump-version.bat ^<patch^|minor^|major^>
    echo.
    echo   patch  — 0.1.0 -^> 0.1.1
    echo   minor  — 0.1.0 -^> 0.2.0
    echo   major  — 0.1.0 -^> 1.0.0
    exit /b 1
)

if not "%BUMP_TYPE%"=="patch" if not "%BUMP_TYPE%"=="minor" if not "%BUMP_TYPE%"=="major" (
    echo [ERROR] Invalid bump type: %BUMP_TYPE%
    echo         Use: patch ^| minor ^| major
    exit /b 1
)

REM ── Read current version ────────────────────────────────────
for /f "tokens=2 delims=:, " %%a in ('findstr /C:"\"version\"" client\package.json') do (
    set "OLD_VERSION=%%~a"
    goto :got_version
)
:got_version

echo [INFO] Current version: %OLD_VERSION%

REM ── Parse semver components ─────────────────────────────────
for /f "tokens=1-3 delims=." %%a in ("%OLD_VERSION%") do (
    set "MAJOR=%%a"
    set "MINOR=%%b"
    set "PATCH=%%c"
)

REM ── Calculate new version ───────────────────────────────────
if "%BUMP_TYPE%"=="patch" (
    set /a "PATCH+=1"
)
if "%BUMP_TYPE%"=="minor" (
    set /a "MINOR+=1"
    set "PATCH=0"
)
if "%BUMP_TYPE%"=="major" (
    set /a "MAJOR+=1"
    set "MINOR=0"
    set "PATCH=0"
)

set "NEW_VERSION=%MAJOR%.%MINOR%.%PATCH%"
echo [INFO] New version:     %NEW_VERSION%  (%BUMP_TYPE% bump)
echo.

REM ── Update client/package.json ──────────────────────────────
powershell -NoProfile -Command ^
  "$content = Get-Content 'client\package.json' -Raw; " ^
  "$updated = $content -replace '\"version\":\s*\"%OLD_VERSION%\"', '\"version\": \"%NEW_VERSION%\"'; " ^
  "$utf8 = New-Object System.Text.UTF8Encoding($false); " ^
  "[System.IO.File]::WriteAllText((Resolve-Path 'client\package.json').Path, $updated, $utf8)"

if errorlevel 1 (
    echo [ERROR] Failed to update client\package.json
    exit /b 1
)

echo [OK] Updated client\package.json: %OLD_VERSION% -^> %NEW_VERSION%
echo.

REM ── Clean up old patch notes for new version ────────────────
if exist "build\patch-notes.md" (
    del "build\patch-notes.md"
    echo [INFO] Cleared old patch notes. Run scripts\write-patch-notes.bat to write new ones.
)

echo.
echo ============================================================
echo   Version bumped: %OLD_VERSION% -^> %NEW_VERSION%
echo ============================================================
echo.
echo   Next steps:
echo     1. scripts\write-patch-notes.bat     (write release notes)
echo     2. scripts\publish-update.bat        (build + publish)
echo.

endlocal
