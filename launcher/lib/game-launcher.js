/**
 * GameLauncher — Hero's Call Arena Launcher
 *
 * Spawns the game process (Electron exe) and monitors its exit.
 * The launcher stays open while the game runs.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

/** The running game process, or null */
let gameProcess = null;

/**
 * Possible game executable names to search for, in priority order.
 * electron-builder may produce different names depending on config.
 */
const EXE_CANDIDATES = [
  "Hero's Call Arena.exe",
  'HeroCallArena.exe',
  'arena.exe',
];

/**
 * Find the game executable inside the install directory.
 *
 * @param {string} installDir — Path to the game install directory
 * @returns {string|null}     — Full path to the exe, or null if not found
 */
function findGameExe(installDir) {
  for (const name of EXE_CANDIDATES) {
    const candidate = path.join(installDir, name);
    if (fs.existsSync(candidate)) return candidate;
  }

  // Fallback: look for any .exe in the root of the install dir
  try {
    const entries = fs.readdirSync(installDir);
    const exe = entries.find((e) => e.endsWith('.exe') && !e.startsWith('Uninstall'));
    if (exe) return path.join(installDir, exe);
  } catch { /* ignored */ }

  return null;
}

/**
 * Launch the game.
 *
 * @param {string} installDir — Path to the game install directory
 * @param {Object} opts
 * @param {Function} opts.onExit — Callback when game process exits: (code) => void
 * @returns {{ success: boolean, error?: string }}
 */
function launch(installDir, { onExit } = {}) {
  if (gameProcess) {
    return { success: false, error: 'Game is already running' };
  }

  const exePath = findGameExe(installDir);
  if (!exePath) {
    return { success: false, error: 'Game executable not found. Try reinstalling.' };
  }

  try {
    gameProcess = spawn(exePath, [], {
      cwd: installDir,
      detached: false,
      stdio: 'ignore',
    });

    gameProcess.on('exit', (code) => {
      gameProcess = null;
      if (onExit) onExit(code);
    });

    gameProcess.on('error', (err) => {
      gameProcess = null;
      if (onExit) onExit(-1, err.message);
    });

    return { success: true };
  } catch (err) {
    gameProcess = null;
    return { success: false, error: err.message };
  }
}

/**
 * Check if the game is currently running.
 */
function isRunning() {
  return gameProcess !== null;
}

/**
 * Kill the game process if it's running.
 */
function kill() {
  if (gameProcess) {
    try {
      gameProcess.kill();
    } catch { /* ignored */ }
    gameProcess = null;
  }
}

module.exports = {
  findGameExe,
  launch,
  isRunning,
  kill,
};
