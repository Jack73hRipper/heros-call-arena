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
 * @param {function} opts.onProgress — Progress callback (extracted, total)
 * @returns {Promise<void>}
 */
async function extract(zipPath, installDir, { isUpdate = false, onProgress } = {}) {
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
        extractWithProgress(zip, stagingDir, onProgress);

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
      extractWithProgress(zip, installDir, onProgress);
    }
  } finally {
    process.noAsar = prevNoAsar;
  }
}

/**
 * Extract zip entries one at a time, calling onProgress after each.
 */
function extractWithProgress(zip, targetDir, onProgress) {
  const entries = zip.getEntries();
  const total = entries.length;
  let extracted = 0;

  fs.mkdirSync(targetDir, { recursive: true });

  for (const entry of entries) {
    zip.extractEntryTo(entry, targetDir, true, true);
    extracted++;
    if (onProgress) onProgress(extracted, total);
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
