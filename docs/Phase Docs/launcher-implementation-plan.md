# Hero's Call Arena — Launcher Implementation Plan

> Created: March 12, 2026  
> Status: Phase L7 Complete  
> Goal: Build a lightweight game launcher so playtesters download once, then receive updates automatically

---

## Table of Contents

1. [Problem & Solution](#problem--solution)  
2. [Hosting Decision](#hosting-decision)  
3. [Architecture](#architecture)  
4. [Update Strategy](#update-strategy)  
5. [Color Theme Reference](#color-theme-reference)  
6. [Implementation Phases](#implementation-phases)  
7. [Folder Structure](#folder-structure)  
8. [Tester Experience](#tester-experience)  
9. [Open Questions](#open-questions)

---

## Problem & Solution

**Problem:** Every update requires sending a new setup.exe to 5–10 playtesters. No auto-update, no central place to check versions, rough experience that undermines confidence in the game.

**Solution:** A separate Electron **Launcher** app (~5 MB) that playtesters install once. The launcher handles downloading the game, checking for updates, and launching the game — like Battle.net or the PoE launcher, but lightweight.

---

## Hosting Decision

### The Challenge
The full game package is ~1.3 GB. GitHub Releases supports up to 2 GB per file, but upload/download speeds are mediocre and there's a 5 GB total soft limit per repo.

### Recommendation: **Backblaze B2 + Cloudflare CDN (Free Tier)**

| Option | Cost | Max File Size | Speed | Daily Update Friendly? | Verdict |
|--------|------|---------------|-------|------------------------|---------|
| GitHub Releases | Free | 2 GB | Slow-medium | Awkward (need new release per push) | Backup option |
| Google Drive | Free (15 GB) | 5 GB | Medium | Bad — API auth is painful, rate limits, sharing links break | Not recommended |
| Backblaze B2 | Free 10 GB storage + 1 GB/day egress | 5 GB | Fast (with CF) | Yes — simple file upload/overwrite | **Recommended** |
| Cloudflare R2 | Free 10 GB storage + unlimited egress | 5 GB | Very fast | Yes | Great alternative |
| Self-hosted VPS | $5–10/mo | Unlimited | Varies | Yes | Overkill for 5–10 testers |
| itch.io butler | Free | Large | Good | Yes — built-in delta patching | Worth considering |

### Why Backblaze B2 + Cloudflare:
- **Free tier** covers 5–10 testers easily (10 GB storage, 1 GB/day free egress, but Cloudflare caches bypass B2 egress)
- Cloudflare's free CDN sits in front — fast downloads, zero egress cost
- Simple REST API — upload a file, get a URL
- No auth headaches for downloads (public bucket)
- Survives daily pushes without friction

### Simpler Alternative: **Cloudflare R2**
- $0 for first 10 GB storage, **$0 egress always** (no bandwidth charges ever)
- S3-compatible API — easy to script uploads
- No CDN setup needed — R2 has built-in public access
- Slightly easier than B2 + Cloudflare combo

### Simplest Possible: **GitHub Releases**
- If the game compresses under 2 GB, this works today with zero setup
- Each update = a new GitHub Release with the zip attached
- Manifest (`latest.json`) hosted via GitHub Pages
- Downside: clunky for daily updates, slow download speeds

### Decision: **GitHub Releases** (active)
Cloudflare R2 was originally recommended but requires a credit card even for the free tier. Google Drive was rejected — no direct download URLs for large files (consent screens), rate limiting, and OAuth complexity. **GitHub Releases** is the chosen host:
- Free, no credit card required
- 2 GB per release asset (game zip compresses to ~400–600 MB, well under limit)
- GitHub CLI (`gh`) handles automated uploads from `publish-update.bat`
- Direct download URLs for public repos — no auth needed for testers

**Setup completed:**
- GitHub repo: **`Jack73hRipper/heros-call-arena`** (public)
- GitHub CLI v2.88.1 installed at `C:\Program Files\GitHub CLI\gh.exe`
- Authenticated via `gh auth login` (keyring-stored token)
- `scripts/publish-config.json` configured with `"host": "github"` and repo `Jack73hRipper/heros-call-arena`
- Publish pipeline is host-agnostic — can switch to R2 or B2 later by changing the config

**Note:** `gh.exe` is not on the system PATH by default. The publish script or terminal session needs `C:\Program Files\GitHub CLI` added to PATH, or call `gh.exe` by full path.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  LAUNCHER  (Electron — installed once, ~5 MB)            │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  UI                                                │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  Game Banner / Logo area                     │  │  │
│  │  ├──────────────────────────────────────────────┤  │  │
│  │  │  Patch Notes Panel (scrollable)              │  │  │
│  │  ├──────────────────────────────────────────────┤  │  │
│  │  │  Status: "Ready" / "Downloading..." / etc    │  │  │
│  │  │  [████████████░░░░] 67% — 230 MB / 340 MB   │  │  │
│  │  ├──────────────────────────────────────────────┤  │  │
│  │  │           [ ▶  P L A Y ]                     │  │  │
│  │  │  v0.3.1 installed    ⚙ Settings              │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Systems:                                                │
│  ├─ VersionChecker  — fetch latest.json, compare local   │
│  ├─ Downloader      — stream zip with progress callback  │
│  ├─ Verifier        — SHA-256 integrity check            │
│  ├─ Extractor       — unzip to install directory         │
│  ├─ GameLauncher    — spawn game process, monitor exit    │
│  └─ SelfUpdater     — electron-updater for launcher      │
└──────────────────────────────────────────────────────────┘
         │                                  │
         │ HTTPS GET                        │ child_process.spawn()
         ▼                                  ▼
┌────────────────────┐       ┌──────────────────────────────┐
│  File Host         │       │  GAME (installed locally)     │
│  (R2 / B2 / GH)   │       │                              │
│                    │       │  ├─ game.exe (Electron)      │
│  latest.json       │       │  ├─ server/ (PyInstaller)    │
│  arena-v0.3.1.zip  │       │  ├─ resources/               │
│  patch-notes.md    │       │  └─ configs, assets, maps    │
└────────────────────┘       └──────────────────────────────┘
```

---

## Update Strategy

### Full Zip Replacement (Phase 1)
- Each update = full game zip (~1.3 GB, likely ~400–600 MB compressed)
- Launcher downloads, verifies hash, extracts, replaces old version
- Simple, reliable, no edge cases
- At 5–10 testers with daily pushes, bandwidth is manageable

### Future: File-Level Delta Updates (Phase 2 — if needed)
- Generate a file manifest with per-file hashes
- Launcher compares local vs remote manifest
- Only downloads changed files
- Typical daily code update would be ~5–20 MB instead of 600 MB
- Implement this only if full-zip downloads become a pain point

---

## Color Theme Reference

The launcher will match the game's grimdark aesthetic:

| Token | Value | Usage |
|-------|-------|-------|
| bg-abyss | `#06060b` | Window background |
| bg-deep | `#0a0a10` | Panel backgrounds |
| bg-panel | `#0f0e16` | Card/section backgrounds |
| bg-surface | `#16141f` | Elevated surfaces |
| bg-elevated | `#1c1a28` | Hover states, raised elements |
| accent-ember | `#c4973a` | Primary accent (buttons, highlights) |
| accent-ember-bright | `#daa84a` | Hover/active accent |
| accent-ember-dim | `#8a6a28` | Subtle accent, borders |
| accent-crimson | `#8b2020` | Alert, danger states |
| text-primary | `#d4c5a0` | Main text |
| text-body | `#b0a58a` | Body text |
| text-secondary | `#7a7060` | Secondary/muted text |
| text-bright | `#f0e8d0` | Emphasis text |
| border-dark | `#1a1820` | Outer borders |
| border-subtle | `#2a2835` | Inner borders |
| border-ember | `rgba(196,151,58,0.4)` | Accent borders |
| font-heading | `'Cinzel', 'Georgia', serif` | Titles |
| font-body | `'Inter', 'Segoe UI', sans-serif` | Body text |
| shadow-glow-ember | `0 0 20px rgba(196,151,58,0.15)` | Ember glow effect |

Play button should use the ember accent with a subtle glow — large, centered, unmissable.

---

## Implementation Phases

### Phase L1: Launcher Shell
> Scaffold the launcher and get a polished window on screen

**Tasks:**
- [x] Create `launcher/` project at repo root
- [x] `npm init` with Electron + electron-builder
- [x] Create `main.js` — BrowserWindow (900×600, frameless or custom title bar)
- [x] Create `index.html` — launcher UI layout
  - Game title banner area (text-based until logo exists — "HERO'S CALL" in Cinzel font)
  - Patch notes section (placeholder text)
  - Status bar ("Ready to play")
  - Large PLAY button (ember gold, glow on hover)
  - Version footer
  - Settings icon (gear)
- [x] Create `styles.css` — grimdark theme matching game CSS variables
- [x] Create `renderer.js` — basic UI binding (play button click → log for now)
- [x] Create `preload.js` — expose IPC bridge
- [x] Window chrome: dark title bar, custom minimize/maximize/close buttons
- [ ] App icon (reuse existing favicon.ico or placeholder) — deferred, no icon file exists yet
- [x] Test: launcher opens, looks polished, play button is clickable
- [x] Create `start-launcher.bat` in project root for dev testing

**Deliverable:** A beautiful launcher window that opens and looks like a real game launcher. Play button logs to console but doesn't do anything yet.

---

### Phase L2: Game Packaging (PyInstaller + Electron Build)
> Bundle the game into a self-contained package that runs without Python installed

**Tasks:**
- [x] Create PyInstaller spec file for the FastAPI server
  - Bundle all of `server/app/`, `server/configs/`, `server/data/`
  - Target: `--onedir` mode (folder with `arena-server.exe`)
  - Test: `arena-server.exe` starts and serves on port 8000
- [x] Modify game's Electron `main.cjs` to spawn the bundled server
  - PROD mode: spawn `arena-server.exe` as child process
  - Wait for server ready (poll `/health` endpoint)
  - On game exit: kill server process
- [x] Add a `/health` endpoint to FastAPI if not already present
- [x] Create `scripts/build-game-package.bat`:
  1. `cd server && pyinstaller arena-server.spec`
  2. `cd client && npm run build` (Vite)
  3. `cd client && npx electron-builder --dir` (unpackaged build)
  4. Copy PyInstaller output into the Electron build folder
  5. Zip the result → `arena-v{VERSION}.zip`
- [ ] Test: unzip on a clean machine (no Python/Node) → game.exe works
- [x] Document the build process

**Deliverable:** A single zip file that contains the complete game — double-click `Hero's Call Arena.exe` and everything starts (server + client). No Python or Node required on the tester's machine.

**Key Detail — PyInstaller:** 
```bash
# From server/ directory
pip install pyinstaller
pyinstaller --name arena-server --onedir app/main.py \
  --add-data "configs;configs" \
  --add-data "data;data" \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on
```

---

### Phase L3: Manifest & Version Check ✅
> Launcher can detect when updates are available

**Tasks:**
- [x] Define manifest schema (`latest.json`):
  ```json
  {
    "version": "0.3.1",
    "releaseDate": "2026-03-12",
    "downloadUrl": "https://your-host.com/arena-0.3.1.zip",
    "downloadSize": 450000000,
    "sha256": "a1b2c3d4...",
    "patchNotes": "### v0.3.1\n- Monster rarity visual improvements\n- 6 new dungeon themes",
    "minLauncherVersion": "1.0.0"
  }
  ```
- [x] Create local version file: `%LOCALAPPDATA%/HeroCallArena/installed.json`
  ```json
  {
    "version": "0.3.0",
    "installedDate": "2026-03-11",
    "installPath": "C:/Users/.../AppData/Local/HeroCallArena/game"
  }
  ```
- [x] Implement `VersionChecker` module in launcher:
  - Fetch `latest.json` from host on launcher startup
  - Compare `latest.version` vs `installed.version`
  - Return state: `not-installed` | `up-to-date` | `update-available` | `check-failed`
- [x] Update launcher UI based on state:
  - `not-installed` → PLAY button says "INSTALL" 
  - `up-to-date` → PLAY button says "PLAY", status "Ready — v0.3.1"
  - `update-available` → PLAY button says "UPDATE", show patch notes
  - `check-failed` → "Offline — Play last installed version" (if game exists)
- [x] Render patch notes markdown in the patch notes panel
- [x] Host a test `latest.json` (even on localhost for initial testing)

**Deliverable:** Launcher knows whether the game is installed, up to date, or needs an update. Patch notes display in the UI.

---

### Phase L4: Download & Install ✅
> Launcher can download and install/update the game

**Tasks:**
- [x] Implement `Downloader` module (`lib/downloader.js`):
  - Stream download with Node `https`/`http` modules
  - Progress callback (bytes received / total bytes)
  - Write to temp file: `%TEMP%/arena-update-{timestamp}.zip`
  - Support cancellation via AbortController
  - Follow HTTP redirects (301, 302, 307, 308)
- [x] Implement `Verifier` module (`lib/verifier.js`):
  - SHA-256 hash of downloaded zip via streaming `crypto.createHash`
  - Compare against `latest.json` hash
  - Reject corrupted downloads with clear error message
- [x] Implement `Extractor` module (`lib/extractor.js`):
  - Unzip to `%LOCALAPPDATA%/HeroCallArena/game/` using `adm-zip`
  - For updates: extract to staging dir first, then atomic swap (rename old → backup, staging → install, remove backup)
  - Clean up temp files on success
- [x] Implement `GameLauncher` module (`lib/game-launcher.js`):
  - `child_process.spawn()` the game executable
  - Auto-detect exe name from multiple candidates
  - Launcher minimizes while game runs
  - Detect game exit → launcher comes back to foreground, re-checks for updates
- [x] Wire up UI:
  - Progress bar during download (percentage + MB counter)
  - Status messages: "Downloading…" → "Verifying…" → "Installing…" → "Ready!"
  - Error states with RETRY button
  - PLAY button becomes CANCEL during download
  - PLAY button disabled during verify/install/launch
  - New states: downloading, verifying, installing, launching, playing, error
- [x] Write `installed.json` after successful install
- [x] Handle edge cases:
  - Disk space check before download (via wmic on Windows)
  - Game already running → blocked with error message
  - Download cancellation → clean up temp file, return to previous state
  - Hash mismatch → clear error, temp file cleaned up
  - Network/timeout errors → friendly error with retry
- [ ] Resume interrupted downloads (deferred — adds complexity for minimal gain at 5–10 testers)

**Deliverable:** Full install + update flow working end to end. Tester clicks "Install" or "Update", sees progress, game is ready to play.

---

### Phase L5: Publish Pipeline ✅
> Streamlined workflow for pushing updates to testers

**Tasks:**
- [x] Choose and set up file host (R2, B2, or GitHub Releases)
  - Host-agnostic config: `scripts/publish-config.json` supports `r2`, `github`, and `local` modes
  - R2: uses `rclone` for upload to Cloudflare R2 bucket
  - GitHub: uses `gh` CLI to create releases and upload assets
  - Local: outputs to `build/publish/` for testing without upload
- [x] Create `scripts/publish-update.bat`:
  1. Reads version from `client/package.json`
  2. Runs `scripts/build-game-package.bat` (full 5-step build)
  3. Calculates SHA-256 of the zip via `certutil`
  4. Reads patch notes from `build/patch-notes.md`
  5. Generates `latest.json` manifest (version, URL, hash, size, patch notes, date)
  6. Uploads zip + `latest.json` to configured host
  7. Prints summary with version, hash, URL, and file size
- [x] Create `scripts/write-patch-notes.bat` — generates patch notes template at `build/patch-notes.md`, opens in VS Code (or Notepad fallback)
- [x] Version bumping helper: `scripts/bump-version.bat patch|minor|major` — parses semver from `client/package.json`, increments, writes back, clears old patch notes
- [ ] Test full cycle: build → publish → launcher detects update → download → play (requires host setup)
- [x] Create `start-publish.bat` convenience wrapper at repo root

**Deliverable:** You run one script, wait for the build, and testers automatically see the update next time they open the launcher.

**Files created:**
- `scripts/publish-config.json` — host configuration (r2/github/local)
- `scripts/publish-update.bat` — full build + publish pipeline
- `scripts/write-patch-notes.bat` — patch notes template generator
- `scripts/bump-version.bat` — semver version bumper
- `start-publish.bat` — convenience wrapper

---

### Phase L6: Launcher Self-Update ✅
> The launcher can update itself without a new setup.exe

**Tasks:**
- [x] Integrate `electron-updater` into the launcher
  - Added `electron-updater` as a production dependency
  - Main process auto-checks for launcher updates on startup (packaged builds only)
  - Events relayed to renderer: checking → available → downloading → downloaded → error
  - Auto-download enabled — updates download silently in the background
  - `autoInstallOnAppQuit = true` — applies update when user closes the launcher
  - Manual "Restart Now" option via `quitAndInstall()` IPC handler
- [x] Configure electron-builder to publish launcher updates (GitHub Releases)
  - Added `publish` config in package.json: `{ provider: "github", owner: "Jack73hRipper", repo: "heros-call-arena" }`
  - Added `npm run publish` script (`electron-builder --win --publish always`)
  - Uses same GitHub repo as game releases (`Jack73hRipper/heros-call-arena`)
  - electron-updater reads `latest.yml` auto-generated by electron-builder in the release
- [x] On launcher startup: check for launcher updates first, then game updates
  - `checkForLauncherUpdate()` called in `app.whenReady()` — runs before renderer's game version check
  - Skipped in dev mode (`app.isPackaged` check) — no false errors during development
  - Network failures silently caught — launcher update failure never blocks game usage
- [x] Auto-download + install launcher update → restart
  - Notification banner appears at top of launcher when update is available/downloading
  - Shows download progress percentage
  - "Restart Now" button appears when download completes
  - Styled with ember accent to match grimdark theme
- [x] Version the launcher separately from the game (launcher v1.x, game v0.x)
  - Launcher version lives in `launcher/package.json` (`"version": "1.0.0"`)
  - Game version lives in `client/package.json` (managed by `scripts/bump-version.bat`)

**Deliverable:** If you need to change the launcher itself, testers get the update automatically. They never need to re-download the launcher installer.

**Files modified:**
- `launcher/package.json` — added electron-updater dep, publish config, publish script
- `launcher/main.js` — electron-updater integration, event relay, IPC handler, startup check
- `launcher/preload.js` — launcher update IPC bridge (onLauncherUpdateStatus, installLauncherUpdate)
- `launcher/renderer.js` — launcher update notification bar handling
- `launcher/index.html` — launcher update notification banner element
- `launcher/styles.css` — notification bar styling (ember-accented top bar)

---

### Phase L7: Polish & Hardening ✅
> Final UX touches for a professional feel

**Tasks:**
- [x] Settings panel:
  - Install location (with folder picker)
  - Auto-check for updates on launch (toggle)
  - Minimize to system tray when game is running (toggle)
  - Clear cache / re-download game
- [x] Error handling:
  - Network timeout → friendly message + retry
  - Hash mismatch → re-download
  - Disk full → clear message with required space
  - Server unreachable → offline mode (launch last installed version)
- [x] System tray icon when minimized
- [x] Launcher remembers window position/size
- [x] Loading spinner during version check
- [x] Animated progress bar (smooth interpolation)
- [x] "Repair" option — force re-download + re-install
- [x] Keyboard shortcuts (Enter = Play, Esc = close settings or close launcher)
- [x] Notification when update is ready (if launcher is in tray)
- [x] Logging to file (`%LOCALAPPDATA%/HeroCallArena/launcher.log`) for debugging tester issues

**Deliverable:** A launcher that feels professional, handles edge cases gracefully, and gives testers confidence in the game.

**Files created:**
- `launcher/lib/logger.js` — file logging with auto-rotation (2 MB max, one backup)
- `launcher/lib/settings.js` — persistent settings (install dir, auto-check, minimize-to-tray, window bounds)

**Files modified:**
- `launcher/main.js` — settings IPC, tray icon, window bounds persistence, repair handler, browse-dir dialog, logging throughout, tray notification on update
- `launcher/preload.js` — settings/repair/browse IPC bridge
- `launcher/renderer.js` — settings panel open/close/save, smooth progress bar (requestAnimationFrame interpolation), loading spinner toggle, repair button with confirmation, Esc key closes settings or launcher
- `launcher/index.html` — settings overlay panel with install dir/browse, toggle switches, repair button; loading spinner SVG in status bar
- `launcher/styles.css` — settings overlay/panel/toggle/button styles, spinner animation, smooth progress bar (will-change)

---

## Future Considerations (Not In Scope Now)

| Feature | When | Why |
|---------|------|-----|
| **Delta/differential updates** | When 600 MB daily downloads become a problem | Per-file manifest diffing — only download changed files (~5–20 MB typical) |
| **Multiple game channels** | When you want alpha/beta/stable | Manifest per channel, channel selector in launcher |
| **Server-side backend hosting** | When you want centralized multiplayer | Testers connect to your hosted server instead of running locally |
| **Account system** | When you need to gate access | Simple key/token system — launcher validates before allowing download |
| **Analytics** | When you want install/play metrics | Launcher pings a simple endpoint on launch/update |

---

## Folder Structure

```
Arena/
├── launcher/                        # NEW — Launcher Electron app
│   ├── package.json                 #   Electron + electron-builder config
│   ├── main.js                      #   Main process (window, IPC, auto-update)
│   ├── preload.js                   #   Preload script (IPC bridge)
│   ├── index.html                   #   Launcher UI
│   ├── styles.css                   #   Grimdark theme
│   ├── renderer.js                  #   UI logic (state machine, event handlers)
│   ├── lib/                         #   Core modules
│   │   ├── version-checker.js       #     Fetch + compare versions
│   │   ├── downloader.js            #     Stream download with progress
│   │   ├── verifier.js              #     SHA-256 hash check
│   │   ├── extractor.js             #     Unzip to install dir
│   │   └── game-launcher.js         #     Spawn game process
│   └── assets/                      #   Launcher assets
│       ├── icon.ico                 #     App icon
│       └── banner.png               #     Banner art (placeholder until logo exists)
│
├── scripts/                         # Build & publish automation
│   ├── build-game-package.bat       #   Build game into distributable zip
│   ├── publish-update.bat           #   Full build + publish pipeline
│   ├── publish-config.json          #   Host configuration (r2/github/local)
│   ├── write-patch-notes.bat        #   Patch notes template + editor
│   ├── bump-version.bat             #   Semver version bumper
│   └── arena-server.spec            #   PyInstaller spec for the server
│
├── client/                          #   (existing — the game)
├── server/                          #   (existing — the backend)
└── ...
```

**On the tester's machine:**
```
%LOCALAPPDATA%/
└── HeroCallArena/
    ├── installed.json               # Local version tracking
    ├── launcher.log                 # Debug log
    └── game/                        # The installed game
        ├── Hero's Call Arena.exe    #   Game Electron executable
        ├── resources/               #   Electron resources (built frontend)
        ├── arena-server/            #   PyInstaller output (bundled Python server)
        │   ├── arena-server.exe
        │   └── ... (Python deps)
        └── configs/                 #   Game configs
```

---

## Tester Experience

### First Time
1. You send them a link: "Download Hero's Call Arena Launcher" (~5 MB)
2. They run `HeroCallArenaLauncher-Setup.exe` → installs in seconds
3. Launcher opens — dark grimdark UI, "HERO'S CALL" banner
4. Game not detected → big **INSTALL** button
5. Click Install → progress bar fills → "Installing..." → done
6. Button changes to **PLAY** → click → game launches

### Daily Updates
1. Open launcher (or it was already in system tray)
2. Launcher auto-checks → "Update Available — v0.3.2"
3. Patch notes appear: "- Fixed hexblade shadow step bug\n- New dungeon theme"
4. Click **UPDATE** → progress bar → done
5. Click **PLAY**

### No Internet
1. Open launcher → version check fails
2. "Could not check for updates — Play offline?"
3. Click **PLAY** → game launches with last installed version

---

## Open Questions

- [x] **File host:** GitHub Releases — repo `Jack73hRipper/heros-call-arena` (public). Cloudflare R2 rejected (requires credit card for free tier). Google Drive rejected (consent screens, rate limiting, OAuth). GitHub CLI (`gh` v2.88.1) installed and authenticated. Publish pipeline configured via `scripts/publish-config.json`.
- [x] **Game versioning scheme:** semver — `scripts/bump-version.bat patch|minor|major` manages versioning from `client/package.json`
- [ ] **Logo/banner art:** text-only placeholder for now, swap in real art when ready
- [ ] **Launcher name:** "Hero's Call Arena Launcher" or just "Hero's Call Launcher"?
- [ ] **Python bundling size:** need to test PyInstaller output size — may need `--exclude-module` to trim unused packages

---

## Dependencies to Install

### Launcher
```
electron
electron-builder
electron-updater       # for launcher self-update (Phase L6)
adm-zip               # for extraction (or use Node built-in zlib)
```

### Build Scripts
```
pip install pyinstaller    # for bundling the Python server
```

---

## Progress Tracker

| Phase | Status | Notes |
|-------|--------|-------|
| L1: Launcher Shell | **Complete** | Frameless 900×600 Electron window, grimdark theme, custom title bar, PLAY button with hover glow, patch notes panel, status bar with progress skeleton, settings icon, keyboard shortcut (Enter=Play), start-launcher.bat |
| L2: Game Packaging | **Complete** | PyInstaller spec (`scripts/arena-server.spec`), `if __name__` entry point in server main.py, Electron main.cjs spawns/kills bundled server in PROD mode (polls `/health`), electron-builder `extraResources` config, `scripts/build-game-package.bat` (5-step build pipeline: PyInstaller → Vite → electron-builder → verify → zip+SHA256) |
| L3: Manifest & Version Check | **Complete** | VersionChecker module fetches remote latest.json, compares with local installed.json, UI state machine for not-installed/up-to-date/update-available/check-failed, patch notes markdown rendering, test manifest server |
| L4: Download & Install | **Complete** | Downloader with progress/cancellation, SHA-256 Verifier, Extractor with atomic update swap, GameLauncher with auto-detect exe/minimize/foreground-on-exit, full UI progress bar with status pipeline, disk space check, installed.json write-back |
| L5: Publish Pipeline | **Complete** | GitHub Releases host (`Jack73hRipper/heros-call-arena`, public), `gh` CLI v2.88.1 authenticated, host-agnostic publish-config.json (R2/GitHub/local), publish-update.bat (build→hash→manifest→upload via `gh release create`), write-patch-notes.bat (template + editor), bump-version.bat (semver patch/minor/major), start-publish.bat convenience wrapper |
| L6: Launcher Self-Update | **Complete** | electron-updater integration, auto-download + background install, GitHub Releases publish config, launcher update notification bar with "Restart Now" button, dev-mode skip, separate launcher versioning (v1.x) from game versioning (v0.x) |
| L7: Polish & Hardening | **Complete** | Settings panel (install dir/browse, auto-check toggle, minimize-to-tray toggle, repair game), system tray icon + context menu, window position/size persistence, loading spinner during version check, smooth progress bar (rAF interpolation), file logging with rotation (launcher.log), keyboard shortcuts (Enter=Play, Esc=close/settings), tray notification on launcher update, comprehensive error logging throughout all operations |
