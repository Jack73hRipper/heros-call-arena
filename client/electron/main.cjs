/**
 * Electron Main Process — Hero's Call Arena
 * 
 * This is the entry point for the Electron desktop app.
 * In DEV mode:  loads from the Vite dev server (http://localhost:5173)
 * In PROD mode: loads the built static files from client/dist/
 *               AND spawns the bundled arena-server.exe automatically.
 * 
 * See start-electron.bat in the project root to launch everything together.
 */

const { app, BrowserWindow, Menu, shell, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// Detect dev vs production
const isDev = process.env.ELECTRON_DEV === 'true' || !app.isPackaged;

// Default server URLs
const VITE_DEV_URL = process.env.VITE_DEV_URL || 'http://localhost:5173';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

let mainWindow = null;
let serverProcess = null;

// ── Bundled Server Management (PROD mode) ──────────────────

function getServerExePath() {
  // In packaged app, arena-server is next to the app.asar
  const resourcesDir = path.dirname(app.getAppPath());
  return path.join(resourcesDir, 'arena-server', 'arena-server.exe');
}

function startBundledServer() {
  if (isDev) return Promise.resolve(); // DEV: server runs separately

  const exePath = getServerExePath();
  const fs = require('fs');
  if (!fs.existsSync(exePath)) {
    console.error(`[Electron] Bundled server not found at: ${exePath}`);
    return Promise.resolve(); // Fall through — maybe server is running externally
  }

  console.log(`[Electron] Starting bundled server: ${exePath}`);
  serverProcess = spawn(exePath, [], {
    cwd: path.dirname(exePath),
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  serverProcess.stdout.on('data', (data) => {
    console.log(`[Server] ${data.toString().trim()}`);
  });
  serverProcess.stderr.on('data', (data) => {
    console.error(`[Server] ${data.toString().trim()}`);
  });
  serverProcess.on('error', (err) => {
    console.error('[Electron] Failed to start server:', err.message);
    serverProcess = null;
  });
  serverProcess.on('exit', (code) => {
    console.log(`[Electron] Server exited with code ${code}`);
    serverProcess = null;
  });

  // Wait for server to be ready by polling /health
  return waitForServer(BACKEND_URL + '/health', 30000);
}

function waitForServer(url, timeoutMs) {
  const startTime = Date.now();
  return new Promise((resolve, reject) => {
    function poll() {
      if (Date.now() - startTime > timeoutMs) {
        reject(new Error('Server failed to start within timeout'));
        return;
      }
      http.get(url, (res) => {
        if (res.statusCode === 200) {
          console.log('[Electron] Server is ready!');
          resolve();
        } else {
          setTimeout(poll, 500);
        }
      }).on('error', () => {
        setTimeout(poll, 500);
      });
    }
    poll();
  });
}

function stopBundledServer() {
  if (serverProcess) {
    console.log('[Electron] Stopping bundled server...');
    serverProcess.kill();
    serverProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 720,
    title: "Hero's Call — Arena",
    icon: path.join(__dirname, '..', 'public', 'favicon.ico'),
    backgroundColor: '#0a0a0f',
    fullscreen: true,
    show: false, // Don't show until ready to prevent flash
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      // Allow connecting to local backend WebSocket
      webSecurity: true,
    },
  });

  // Show window when content is ready (no white flash)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // Load the app
  if (isDev) {
    console.log(`[Electron] DEV mode — loading from ${VITE_DEV_URL}`);
    mainWindow.loadURL(VITE_DEV_URL);
    // Open DevTools in dev mode (can toggle with Ctrl+Shift+I)
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    console.log('[Electron] PROD mode — loading from dist/');
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  // Open external links in default browser, not in Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  // Clean up on close
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Build the application menu
  buildMenu();
}

function buildMenu() {
  const template = [
    {
      label: 'Game',
      submenu: [
        {
          label: 'Reload',
          accelerator: 'CmdOrCtrl+R',
          click: () => mainWindow?.webContents.reload(),
        },
        {
          label: 'Toggle DevTools',
          accelerator: 'CmdOrCtrl+Shift+I',
          click: () => mainWindow?.webContents.toggleDevTools(),
        },
        { type: 'separator' },
        {
          label: 'Toggle Fullscreen',
          accelerator: 'F11',
          click: () => {
            if (mainWindow) {
              mainWindow.setFullScreen(!mainWindow.isFullScreen());
            }
          },
        },
        { type: 'separator' },
        {
          label: 'Quit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => app.quit(),
        },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Zoom In',
          accelerator: 'CmdOrCtrl+=',
          click: () => {
            const zoom = mainWindow?.webContents.getZoomLevel() ?? 0;
            mainWindow?.webContents.setZoomLevel(zoom + 0.5);
          },
        },
        {
          label: 'Zoom Out',
          accelerator: 'CmdOrCtrl+-',
          click: () => {
            const zoom = mainWindow?.webContents.getZoomLevel() ?? 0;
            mainWindow?.webContents.setZoomLevel(zoom - 0.5);
          },
        },
        {
          label: 'Reset Zoom',
          accelerator: 'CmdOrCtrl+0',
          click: () => mainWindow?.webContents.setZoomLevel(0),
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// ── IPC Handlers ───────────────────────────────────────────

// Quit app when renderer requests it (town hub ESC menu → Quit Game)
ipcMain.on('quit-app', () => {
  app.quit();
});

// ── App lifecycle ──────────────────────────────────────────

app.whenReady().then(async () => {
  // In PROD mode, start the bundled server before creating the window
  try {
    await startBundledServer();
  } catch (err) {
    console.error('[Electron] Server startup failed:', err.message);
    // Continue anyway — user might have server running externally
  }

  createWindow();

  // macOS: re-create window when dock icon clicked and no windows exist
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed (except on macOS)
app.on('window-all-closed', () => {
  stopBundledServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Ensure server is killed on quit
app.on('will-quit', () => {
  stopBundledServer();
});

// Security: prevent new window creation
app.on('web-contents-created', (_, contents) => {
  contents.on('will-navigate', (event, url) => {
    // Allow navigation to dev server and built files only
    if (isDev && url.startsWith(VITE_DEV_URL)) return;
    if (url.startsWith('file://')) return;
    event.preventDefault();
  });
});
