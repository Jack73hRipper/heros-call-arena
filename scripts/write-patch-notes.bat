@echo off
REM ============================================================
REM  write-patch-notes.bat — Create/edit patch notes for a release
REM
REM  Opens a patch notes template at build/patch-notes.md
REM  The publish-update.bat script reads this file and embeds
REM  the contents into latest.json for the launcher to display.
REM
REM  Run from repo root: scripts\write-patch-notes.bat
REM ============================================================

setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

REM ── Read version from client/package.json ───────────────────
for /f "tokens=2 delims=:, " %%a in ('findstr /C:"\"version\"" client\package.json') do (
    set "VERSION=%%~a"
    goto :got_version
)
:got_version

if not exist "build" mkdir "build"

set "PATCH_FILE=build\patch-notes.md"

REM If patch notes already exist, don't overwrite — just open
if exist "%PATCH_FILE%" (
    echo [INFO] Existing patch notes found at %PATCH_FILE%
    echo        Opening for editing...
    echo.
    goto :open_editor
)

REM ── Generate template ───────────────────────────────────────
echo [INFO] Creating patch notes template for v%VERSION%...

(
    echo ### v%VERSION%
    echo.
    echo **New Features**
    echo - 
    echo.
    echo **Bug Fixes**
    echo - 
    echo.
    echo **Balance Changes**
    echo - 
    echo.
    echo **Known Issues**
    echo - 
) > "%PATCH_FILE%"

echo [OK] Template created at %PATCH_FILE%
echo.

:open_editor
REM Try to open in VS Code, fall back to notepad
where code >nul 2>&1
if not errorlevel 1 (
    code "%PATCH_FILE%"
    echo [INFO] Opened in VS Code. Save and close when done.
) else (
    notepad "%PATCH_FILE%"
    echo [INFO] Opened in Notepad. Save and close when done.
)

echo.
echo [TIP] After editing, run: scripts\publish-update.bat
echo       The patch notes will be embedded in latest.json automatically.
echo.

endlocal
