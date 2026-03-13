@echo off
REM ============================================================
REM  publish-update.bat — Build, package, and publish a game update
REM
REM  This script:
REM    1. Reads version from client/package.json
REM    2. Runs the full game build pipeline
REM    3. Reads patch notes from build/patch-notes.md
REM    4. Generates latest.json manifest with version, hash, URL
REM    5. Uploads the zip + latest.json to the configured host
REM
REM  Prerequisites:
REM    - For R2 hosting:  Install rclone and run 'rclone config'
REM    - For GitHub:      Install gh CLI and authenticate
REM    - For local:       No setup needed (files go to build/publish/)
REM
REM  Configuration: scripts/publish-config.json
REM  Run from repo root: scripts\publish-update.bat
REM ============================================================

setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

REM ── Ensure GitHub CLI is on PATH ────────────────────────────
if exist "C:\Program Files\GitHub CLI\gh.exe" (
    set "PATH=C:\Program Files\GitHub CLI;%PATH%"
)

echo.
echo ============================================================
echo   Hero's Call Arena — Publish Update
echo ============================================================
echo.

REM ── Read version from client/package.json ───────────────────
for /f "tokens=2 delims=:, " %%a in ('findstr /C:"\"version\"" client\package.json') do (
    set "VERSION=%%~a"
    goto :got_version
)
:got_version
if "%VERSION%"=="" (
    echo [ERROR] Could not read version from client\package.json
    exit /b 1
)
echo [INFO] Publishing version: %VERSION%
echo.

REM ── Read host config ────────────────────────────────────────
set "CONFIG_FILE=scripts\publish-config.json"
if not exist "%CONFIG_FILE%" (
    echo [ERROR] Config file not found: %CONFIG_FILE%
    echo         Copy scripts\publish-config.json and fill in your hosting details.
    exit /b 1
)

REM Parse 'host' field from config
for /f "tokens=2 delims=:, " %%h in ('findstr /C:"\"host\"" "%CONFIG_FILE%"') do (
    set "HOST=%%~h"
    goto :got_host
)
:got_host
echo [INFO] Upload target: %HOST%
echo.

REM ── Step 1: Build the game package ──────────────────────────
echo [1/5] Building game package...
echo.

call scripts\build-game-package.bat
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Fix errors above before publishing.
    exit /b 1
)

REM ── Verify build output exists ──────────────────────────────
set "ZIP_FILE=build\arena-v%VERSION%.zip"
if not exist "%ZIP_FILE%" (
    echo [ERROR] Expected zip not found: %ZIP_FILE%
    exit /b 1
)

REM ── Step 2: Get SHA-256 hash ────────────────────────────────
echo [2/5] Calculating SHA-256 hash...
echo.

for /f "tokens=1" %%h in ('certutil -hashfile "%ZIP_FILE%" SHA256 ^| findstr /v "hash CertUtil"') do (
    set "SHA256=%%h"
    goto :got_hash
)
:got_hash
echo [INFO] SHA-256: %SHA256%

REM ── Get file size ───────────────────────────────────────────
for %%F in ("%ZIP_FILE%") do set "FILE_SIZE=%%~zF"
echo [INFO] File size: %FILE_SIZE% bytes
echo.

REM ── Step 3: Read patch notes ────────────────────────────────
echo [3/5] Reading patch notes...
echo.

set "PATCH_NOTES_FILE=build\patch-notes.md"
if not exist "%PATCH_NOTES_FILE%" (
    echo [WARNING] No patch notes found at %PATCH_NOTES_FILE%
    echo          Run scripts\write-patch-notes.bat first, or create build\patch-notes.md manually.
    echo          Using default patch notes.
    set "PATCH_NOTES=### v%VERSION%\n- Bug fixes and improvements"
) else (
    echo [INFO] Patch notes found at %PATCH_NOTES_FILE%
)

REM ── Step 4: Generate latest.json ────────────────────────────
echo [4/5] Generating latest.json manifest...
echo.

REM Get today's date in YYYY-MM-DD format
for /f "tokens=2 delims==" %%d in ('wmic os get localdatetime /value 2^>nul') do set "DT=%%d"
set "RELEASE_DATE=%DT:~0,4%-%DT:~4,2%-%DT:~6,2%"

REM Determine download URL based on host
if "%HOST%"=="r2" (
    for /f "tokens=2 delims=:, " %%u in ('findstr /C:"\"publicUrl\"" "%CONFIG_FILE%"') do (
        set "RAW_URL=%%~u"
        goto :got_r2_url
    )
    :got_r2_url
    REM Reconstruct URL — findstr splits on colon so we need to rejoin
    for /f "tokens=*" %%L in ('powershell -NoProfile -Command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).r2.publicUrl"') do set "PUBLIC_URL=%%L"
    set "DOWNLOAD_URL=!PUBLIC_URL!/arena-v%VERSION%.zip"
)
if "%HOST%"=="github" (
    for /f "tokens=*" %%L in ('powershell -NoProfile -Command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).github.repo"') do set "GH_REPO=%%L"
    set "DOWNLOAD_URL=https://github.com/!GH_REPO!/releases/download/v%VERSION%/arena-v%VERSION%.zip"
)
if "%HOST%"=="local" (
    set "DOWNLOAD_URL=http://localhost:8088/arena-v%VERSION%.zip"
)

echo [INFO] Download URL: %DOWNLOAD_URL%

REM Generate latest.json using PowerShell for proper JSON with embedded patch notes
if not exist "build\publish" mkdir "build\publish"

powershell -NoProfile -Command ^
  "$patchFile = 'build\patch-notes.md'; " ^
  "if (Test-Path $patchFile) { $notes = (Get-Content $patchFile -Raw) -replace '\\', '\\\\' -replace '\"', '\\"' -replace \"`r`n\", '\n' -replace \"`n\", '\n' } " ^
  "else { $notes = '### v%VERSION%\n- Bug fixes and improvements' }; " ^
  "$json = @{ version = '%VERSION%'; releaseDate = '%RELEASE_DATE%'; downloadUrl = '%DOWNLOAD_URL%'; downloadSize = [long]%FILE_SIZE%; sha256 = '%SHA256%'; patchNotes = $notes; minLauncherVersion = '1.0.0' }; " ^
  "$text = ($json | ConvertTo-Json -Depth 3); " ^
  "[System.IO.File]::WriteAllText('build\publish\latest.json', $text, (New-Object System.Text.UTF8Encoding($false)))"

if errorlevel 1 (
    echo [ERROR] Failed to generate latest.json
    exit /b 1
)

REM Also copy the zip to publish dir for local testing
copy "%ZIP_FILE%" "build\publish\" >nul 2>&1

echo [OK] latest.json generated at build\publish\latest.json
echo.

REM ── Step 5: Upload to host ──────────────────────────────────
echo [5/5] Uploading to %HOST%...
echo.

if "%HOST%"=="r2" goto :upload_r2
if "%HOST%"=="github" goto :upload_github
if "%HOST%"=="local" goto :upload_local

echo [ERROR] Unknown host: %HOST%
echo         Set 'host' in %CONFIG_FILE% to: r2 ^| github ^| local
exit /b 1

REM ── R2 Upload ───────────────────────────────────────────────
:upload_r2
    REM Verify rclone is installed
    rclone version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] rclone not found. Install it from https://rclone.org/downloads/
        echo         Then run: rclone config
        echo         Create a remote named 'r2' pointing to your Cloudflare R2 bucket.
        exit /b 1
    )

    for /f "tokens=*" %%L in ('powershell -NoProfile -Command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).r2.rcloneRemote"') do set "RCLONE_REMOTE=%%L"
    for /f "tokens=*" %%L in ('powershell -NoProfile -Command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).r2.bucket"') do set "R2_BUCKET=%%L"

    echo [INFO] Uploading zip to R2...
    rclone copyto "%ZIP_FILE%" "%RCLONE_REMOTE%:%R2_BUCKET%/arena-v%VERSION%.zip" --progress
    if errorlevel 1 (
        echo [ERROR] Failed to upload zip to R2
        exit /b 1
    )

    echo [INFO] Uploading latest.json to R2...
    rclone copyto "build\publish\latest.json" "%RCLONE_REMOTE%:%R2_BUCKET%/latest.json" --progress
    if errorlevel 1 (
        echo [ERROR] Failed to upload latest.json to R2
        exit /b 1
    )

    echo [OK] Uploaded to R2 successfully.
    goto :upload_done

REM ── GitHub Release ──────────────────────────────────────────
:upload_github
    REM Verify gh CLI is installed
    gh --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] GitHub CLI (gh) not found. Install from https://cli.github.com/
        echo         Then run: gh auth login
        exit /b 1
    )

    for /f "tokens=*" %%L in ('powershell -NoProfile -Command "(Get-Content '%CONFIG_FILE%' | ConvertFrom-Json).github.repo"') do set "GH_REPO=%%L"

    echo [INFO] Creating GitHub release v%VERSION%...
    gh release create "v%VERSION%" "%ZIP_FILE%" --repo "%GH_REPO%" --title "v%VERSION%" --notes-file "%PATCH_NOTES_FILE%" 2>nul
    if errorlevel 1 (
        echo [WARNING] Release may already exist — attempting to upload asset to existing release...
        gh release upload "v%VERSION%" "%ZIP_FILE%" --repo "%GH_REPO%" --clobber
        if errorlevel 1 (
            echo [ERROR] Failed to upload to GitHub release
            exit /b 1
        )
    )

    REM Push latest.json to gh-pages branch for GitHub Pages hosting
    echo [INFO] Deploying latest.json to GitHub Pages...
    
    REM Create a temp directory for gh-pages content
    if exist "build\gh-pages-temp" rmdir /s /q "build\gh-pages-temp"
    mkdir "build\gh-pages-temp"
    copy "build\publish\latest.json" "build\gh-pages-temp\latest.json"
    
    REM Use git to push to gh-pages branch
    pushd "build\gh-pages-temp"
    git init
    git checkout -b gh-pages
    git add latest.json
    git commit -m "Update latest.json to v%VERSION%"
    git remote add origin "https://github.com/%GH_REPO%.git"
    git push origin gh-pages --force
    popd
    
    REM Clean up temp directory
    rmdir /s /q "build\gh-pages-temp"
    
    echo [OK] latest.json deployed to GitHub Pages.
    echo [INFO] Manifest URL: https://%GH_REPO:~0,14%.github.io/%GH_REPO:~15%/latest.json

    echo [OK] GitHub release created.
    goto :upload_done

REM ── Local (no upload) ───────────────────────────────────────
:upload_local
    echo [INFO] Local mode — no upload performed.
    echo [INFO] Files ready at build\publish\:
    dir /b "build\publish\"
    echo.
    echo [TIP] To test locally, serve build\publish\ with:
    echo       npx http-server build\publish -p 8088 --cors
    echo       Then set LAUNCHER_MANIFEST_URL=http://localhost:8088/latest.json
    goto :upload_done

:upload_done
echo.
echo ============================================================
echo   PUBLISH COMPLETE
echo ============================================================
echo.
echo   Version:      %VERSION%
echo   Release Date: %RELEASE_DATE%
echo   SHA-256:      %SHA256%
echo   File Size:    %FILE_SIZE% bytes
echo   Host:         %HOST%
echo   Download URL: %DOWNLOAD_URL%
echo.
echo   Testers will see this update next time they open the launcher.
echo.
echo ============================================================
echo.

endlocal
