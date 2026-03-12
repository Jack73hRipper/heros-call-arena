# Playtest & Distribution System

**Goal:** Friends download a client launcher, install/update the game, and connect to a hosted server.

**Current State:** Electron app exists with NSIS installer build, but the client cannot connect to a remote server in packaged mode. Server only accepts localhost connections.

---

## Phase A — LAN Playtest Foundation

**Objective:** Make the game playable on a local network with zero extra software. Multiple browsers on the same WiFi can connect.

### A1: Server Bind to All Interfaces

**File:** `start-backend.bat`, `start-game.bat`

Add `--host 0.0.0.0` to the uvicorn launch command so the Python backend accepts connections from other machines on the network, not just localhost.

```
# Before
python -m uvicorn app.main:app --reload --port 8000

# After
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### A2: CORS — Allow LAN Origins

**File:** `server/app/config.py`

The CORS whitelist only allows `localhost`. Add a wildcard or LAN-friendly pattern so browsers on other machines aren't blocked.

```python
# Before
CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

# After — allow any local network origin for playtesting
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
    "*",  # Allow all origins during playtest (restrict for production)
]
```

Also update the CORS middleware in `server/app/main.py` to handle the wildcard properly (when using `"*"`, `allow_credentials` must be `False`, or we switch to a dynamic origin callback).

### A3: Vite Dev Server — Listen on All Interfaces

**File:** `client/vite.config.js`

Add `host: true` to the Vite server config so the frontend dev server is accessible from LAN IPs.

```js
server: {
    host: true,  // Listen on 0.0.0.0 (LAN accessible)
    port: 5173,
    proxy: { ... }
}
```

### A4: Create `start-playtest.bat`

A dedicated launcher that starts everything and prints the host machine's LAN IP so you can share it with friends.

- Starts backend with `--host 0.0.0.0`
- Starts frontend with `--host`
- Prints `Your friends can connect at: http://<LAN_IP>:5173`

### A5: Verification

- [ ] Start game on host machine via `start-playtest.bat`
- [ ] Open `http://<HOST_LAN_IP>:5173` on a second device on the same WiFi
- [ ] Both players can create/join a match and play together
- [ ] WebSocket connects and game state syncs in real time

### Tests

No new automated tests needed — this is infrastructure config only.

---

## Phase B — Electron Server URL Configuration

**Objective:** The packaged Electron client can connect to any server IP, not just localhost. This is the critical unlock for "download the client and connect."

### B1: Server URL Configuration System

**File:** `client/electron/main.cjs`, `client/electron/preload.cjs`

Add a mechanism for the Electron client to know where the server is. Two options (implement both, with fallback):

1. **Config file:** `server-config.json` alongside the .exe — the simplest for playtesting
2. **In-app setting:** A server URL input on the login/lobby screen

The config file approach:
```json
// server-config.json (lives next to the .exe or in userData)
{
  "serverUrl": "http://192.168.1.100:8000"
}
```

Electron main process reads this on startup and injects it into the renderer via the preload bridge.

### B2: Preload Bridge — Expose Server URL

**File:** `client/electron/preload.cjs`

Expose the server URL to the renderer so the React app can use it:

```js
contextBridge.exposeInMainWorld('electronAPI', {
    isElectron: true,
    platform: process.platform,
    version: require('../package.json').version,
    quitApp: () => ipcRenderer.send('quit-app'),
    // NEW
    serverUrl: null,  // Populated by main process via IPC
});
```

Use IPC to send the resolved server URL from main → renderer after loading config.

### B3: API Base URL Helper

**File:** New file `client/src/utils/serverUrl.js`

Create a utility that returns the correct base URL for API calls:

```js
/**
 * Returns the base URL for API and WebSocket connections.
 * - In browser (Vite dev): empty string (uses relative paths via proxy)
 * - In Electron prod: reads from electronAPI.serverUrl
 */
export function getApiBaseUrl() {
    if (window.electronAPI?.serverUrl) {
        return window.electronAPI.serverUrl;  // e.g. "http://192.168.1.100:8000"
    }
    return '';  // Vite proxy handles it
}

export function getWsBaseUrl() {
    if (window.electronAPI?.serverUrl) {
        const url = new URL(window.electronAPI.serverUrl);
        const protocol = url.protocol === 'https:' ? 'wss' : 'ws';
        return `${protocol}://${url.host}`;
    }
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}`;
}
```

### B4: Update All fetch() Calls

**Files:** `useWebSocket.js`, `App.jsx`, `Lobby.jsx`, `WaitingRoom.jsx`, `fetchWithRetry.js`, `Bank.jsx`, `HeroDetailPanel.jsx`, plus any other files using `fetch('/api/...')`

Prepend `getApiBaseUrl()` to all API calls:

```js
// Before
fetch('/api/lobby/create', { ... })

// After
fetch(`${getApiBaseUrl()}/api/lobby/create`, { ... })
```

For the WebSocket hook:
```js
// Before
const url = `${protocol}://${window.location.host}/ws/${matchId}/${playerId}`;

// After
import { getWsBaseUrl } from '../utils/serverUrl';
const url = `${getWsBaseUrl()}/ws/${matchId}/${playerId}`;
```

Also update `fetchWithRetry.js` so all calls routed through it automatically get the base URL.

### B5: Server URL Input Screen (In-App Fallback)

**File:** New component or addition to Lobby screen

If no `server-config.json` is found, show a simple "Server Address" input field on the lobby screen (Electron mode only). Save the last-used address to localStorage or electron-store.

This lets friends type in the IP you give them without editing config files.

### B6: CORS — Allow Electron Origin

**File:** `server/app/main.py`

When the Electron app makes requests, the origin will be `null` (from `file://` protocol) or the server URL itself. Ensure CORS handles this:

- In development/playtest: use the wildcard from Phase A2
- In production: add specific origin handling for `null` (Electron file:// origin)

### B7: Verification

- [ ] Build the Electron app: `npm run electron:build`
- [ ] Copy the installer to another machine
- [ ] Install, set server URL to host machine's IP
- [ ] Launch — client connects to host server
- [ ] Create match, join match, play a full game
- [ ] WebSocket, all API calls, asset loading all work

### Tests

- Unit test for `getApiBaseUrl()` and `getWsBaseUrl()` with mocked `window.electronAPI`

---

## Phase C — Packaged Client Build & Distribution

**Objective:** Produce a clean, distributable installer that friends can download and run.

### C1: App Metadata & Branding

**File:** `client/package.json` (build section)

Review and finalize:
- App name, version, description
- Icon (currently `favicon.ico` — consider a proper `.ico` with multiple sizes)
- NSIS installer options (one-click vs custom, desktop shortcut, start menu)

### C2: Build Pipeline Verification

Run the full build and verify the output:

```bash
cd client
npm run electron:build
```

Verify:
- [ ] NSIS installer created in `build/electron/`
- [ ] Portable .exe also created
- [ ] Installer runs on a clean Windows machine
- [ ] App launches and shows the lobby screen
- [ ] Server connection works with `server-config.json`

### C3: Distribution Method

For early playtesting, choose one:

| Method | Pros | Cons |
|--------|------|------|
| **Google Drive / Dropbox link** | Zero setup, free | Manual re-download for updates |
| **GitHub Releases** | Version history, enables auto-updater later | Repo must be accessible to friends |
| **Discord file share** | Friends are probably already there | 25MB limit (may need to split or Nitro) |

**Recommendation:** GitHub Releases — it's free, has version history, and is the foundation for Phase E auto-updates. The repo can be private with friends added as collaborators, or use release asset links.

### C4: Server Hosting for Remote Play

If friends are not on LAN, the Python backend needs to be reachable. Options:

| Method | Cost | Setup | Notes |
|--------|------|-------|-------|
| **Tailscale** | Free | 15 min/person | Virtual LAN — everyone installs Tailscale, connect via Tailscale IP |
| **VPS** | $5/mo | 30 min | DigitalOcean/Hetzner, run uvicorn on a public IP |
| **Port forward** | Free | 10 min | Expose your router port — dnyamic DNS recommended |
| **ngrok** | Free tier | 5 min | Temporary public URL, good for quick sessions |

**Recommendation for early playtest:** Tailscale. Zero cost, encrypted, no port forwarding, and once Phase B is done, friends just enter your Tailscale IP.

### C5: Verification

- [ ] Friend downloads and installs from chosen distribution method
- [ ] Connects to server (LAN or Tailscale)
- [ ] Full game session works end to end

---

## Phase D — Quality of Life for Playtesting

**Objective:** Smooth out the playtest experience with small polish items.

### D1: Connection Status Indicator

**File:** Lobby or HUD component

Show a clear visual for:
- "Connecting to server..."
- "Connected" (green dot)
- "Disconnected — retrying..." (with auto-reconnect)
- "Server unreachable" (with option to change server URL)

### D2: Auto-Reconnect on Disconnect

**File:** `client/src/hooks/useWebSocket.js`

If the WebSocket drops mid-match, auto-reconnect with exponential backoff instead of requiring a page refresh.

### D3: Server Status Endpoint

**File:** `server/app/routes/` (new or existing)

Add a simple `GET /api/status` endpoint that returns:
```json
{
  "status": "online",
  "version": "0.1.0",
  "players_online": 3,
  "active_matches": 1
}
```

The client can ping this on launch to verify connectivity before entering the lobby.

### D4: Playtest Feedback Collection

Consider adding a simple in-game feedback button (Escape menu) that logs feedback to a file or Discord webhook. Low priority but useful.

### D5: Verification

- [ ] Connection indicator clearly shows state
- [ ] Disconnecting WiFi briefly → auto-reconnects
- [ ] `/api/status` returns valid data

---

## Phase E — Auto-Updater

**Objective:** Friends get game updates automatically when they launch the app.

### E1: Install electron-updater

```bash
cd client
npm install electron-updater
```

### E2: Configure Update Source

**File:** `client/package.json` (build section)

Add publish config pointing to GitHub Releases:

```json
"build": {
    "publish": {
        "provider": "github",
        "owner": "your-github-username",
        "repo": "arena"
    }
}
```

### E3: Update Check in Main Process

**File:** `client/electron/main.cjs`

```js
const { autoUpdater } = require('electron-updater');

app.on('ready', () => {
    createWindow();
    // Check for updates after window is ready
    autoUpdater.checkForUpdatesAndNotify();
});

autoUpdater.on('update-available', () => {
    // Notify renderer: "Update available, downloading..."
});

autoUpdater.on('update-downloaded', () => {
    // Notify renderer: "Update ready — restart to apply"
    // Or auto-restart: autoUpdater.quitAndInstall();
});
```

### E4: Update UI in Renderer

Show a non-intrusive notification:
- "Checking for updates..."
- "Downloading update (v0.2.0)..."
- "Update ready — click to restart" / auto-restart

### E5: Release Workflow

When you want to push an update:
1. Bump version in `package.json`
2. `npm run electron:build`
3. Push the build artifacts to GitHub Releases (or configure CI to do it)
4. Friends launch the app → auto-updater detects new version → downloads → installs

### E6: Verification

- [ ] Build v0.1.0, distribute to friend
- [ ] Bump to v0.2.0, publish release
- [ ] Friend launches app → gets notified of update
- [ ] Update installs and app restarts on new version

---

## Implementation Order

```
Phase A ──→ Phase B ──→ Phase C ──→ Phase D ──→ Phase E
(LAN)      (Electron)   (Distribute)  (Polish)   (Auto-update)
 ~1hr       ~3hr         ~1hr          ~2hr        ~3hr
```

**Minimum viable playtest:** Phase A only (browser-based LAN play, no install needed).

**Full vision (download → install → connect → auto-update):** All five phases.

---

## File Change Summary

| Phase | Files Modified | Files Created |
|-------|---------------|---------------|
| A | `start-backend.bat`, `start-game.bat`, `server/app/config.py`, `server/app/main.py`, `client/vite.config.js` | `start-playtest.bat` |
| B | `client/electron/main.cjs`, `client/electron/preload.cjs`, `client/src/hooks/useWebSocket.js`, `client/src/App.jsx`, `client/src/components/Lobby/Lobby.jsx`, `client/src/components/WaitingRoom/WaitingRoom.jsx`, `client/src/utils/fetchWithRetry.js`, `client/src/components/TownHub/Bank.jsx`, `client/src/components/TownHub/HeroDetailPanel.jsx` | `client/src/utils/serverUrl.js` |
| C | `client/package.json` (metadata) | — |
| D | `client/src/hooks/useWebSocket.js`, lobby/HUD components | Server status route |
| E | `client/package.json`, `client/electron/main.cjs` | Update UI component |
