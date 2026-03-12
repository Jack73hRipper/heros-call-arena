/**
 * Electron Main Process — Hero's Call Arena Launcher
 *
 * Creates a 900×600 frameless window with custom title bar chrome.
 * Phase L4: download, verify, extract, and launch game.
 * Phase L6: launcher self-update via electron-updater.
 * Phase L7: polish & hardening — settings, tray, logging, repair, window persistence.
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, dialog, Notification, nativeImage } = require('electron');
const path = require('path');
const { execSync } = require('child_process');
const fs = require('fs');
const { autoUpdater } = require('electron-updater');

const versionChecker = require('./lib/version-checker');
const downloader = require('./lib/downloader');
const verifier = require('./lib/verifier');
const extractor = require('./lib/extractor');
const gameLauncher = require('./lib/game-launcher');
const logger = require('./lib/logger');
const settings = require('./lib/settings');

let mainWindow = null;
let tray = null;

/* ── Manifest URL configuration ── */
// For local testing, serve latest.json via a simple HTTP server.
// For production, replace with your CDN / R2 / B2 / GitHub URL.
const MANIFEST_URL = process.env.LAUNCHER_MANIFEST_URL
  || 'http://localhost:8088/latest.json';

versionChecker.setManifestUrl(MANIFEST_URL);

logger.info('Launcher starting');
logger.info(`Manifest URL: ${MANIFEST_URL}`);

function createWindow() {
  const savedBounds = settings.get('windowBounds');

  mainWindow = new BrowserWindow({
    width: savedBounds ? savedBounds.width : 900,
    height: savedBounds ? savedBounds.height : 600,
    x: savedBounds ? savedBounds.x : undefined,
    y: savedBounds ? savedBounds.y : undefined,
    minWidth: 900,
    minHeight: 600,
    resizable: false,
    frame: false,              // Custom title bar
    transparent: false,
    title: "Hero's Call Arena Launcher",
    backgroundColor: '#06060b',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  /* Save window position on move/resize */
  const saveBounds = () => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isMinimized()) {
      settings.set({ windowBounds: mainWindow.getBounds() });
    }
  };
  mainWindow.on('moved', saveBounds);
  mainWindow.on('resized', saveBounds);

  /* Minimize to tray instead of taskbar if enabled */
  mainWindow.on('minimize', () => {
    if (settings.get('minimizeToTray') && tray) {
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/* ── IPC handlers for custom window chrome ── */
ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

/* ── IPC handler: version check (Phase L3) ── */
ipcMain.handle('check-for-updates', async () => {
  logger.info('Checking for game updates…');
  const result = await versionChecker.checkForUpdates();
  logger.info(`Update check result: ${result.state}`);
  return result;
});

/* ── IPC handlers: settings (Phase L7) ── */

ipcMain.handle('get-settings', () => {
  return settings.load();
});

ipcMain.handle('save-settings', (_event, updates) => {
  const saved = settings.set(updates);
  logger.info(`Settings updated: ${JSON.stringify(updates)}`);
  return saved;
});

ipcMain.handle('browse-install-dir', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Choose Install Location',
    properties: ['openDirectory'],
    defaultPath: settings.get('installDir'),
  });
  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});

/** Repair game — delete installed files and re-trigger install */
ipcMain.handle('repair-game', async () => {
  logger.info('Repair requested — removing installed game');
  const installDir = getInstallDir();
  try {
    if (fs.existsSync(installDir)) {
      fs.rmSync(installDir, { recursive: true, force: true });
    }
    // Clear installed.json so the launcher sees "not-installed"
    const installedJson = versionChecker.INSTALLED_JSON;
    if (fs.existsSync(installedJson)) {
      fs.unlinkSync(installedJson);
    }
    logger.info('Repair cleanup complete');
    return { success: true };
  } catch (err) {
    logger.error(`Repair failed: ${err.message}`);
    return { success: false, error: err.message };
  }
});

/** Get the log file path for the renderer to display */
ipcMain.handle('get-log-path', () => {
  return logger.LOG_PATH;
});

/* ── IPC handlers: download, verify, extract, launch (Phase L4) ── */

/**
 * Start downloading + installing the game.
 * Sends progress events back to the renderer.
 */
ipcMain.handle('start-install', async (_event, manifest) => {
  const installDir = getInstallDir();
  const isUpdate = versionChecker.isGameInstalled();
  logger.info(`Starting ${isUpdate ? 'update' : 'install'} — v${manifest.version} to ${installDir}`);

  try {
    /* 1 — Check disk space (rough check: need ~2x download for zip + extract) */
    const requiredBytes = (manifest.downloadSize || 500_000_000) * 2;
    const freeBytes = getDiskFreeSpace(installDir);
    if (freeBytes !== null && freeBytes < requiredBytes) {
      const requiredMB = Math.ceil(requiredBytes / 1_000_000);
      const freeMB = Math.ceil(freeBytes / 1_000_000);
      const errMsg = `Not enough disk space. Need ~${requiredMB} MB, only ${freeMB} MB free.`;
      logger.error(errMsg);
      return { success: false, error: errMsg };
    }

    /* 2 — Download */
    sendToRenderer('install-status', 'downloading');
    logger.info(`Downloading from ${manifest.downloadUrl}`);
    const zipPath = await downloader.download(manifest.downloadUrl, {
      expectedSize: manifest.downloadSize,
      onProgress: (received, total) => {
        sendToRenderer('download-progress', { received, total });
      },
    });
    logger.info(`Download complete: ${zipPath}`);

    /* 3 — Verify */
    sendToRenderer('install-status', 'verifying');
    if (manifest.sha256) {
      logger.info('Verifying SHA-256…');
      const result = await verifier.verify(zipPath, manifest.sha256);
      if (!result.valid) {
        extractor.cleanupZip(zipPath);
        const errMsg = 'Download verification failed — file may be corrupted. Please try again.';
        logger.error(errMsg);
        return { success: false, error: errMsg };
      }
      logger.info('Verification passed');
    }

    /* 4 — Extract */
    sendToRenderer('install-status', 'installing');
    logger.info('Extracting…');
    await extractor.extract(zipPath, installDir, { isUpdate });
    extractor.cleanupZip(zipPath);
    logger.info('Extraction complete');

    /* 5 — Write installed.json */
    versionChecker.writeInstalled({
      version: manifest.version,
      installedDate: new Date().toISOString().slice(0, 10),
      installPath: installDir,
    });
    logger.info(`Install complete — v${manifest.version}`);

    sendToRenderer('install-status', 'ready');
    return { success: true };

  } catch (err) {
    logger.error(`Install failed: ${err.message}`);
    sendToRenderer('install-status', 'error');
    return { success: false, error: err.message };
  }
});

/** Cancel an in-progress download. */
ipcMain.handle('cancel-install', async () => {
  downloader.cancel();
  return { cancelled: true };
});

/** Launch the game executable. */
ipcMain.handle('launch-game', async () => {
  if (gameLauncher.isRunning()) {
    return { success: false, error: 'Game is already running' };
  }

  const installDir = getInstallDir();
  logger.info(`Launching game from ${installDir}`);
  const result = gameLauncher.launch(installDir, {
    onExit: (code) => {
      logger.info(`Game exited with code ${code}`);
      sendToRenderer('game-exited', code);
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    },
  });

  if (result.success) {
    logger.info('Game launched successfully');
    // Minimize or hide to tray based on settings
    if (mainWindow) {
      if (settings.get('minimizeToTray') && tray) {
        mainWindow.hide();
      } else {
        mainWindow.minimize();
      }
    }
  } else {
    logger.error(`Game launch failed: ${result.error}`);
  }

  return result;
});

/** Check if game is currently running. */
ipcMain.handle('is-game-running', async () => {
  return gameLauncher.isRunning();
});

/* ── Helper: send event to renderer ── */
function sendToRenderer(channel, data) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, data);
  }
}

/* ── Helper: get install dir respecting settings ── */
function getInstallDir() {
  return settings.get('installDir') || versionChecker.getInstallDir();
}

/* ── Helper: get free disk space on the drive containing a path ── */
function getDiskFreeSpace(targetPath) {
  try {
    const drive = path.parse(targetPath).root || 'C:\\';
    // Use wmic on Windows
    const output = execSync(
      `wmic logicaldisk where "DeviceID='${drive.replace('\\', '')}'" get FreeSpace /value`,
      { encoding: 'utf-8', timeout: 5000 }
    );
    const match = output.match(/FreeSpace=(\d+)/);
    return match ? parseInt(match[1], 10) : null;
  } catch {
    return null; // Non-fatal — skip disk check
  }
}

/* ── Phase L6: Launcher Self-Update via electron-updater ── */

// Auto-download launcher updates in the background and install on quit
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = true;

// Suppress default console logging — we relay status to the renderer
autoUpdater.logger = null;

autoUpdater.on('checking-for-update', () => {
  logger.info('Checking for launcher updates…');
  sendToRenderer('launcher-update-status', { status: 'checking' });
});

autoUpdater.on('update-available', (info) => {
  logger.info(`Launcher update available: v${info.version}`);
  sendToRenderer('launcher-update-status', {
    status: 'available',
    version: info.version,
  });
});

autoUpdater.on('update-not-available', () => {
  logger.info('Launcher is up to date');
  sendToRenderer('launcher-update-status', { status: 'up-to-date' });
});

autoUpdater.on('download-progress', (progress) => {
  sendToRenderer('launcher-update-status', {
    status: 'downloading',
    percent: Math.round(progress.percent),
  });
});

autoUpdater.on('update-downloaded', (info) => {
  logger.info(`Launcher update downloaded: v${info.version}`);
  sendToRenderer('launcher-update-status', {
    status: 'downloaded',
    version: info.version,
  });
  // Show tray notification if window is hidden
  if (tray && mainWindow && !mainWindow.isVisible() && Notification.isSupported()) {
    new Notification({
      title: "Hero's Call Arena",
      body: `Launcher v${info.version} ready — restart to apply`,
    }).show();
  }
});

autoUpdater.on('error', (err) => {
  logger.warn(`Launcher update error: ${err.message}`);
  // Non-fatal — launcher update failure should not block game usage
  sendToRenderer('launcher-update-status', {
    status: 'error',
    message: err.message,
  });
});

/** IPC: manually trigger install-and-restart for a downloaded launcher update */
ipcMain.handle('install-launcher-update', () => {
  autoUpdater.quitAndInstall(false, true);
});

/** Check for launcher self-updates (called after window is ready) */
function checkForLauncherUpdate() {
  // Only check in production (packaged) builds — skip in dev
  if (!app.isPackaged) {
    sendToRenderer('launcher-update-status', { status: 'dev-mode' });
    return;
  }
  autoUpdater.checkForUpdates().catch(() => {
    // Silently ignore — network issues shouldn't block the launcher
  });
}

/* ── System tray ── */
function createTray() {
  // Create a simple 16x16 ember-colored icon programmatically
  const icon = nativeImage.createFromBuffer(
    Buffer.alloc(16 * 16 * 4, 0), { width: 16, height: 16 }
  );
  // Try to load a real icon if it exists
  const iconPath = path.join(__dirname, 'assets', 'icon.ico');
  let trayIcon = icon;
  try {
    if (fs.existsSync(iconPath)) {
      trayIcon = nativeImage.createFromPath(iconPath);
    }
  } catch { /* use fallback */ }

  tray = new Tray(trayIcon);
  tray.setToolTip("Hero's Call Arena Launcher");

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show Launcher', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } } },
    { type: 'separator' },
    { label: 'Quit', click: () => { app.quit(); } },
  ]);
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
  });
}

/* ── App lifecycle ── */
app.whenReady().then(() => {
  createWindow();
  createTray();
  // Check for launcher self-update first, then renderer handles game update check
  checkForLauncherUpdate();
  logger.info('Launcher ready');
});

app.on('window-all-closed', () => {
  // If minimize-to-tray is enabled, don't quit when window closes
  if (!settings.get('minimizeToTray')) {
    app.quit();
  }
});

app.on('before-quit', () => {
  logger.info('Launcher shutting down');
  if (tray) {
    tray.destroy();
    tray = null;
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
