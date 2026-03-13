# Hero's Call Arena — Launcher & Update Pipeline

> Last updated: March 12, 2026

---

## Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| **Source code** | [Jack73hRipper/heros-call-arena](https://github.com/Jack73hRipper/heros-call-arena) (public) | All game + launcher source |
| **Game releases** | GitHub Releases on the same repo | Hosts `arena-v{VERSION}.zip` (~300–600 MB) |
| **Manifest** | GitHub Pages (`gh-pages` branch) | Hosts `latest.json` (launcher update check) and `server-url.json` (remote server discovery) |
| **Manifest URL** | `https://jack73hripper.github.io/heros-call-arena/latest.json` | Hardcoded in `launcher/main.js` |
| **Server URL** | `https://jack73hripper.github.io/heros-call-arena/server-url.json` | Fetched by game client to find the remote server |
| **GitHub CLI** | `C:\Program Files\GitHub CLI\gh.exe` | Used by publish scripts (not on PATH — scripts add it automatically) |
| **Cloudflared** | `C:\Program Files (x86)\cloudflared\cloudflared.exe` | Creates free Cloudflare quick tunnels for online play |

---

## Versioning

| What | Where | Managed by |
|------|-------|------------|
| **Game version** | `client/package.json` → `"version"` | `scripts\bump-version.bat` |
| **Launcher version** | `launcher/package.json` → `"version"` | Manual (only bump when launcher itself changes) |

Game uses semver: `0.MAJOR.PATCH` (e.g., `0.1.0` → `0.1.1` → `0.2.0`)

---

## Pushing a Game Update (3 steps)

### Step 1: Bump the version

```
scripts\bump-version.bat patch
```

Options: `patch` (0.1.0 → 0.1.1), `minor` (0.1.0 → 0.2.0), `major` (0.1.0 → 1.0.0)

### Step 2: Write patch notes

```
scripts\write-patch-notes.bat
```

Opens `build\patch-notes.md` in VS Code. Write what changed, save, close.

### Step 3: Publish

```
start-publish.bat
```

This single script does everything:
1. Builds the Python server with PyInstaller → `arena-server.exe`
2. Builds the frontend with Vite
3. Packages the Electron app with electron-builder
4. Copies the server into the Electron build
5. Zips it all → `build\arena-v{VERSION}.zip`
6. Calculates SHA-256 hash
7. Generates `latest.json` manifest
8. Creates a GitHub Release and uploads the zip
9. Deploys `latest.json` to GitHub Pages (`gh-pages` branch)

**That's it.** Testers will see the update next time they open the launcher.

---

## What Testers Experience

### First time
1. You send them the launcher installer (~5 MB `.exe`)
2. They install it — takes seconds
3. Launcher opens → shows **INSTALL** button
4. Click Install → progress bar → game downloads and installs
5. Click **PLAY**

### When you push an update
1. Tester opens the launcher (or it's already in their system tray)
2. Launcher auto-checks `latest.json` → detects new version
3. Shows **UPDATE** button + patch notes
4. Click Update → downloads → verifies hash → installs
5. Click **PLAY**

### Offline
- Launcher shows "Could not check for updates"
- They can still click **PLAY** to launch the last installed version

---

## Building the Launcher Installer

To generate the launcher `.exe` that you send to testers:

```
cd launcher
npm run build
```

Output: `build\launcher\Hero's Call Arena Launcher Setup {VERSION}.exe`

To publish a launcher self-update (testers get it automatically):

```
cd launcher
npm run publish
```

This uploads to GitHub Releases with `latest.yml` — electron-updater handles the rest.

---

## File Flow Diagram

```
YOU (developer)                          GITHUB                         TESTER
                                                                        
scripts\bump-version.bat                                                
        │                                                               
scripts\write-patch-notes.bat                                           
        │                                                               
start-publish.bat ──────────────►  GitHub Release (v0.x.x)              
        │                              arena-v0.x.x.zip ◄──── Download  
        │                                                         │     
        └──────────────────────►  GitHub Pages (gh-pages)         │     
                                       latest.json ◄──── Fetch    │     
                                                    │             │     
                                              ┌─────┘             │     
                                              ▼                   ▼     
                                         LAUNCHER ──► Compare ──► Install/Update
                                              │                         
                                              └──────► PLAY ──► Game launches
```

---

## Hosting Online (Remote Server)

The game supports remote multiplayer via Cloudflare quick tunnels — no domain, no account setup required.

### Starting the server for online play

```
start-server-online.bat
```

This script does 4 things:
1. Starts the FastAPI server on `localhost:8000` with CORS set to `*`
2. Opens a Cloudflare quick tunnel (free, anonymous — gives you a random `https://xxx.trycloudflare.com` URL)
3. Publishes `server-url.json` to GitHub Pages so players' game clients can find the server
4. Keeps running — press Ctrl+C to stop

### Stopping the server

Close the terminal, then run:

```
stop-server-online.bat
```

This publishes `server-url.json` with `"status": "offline"` so player clients fall back to localhost.

### How players connect

The game client (`serverUrl.js`) automatically:
1. Fetches `server-url.json` from GitHub Pages on startup
2. If `status: "online"` and the URL is reachable → routes all API/WebSocket traffic through the tunnel
3. If offline or unreachable → falls back to `http://localhost:8000` (local play)

No player configuration needed — it's fully automatic.

### Key files for online play

| File | Purpose |
|------|---------|
| `start-server-online.bat` | Start server + tunnel + publish URL |
| `stop-server-online.bat` | Publish offline status |
| `client/src/utils/serverUrl.js` | Client-side server discovery (`getServerUrl()`, `getWsUrl()`, `apiFetch()`) |
| `client/src/utils/fetchWithRetry.js` | Resilient fetch wrapper — auto-prepends server base URL |
| `client/src/hooks/useWebSocket.js` | WebSocket hook — uses dynamic server URL |

---

## Key Files

| File | Purpose |
|------|---------|
| `start-publish.bat` | Convenience wrapper — runs the full publish pipeline |
| `scripts/publish-update.bat` | The actual build + publish logic |
| `scripts/publish-config.json` | Host config (`"host": "github"`, repo name) |
| `scripts/build-game-package.bat` | Builds game into distributable zip (called by publish) |
| `scripts/bump-version.bat` | Increments game version in `client/package.json` |
| `scripts/write-patch-notes.bat` | Opens patch notes template for editing |
| `scripts/arena-server.spec` | PyInstaller spec for bundling the Python backend |
| `launcher/main.js` | Launcher main process (manifest URL, IPC, auto-update) |
| `launcher/lib/version-checker.js` | Fetches `latest.json`, compares with local install |
| `launcher/lib/downloader.js` | Downloads game zip with progress + cancellation |
| `launcher/lib/verifier.js` | SHA-256 hash verification |
| `launcher/lib/extractor.js` | Unzips to install directory with atomic swap |
| `launcher/lib/game-launcher.js` | Spawns the game process |

---

## Tester's Local Files

```
%APPDATA%\heros-call-launcher\          ← Launcher app data
    HeroCallArena\
        installed.json                  ← Tracks installed game version
        launcher.log                    ← Debug log (2 MB max, auto-rotates)
        settings.json                   ← User preferences

%LOCALAPPDATA%\HeroCallArena\game\      ← The installed game
    Hero's Call Arena.exe               ← Game executable
    resources\                          ← Electron resources (built frontend)
    arena-server\                       ← Bundled Python server
        arena-server.exe
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `gh` not recognized | Scripts add `C:\Program Files\GitHub CLI` to PATH automatically. If running manually: `$env:PATH = "C:\Program Files\GitHub CLI;$env:PATH"` |
| Publish fails with auth error | Run `gh auth login` and authenticate |
| Launcher shows "check-failed" | Check internet connection. Verify `https://jack73hripper.github.io/heros-call-arena/latest.json` loads in a browser |
| Hash mismatch after download | The zip on GitHub Releases doesn't match `latest.json`. Re-run `start-publish.bat` |
| electron-builder symlink warnings | Harmless — those are macOS code-signing files, doesn't affect Windows builds |
| Tester can't download (private repo) | Repo must be **public** for unauthenticated downloads |
| Need to change hosting later | Edit `scripts/publish-config.json` — change `"host"` to `"r2"` or `"local"` |
| Tunnel URL not found | `start-server-online.bat` waits 30s. Check `%TEMP%\cloudflared-tunnel.log` for errors |
| Players can't connect remotely | Verify `server-url.json` on GitHub Pages shows `"status": "online"`. Run `stop-server-online.bat` then `start-server-online.bat` to refresh |
| `cloudflared` not found | Install via `winget install Cloudflare.cloudflared` |

---

## Quick Reference

```bash
# Bump version + write notes + publish (the full workflow)
scripts\bump-version.bat patch
scripts\write-patch-notes.bat
start-publish.bat

# Just build locally (no upload)
scripts\build-game-package.bat

# Test launcher in dev mode
start-launcher.bat

# Check GitHub auth
"C:\Program Files\GitHub CLI\gh.exe" auth status

# View releases
"C:\Program Files\GitHub CLI\gh.exe" release list --repo Jack73hRipper/heros-call-arena
```
