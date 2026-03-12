/**
 * Settings — Hero's Call Arena Launcher
 *
 * Persists user settings to %LOCALAPPDATA%/HeroCallArena/settings.json.
 * Settings: install location, auto-check updates, minimize to tray,
 *           window bounds (position/size persistence).
 */

const { app } = require('electron');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(app.getPath('userData'), 'HeroCallArena');
const SETTINGS_PATH = path.join(DATA_DIR, 'settings.json');

const DEFAULTS = {
  installDir: path.join(DATA_DIR, 'game'),
  autoCheckUpdates: true,
  minimizeToTray: false,
  windowBounds: null, // { x, y, width, height }
};

/** Read settings from disk, merged with defaults. */
function load() {
  try {
    if (!fs.existsSync(SETTINGS_PATH)) return { ...DEFAULTS };
    const raw = fs.readFileSync(SETTINGS_PATH, 'utf-8');
    const saved = JSON.parse(raw);
    return { ...DEFAULTS, ...saved };
  } catch {
    return { ...DEFAULTS };
  }
}

/** Persist settings to disk. */
function save(settings) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(SETTINGS_PATH, JSON.stringify(settings, null, 2), 'utf-8');
}

/** Get a single setting value. */
function get(key) {
  const all = load();
  return key in all ? all[key] : DEFAULTS[key];
}

/** Update one or more settings and persist. */
function set(updates) {
  const current = load();
  const merged = { ...current, ...updates };
  save(merged);
  return merged;
}

module.exports = { load, save, get, set, DEFAULTS, DATA_DIR, SETTINGS_PATH };
