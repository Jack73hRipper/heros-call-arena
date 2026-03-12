/**
 * VersionChecker — Hero's Call Arena Launcher
 *
 * Fetches the remote manifest (latest.json), reads local install state
 * (installed.json), compares versions, and returns an update state.
 *
 * States:
 *   not-installed   — No game found on disk
 *   up-to-date      — Installed version matches latest
 *   update-available — Remote version is newer than local
 *   check-failed    — Could not reach the manifest (offline / error)
 */

const { app } = require('electron');
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

/* ── Paths ── */
const DATA_DIR = path.join(app.getPath('userData'), 'HeroCallArena');
const INSTALLED_JSON = path.join(DATA_DIR, 'installed.json');

/* ── Default manifest URL (override via setManifestUrl) ── */
let manifestUrl = '';

/**
 * Set the remote manifest URL.
 * Accepts http:// (local dev) or https:// (production).
 */
function setManifestUrl(url) {
  manifestUrl = url;
}

/* ── Read local installed.json ── */
function readInstalled() {
  try {
    if (!fs.existsSync(INSTALLED_JSON)) return null;
    const raw = fs.readFileSync(INSTALLED_JSON, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/* ── Write local installed.json ── */
function writeInstalled(data) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(INSTALLED_JSON, JSON.stringify(data, null, 2), 'utf-8');
}

/* ── Fetch remote manifest (follows redirects) ── */
function fetchManifest() {
  return new Promise((resolve, reject) => {
    if (!manifestUrl) {
      return reject(new Error('No manifest URL configured'));
    }

    function doGet(url, redirectsLeft) {
      const client = url.startsWith('https') ? https : http;

      const req = client.get(url, { timeout: 10000 }, (res) => {
        // Follow redirects (301, 302, 307, 308)
        if ([301, 302, 307, 308].includes(res.statusCode) && res.headers.location) {
          if (redirectsLeft <= 0) {
            return reject(new Error('Too many redirects fetching manifest'));
          }
          return doGet(res.headers.location, redirectsLeft - 1);
        }

        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`HTTP ${res.statusCode} fetching manifest`));
        }

        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch (e) {
            reject(new Error('Invalid JSON in manifest'));
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Manifest fetch timed out'));
      });
    }

    doGet(manifestUrl, 5);
  });
}

/**
 * Compare two semver-style version strings.
 * Returns:  1 if a > b,  -1 if a < b,  0 if equal
 */
function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const va = pa[i] || 0;
    const vb = pb[i] || 0;
    if (va > vb) return 1;
    if (va < vb) return -1;
  }
  return 0;
}

/**
 * Check for updates.
 *
 * @returns {Object} result
 *   .state         — 'not-installed' | 'up-to-date' | 'update-available' | 'check-failed'
 *   .installed     — installed.json data (or null)
 *   .latest        — latest.json data (or null)
 *   .error         — error message if check-failed
 */
async function checkForUpdates() {
  const installed = readInstalled();

  let latest = null;
  try {
    latest = await fetchManifest();
  } catch (err) {
    // Can't reach manifest — check-failed
    return {
      state: 'check-failed',
      installed,
      latest: null,
      error: err.message,
    };
  }

  // No local install
  if (!installed || !installed.version) {
    return {
      state: 'not-installed',
      installed: null,
      latest,
      error: null,
    };
  }

  // Compare versions
  const cmp = compareVersions(latest.version, installed.version);
  if (cmp > 0) {
    return {
      state: 'update-available',
      installed,
      latest,
      error: null,
    };
  }

  return {
    state: 'up-to-date',
    installed,
    latest,
    error: null,
  };
}

/**
 * Get the install directory path.
 */
function getInstallDir() {
  return path.join(DATA_DIR, 'game');
}

/**
 * Check whether a game installation exists on disk.
 */
function isGameInstalled() {
  const installed = readInstalled();
  if (!installed || !installed.installPath) return false;
  return fs.existsSync(installed.installPath);
}

module.exports = {
  setManifestUrl,
  readInstalled,
  writeInstalled,
  fetchManifest,
  compareVersions,
  checkForUpdates,
  getInstallDir,
  isGameInstalled,
  get DATA_DIR() { return DATA_DIR; },
  get INSTALLED_JSON() { return INSTALLED_JSON; },
};
