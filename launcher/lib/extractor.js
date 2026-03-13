/**
 * Extractor — Hero's Call Arena Launcher
 *
 * Extracts a downloaded zip to the game install directory.
 * For updates: extracts to a temp dir first, then swaps (atomic-ish replace).
 * Cleans up temp files on success.
 */

const AdmZip = require('adm-zip');
const fs = require('fs');
const path = require('path');

/**
 * Extract a zip file to a target directory.
 *
 * For fresh installs, extracts directly to installDir.
 * For updates, extracts to a staging dir, removes old install, renames staging.
 *
 * @param {string} zipPath    — Path to the downloaded zip file
 * @param {string} installDir — Target installation directory
 * @param {Object} opts
 * @param {boolean} opts.isUpdate — Whether this is an update (atomic swap)
 * @returns {Promise<void>}
 */
async function extract(zipPath, installDir, { isUpdate = false } = {}) {
  const parentDir = path.dirname(installDir);
  fs.mkdirSync(parentDir, { recursive: true });

  // Disable Electron's ASAR interception so adm-zip can extract
  // files with ".asar" in the path (e.g. resources/app.asar) as
  // real files instead of virtual archives.
  const prevNoAsar = process.noAsar;
  process.noAsar = true;

  try {
    if (isUpdate) {
      // Atomic-ish update: extract to staging dir, then swap
      const stagingDir = installDir + '-staging-' + Date.now();

      try {
        // Extract to staging
        const zip = new AdmZip(zipPath);
        zip.extractAllTo(stagingDir, true);

        // Remove old install
        const backupDir = installDir + '-old-' + Date.now();
        if (fs.existsSync(installDir)) {
          fs.renameSync(installDir, backupDir);
        }

        // Promote staging to install dir
        fs.renameSync(stagingDir, installDir);

        // Clean up backup
        removeDir(backupDir);
      } catch (err) {
        // Clean up staging on failure
        removeDir(stagingDir);
        throw err;
      }
    } else {
      // Fresh install: extract directly
      if (fs.existsSync(installDir)) {
        removeDir(installDir);
      }
      const zip = new AdmZip(zipPath);
      zip.extractAllTo(installDir, true);
    }
  } finally {
    process.noAsar = prevNoAsar;
  }
}

/**
 * Recursively remove a directory (sync).
 * Safe no-op if the path doesn't exist.
 */
function removeDir(dirPath) {
  try {
    if (fs.existsSync(dirPath)) {
      fs.rmSync(dirPath, { recursive: true, force: true });
    }
  } catch { /* best effort */ }
}

/**
 * Clean up a temp zip file after successful install.
 */
function cleanupZip(zipPath) {
  try { fs.unlinkSync(zipPath); } catch { /* ignored */ }
}

module.exports = {
  extract,
  cleanupZip,
};
