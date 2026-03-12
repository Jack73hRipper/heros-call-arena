/**
 * Logger — Hero's Call Arena Launcher
 *
 * Writes timestamped log entries to %LOCALAPPDATA%/HeroCallArena/launcher.log.
 * Auto-rotates when log exceeds 2 MB (keeps one backup).
 */

const { app } = require('electron');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(app.getPath('userData'), 'HeroCallArena');
const LOG_PATH = path.join(DATA_DIR, 'launcher.log');
const LOG_BACKUP = path.join(DATA_DIR, 'launcher.log.1');
const MAX_SIZE = 2 * 1024 * 1024; // 2 MB

/** Ensure the data directory exists */
function ensureDir() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

/** Rotate log file if it exceeds MAX_SIZE */
function rotateIfNeeded() {
  try {
    const stats = fs.statSync(LOG_PATH);
    if (stats.size >= MAX_SIZE) {
      if (fs.existsSync(LOG_BACKUP)) fs.unlinkSync(LOG_BACKUP);
      fs.renameSync(LOG_PATH, LOG_BACKUP);
    }
  } catch {
    // File doesn't exist yet — that's fine
  }
}

/**
 * Write a log line.
 * @param {'INFO'|'WARN'|'ERROR'} level
 * @param {string} message
 */
function write(level, message) {
  try {
    ensureDir();
    rotateIfNeeded();
    const timestamp = new Date().toISOString();
    const line = `[${timestamp}] [${level}] ${message}\n`;
    fs.appendFileSync(LOG_PATH, line, 'utf-8');
  } catch {
    // Logging should never crash the launcher
  }
}

const logger = {
  info:  (msg) => write('INFO', msg),
  warn:  (msg) => write('WARN', msg),
  error: (msg) => write('ERROR', msg),
  LOG_PATH,
};

module.exports = logger;
