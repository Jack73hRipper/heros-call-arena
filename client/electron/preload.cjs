/**
 * Electron Preload Script — Hero's Call Arena
 * 
 * Runs in a sandboxed context before the renderer page loads.
 * Exposes a safe bridge API to the renderer via contextBridge.
 * 
 * The renderer can check `window.electronAPI` to detect if running in Electron.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose a minimal API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Let the renderer know it's running inside Electron
  isElectron: true,

  // Platform info (useful for UI tweaks)
  platform: process.platform, // 'win32' | 'darwin' | 'linux'

  // App version (from package.json)
  version: require('../package.json').version,

  // Quit the application (used by town hub escape menu)
  quitApp: () => ipcRenderer.send('quit-app'),
});
