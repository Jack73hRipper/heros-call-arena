# Electron Desktop App — Hero's Call Arena

> Added: February 2026  
> Status: Working — Dev mode tested, build config ready

## Overview

The game can now run as a standalone desktop application using **Electron**, in addition to the existing browser-based mode. Both modes use the same React frontend and Python backend — Electron simply wraps the web client in a native window.

### Distribution Channels

| Channel | How | Status |
|---------|-----|--------|
| **Browser** | `start-game.bat` → opens `http://localhost:5173` | Existing |
| **Electron Desktop** | `start-electron.bat` → native window | New |
| **Packaged .exe** | `npm run electron:build` → installer | Ready to build |

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Electron Main Process (main.cjs)       │
│  - Creates BrowserWindow                │
│  - DEV: loads http://localhost:5173      │
│  - PROD: loads dist/index.html          │
├─────────────────────────────────────────┤
│  Preload Script (preload.cjs)           │
│  - Exposes window.electronAPI           │
│  - isElectron, platform, version        │
├─────────────────────────────────────────┤
│  Renderer (same React app)              │
│  - Identical to browser version         │
│  - Connects to backend via WebSocket    │
└──────────────┬──────────────────────────┘
               │ WS / HTTP
               ▼
┌─────────────────────────────────────────┐
│  Python Backend (FastAPI)               │
│  - Runs separately on port 8000         │
│  - Same as browser mode                 │
└─────────────────────────────────────────┘
```

---

## Quick Start (Development)

### Option A: Use the batch file (recommended)
```
start-electron.bat
```
This starts the backend, Vite dev server, AND launches the Electron window automatically.

### Option B: Manual steps

1. **Start the backend** (terminal 1):
   ```bash
   cd server
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. **Start Vite + Electron** (terminal 2):
   ```bash
   cd client
   npm run electron:dev
   ```
   This uses `concurrently` to start Vite and Electron together. Electron waits for Vite to be ready before opening the window.

3. **Or start them separately** (terminals 2 & 3):
   ```bash
   # Terminal 2
   cd client
   npm run dev

   # Terminal 3 (after Vite is ready)
   cd client
   npx electron .
   ```

---

## NPM Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start Vite dev server only (browser mode) |
| `npm run electron:dev` | Start Vite + Electron together (desktop mode) |
| `npm run electron:build` | Build Vite + package Windows installer (.exe) |
| `npm run electron:build:all` | Build for Windows + Mac + Linux |
| `npm run electron:pack` | Build without creating installer (for testing) |

---

## File Structure

```
client/
├── electron/
│   ├── main.cjs        # Electron main process (window creation, menus, lifecycle)
│   └── preload.cjs     # Preload script (exposes electronAPI to renderer)
├── package.json        # Updated with Electron scripts + build config
├── vite.config.js      # Updated with relative base path for Electron builds
└── src/                # React app (unchanged — works in both browser and Electron)
```

---

## Build & Distribution

### Building a Windows Installer
```bash
cd client
npm run electron:build
```

Output goes to `build/electron/` (at project root):
- **NSIS installer** (.exe) — standard Windows installer with desktop shortcut
- **Portable** (.exe) — single-file, no install needed

### Build Configuration

The `build` section in `package.json` controls packaging:

| Setting | Value |
|---------|-------|
| App ID | `com.heroscall.arena` |
| Product Name | `Hero's Call Arena` |
| Windows targets | NSIS installer + portable .exe |
| Mac target | DMG |
| Linux target | AppImage |
| Output directory | `../build/electron/` |

### Important Note for Production Builds

The packaged Electron app only bundles the **frontend**. The Python backend must be running separately (or bundled via PyInstaller in a future step). For now:
- The user runs the backend server
- The Electron app connects to `localhost:8000`

---

## Electron Features

### Window Configuration
- **Default size**: 1400×900 (min: 1024×720)
- **Background color**: `#0a0a0f` (matches game theme, no white flash)
- **Show on ready**: Window only appears after content loads

### Menu Bar
- **Game** → Reload, Toggle DevTools, Toggle Fullscreen (F11), Quit
- **View** → Zoom In/Out/Reset

### Dev Mode Features
- DevTools open automatically (detached window)
- Hot reload via Vite — changes appear instantly
- All existing browser DevTools work normally

### Security
- Context isolation enabled (renderer can't access Node.js)
- External links open in default browser
- Navigation restricted to dev server / local files only

---

## Detecting Electron in React Code

The preload script exposes `window.electronAPI`:

```jsx
// Check if running in Electron
if (window.electronAPI?.isElectron) {
  console.log('Running in Electron desktop app');
  console.log('Platform:', window.electronAPI.platform);  // 'win32' | 'darwin' | 'linux'
  console.log('Version:', window.electronAPI.version);     // from package.json
}
```

This can be used for platform-specific UI tweaks (e.g., hiding browser-only elements, adding native menu hints).

---

## Future Enhancements

- [ ] **Bundle Python backend** inside Electron using PyInstaller (true single-executable)
- [ ] **Auto-updater** via electron-updater (push updates to users)
- [ ] **App icon** — replace favicon.ico with a proper multi-resolution icon
- [ ] **System tray** — minimize to tray instead of closing
- [ ] **PWA support** — add manifest.json + service worker for browser installability
- [ ] **Code signing** — sign the .exe for Windows SmartScreen trust
