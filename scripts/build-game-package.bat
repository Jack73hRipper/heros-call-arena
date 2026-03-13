@echo off
REM ============================================================
REM  build-game-package.bat — Build Hero's Call Arena for distribution
REM
REM  Steps:
REM    1. PyInstaller bundles the Python server → arena-server.exe
REM    2. Vite builds the frontend → client/dist/
REM    3. electron-builder packages the Electron app (unpackaged)
REM    4. Copies PyInstaller output into the Electron build
REM    5. Zips the result → build/arena-v{VERSION}.zip
REM
REM  Run from the repo root: scripts\build-game-package.bat
REM ============================================================

setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

echo.
echo ============================================================
echo   Hero's Call Arena — Game Package Builder
echo ============================================================
echo.

REM ── Read version from client/package.json ───────────────────
for /f "tokens=2 delims=:, " %%a in ('findstr /C:"\"version\"" client\package.json') do (
    set "VERSION=%%~a"
    goto :got_version
)
:got_version
echo [INFO] Building version: %VERSION%
echo.

REM ── Step 1: PyInstaller — Bundle Python Server ──────────────
echo [1/5] Building Python server with PyInstaller...
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\
    echo         Create it with: python -m venv .venv
    echo         Then install deps: pip install -r server\requirements.txt pyinstaller
    exit /b 1
)

call .venv\Scripts\activate.bat

REM Check PyInstaller is installed
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not found. Install it with: pip install pyinstaller
    exit /b 1
)

cd server
pyinstaller --noconfirm --clean "..\scripts\arena-server.spec"
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    cd ..
    exit /b 1
)
cd ..

REM Move PyInstaller output to build directory
if not exist "build\pyinstaller" mkdir "build\pyinstaller"
if exist "build\pyinstaller\arena-server" rmdir /s /q "build\pyinstaller\arena-server"
move "server\dist\arena-server" "build\pyinstaller\arena-server"

REM Clean up PyInstaller temp files
if exist "server\dist" rmdir /s /q "server\dist"
if exist "server\build" rmdir /s /q "server\build"

echo [OK] Server bundled successfully.
echo.

REM ── Step 2: Vite — Build Frontend ──────────────────────────
echo [2/5] Building frontend with Vite (Electron mode)...
echo.

cd client
set ELECTRON_BUILD=true
call npm run build
if errorlevel 1 (
    echo [ERROR] Vite build failed!
    cd ..
    exit /b 1
)
cd ..

echo [OK] Frontend built successfully.
echo.

REM ── Step 3: electron-builder — Package Electron App ────────
echo [3/5] Packaging Electron app (unpackaged)...
echo.

cd client
call npx electron-builder --dir --win
if errorlevel 1 (
    echo [ERROR] electron-builder failed!
    cd ..
    exit /b 1
)
cd ..

echo [OK] Electron app packaged successfully.
echo.

REM ── Step 4: Verify the build ────────────────────────────────
echo [4/5] Verifying build output...
echo.

set "BUILD_DIR=build\electron\win-unpacked"
if not exist "%BUILD_DIR%\Hero's Call Arena.exe" (
    echo [ERROR] Game executable not found at %BUILD_DIR%\Hero's Call Arena.exe
    echo         Check electron-builder output above.
    exit /b 1
)

if not exist "%BUILD_DIR%\resources\arena-server\arena-server.exe" (
    echo [WARNING] arena-server.exe not found in resources — it may be in a different location
    echo          Checking alternative paths...
    
    REM electron-builder may place extraResources differently
    dir /s /b "%BUILD_DIR%\arena-server.exe" 2>nul
)

echo [OK] Build verified.
echo.

REM ── Step 5: Create distribution zip ─────────────────────────
echo [5/5] Creating distribution zip...
echo.

set "ZIP_NAME=arena-v%VERSION%.zip"

REM Use PowerShell to create the zip (available on all modern Windows)
if exist "build\%ZIP_NAME%" del "build\%ZIP_NAME%"
powershell -NoProfile -Command "Compress-Archive -Path '%BUILD_DIR%\*' -DestinationPath 'build\%ZIP_NAME%' -Force"
if errorlevel 1 (
    echo [ERROR] Failed to create zip!
    exit /b 1
)

REM Calculate SHA-256 hash
echo.
echo [INFO] Calculating SHA-256 hash...
for /f "tokens=1" %%h in ('certutil -hashfile "build\%ZIP_NAME%" SHA256 ^| findstr /v "hash CertUtil"') do (
    set "SHA256=%%h"
    goto :got_hash
)
:got_hash

echo.
echo ============================================================
echo   BUILD COMPLETE
echo ============================================================
echo.
echo   Package:  build\%ZIP_NAME%
echo   Version:  %VERSION%
echo   SHA-256:  %SHA256%
echo.
echo   To test: Unzip on a machine without Python/Node installed
echo            and run "Hero's Call Arena.exe"
echo.
echo ============================================================
echo.

endlocal
