/**
 * Preload Script — Hero's Call Arena Launcher
 *
 * Exposes a safe IPC bridge to the renderer process.
 * Phase L4: download, install, launch, and progress channels.
 * Phase L6: launcher self-update channels.
 * Phase L7: settings, repair, logging.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('launcherAPI', {
  /* ── Window chrome controls ── */
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  closeWindow:    () => ipcRenderer.send('window-close'),

  /* ── Phase L3: version checking ── */
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),

  /* ── Phase L4: download / install / launch ── */
  startInstall:   (manifest) => ipcRenderer.invoke('start-install', manifest),
  cancelInstall:  ()         => ipcRenderer.invoke('cancel-install'),
  launchGame:     ()         => ipcRenderer.invoke('launch-game'),
  isGameRunning:  ()         => ipcRenderer.invoke('is-game-running'),

  /* ── Phase L4: event listeners from main process ── */
  onDownloadProgress: (callback) => {
    ipcRenderer.on('download-progress', (_e, data) => callback(data));
  },
  onInstallStatus: (callback) => {
    ipcRenderer.on('install-status', (_e, status) => callback(status));
  },
  onGameExited: (callback) => {
    ipcRenderer.on('game-exited', (_e, code) => callback(code));
  },

  /* ── Phase L6: launcher self-update ── */
  onLauncherUpdateStatus: (callback) => {
    ipcRenderer.on('launcher-update-status', (_e, data) => callback(data));
  },
  installLauncherUpdate: () => ipcRenderer.invoke('install-launcher-update'),

  /* ── Phase L7: settings, repair, logging ── */
  getSettings:    ()        => ipcRenderer.invoke('get-settings'),
  saveSettings:   (updates) => ipcRenderer.invoke('save-settings', updates),
  browseInstallDir: ()      => ipcRenderer.invoke('browse-install-dir'),
  repairGame:     ()        => ipcRenderer.invoke('repair-game'),
  getLogPath:     ()        => ipcRenderer.invoke('get-log-path'),
});
