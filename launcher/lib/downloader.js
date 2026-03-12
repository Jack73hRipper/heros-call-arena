/**
 * Downloader — Hero's Call Arena Launcher
 *
 * Streams a file download with progress callbacks.
 * Writes to a temp file, supports cancellation.
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

/** Active abort controller — allows cancellation */
let activeAbortController = null;

/**
 * Download a file from a URL to a temporary location.
 *
 * @param {string} url            — Remote file URL
 * @param {Object} opts
 * @param {number} opts.expectedSize — Expected total bytes (for progress)
 * @param {Function} opts.onProgress — (received, total) => void
 * @returns {Promise<string>}     — Path to the downloaded temp file
 */
function download(url, { expectedSize = 0, onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const tempPath = path.join(os.tmpdir(), `arena-update-${Date.now()}.zip`);
    const file = fs.createWriteStream(tempPath);

    activeAbortController = new AbortController();
    const { signal } = activeAbortController;

    // Listen for cancellation
    signal.addEventListener('abort', () => {
      file.close();
      cleanupTempFile(tempPath);
      reject(new Error('Download cancelled'));
    }, { once: true });

    const client = url.startsWith('https') ? https : http;

    const req = client.get(url, { timeout: 30000 }, (res) => {
      // Follow redirects (301, 302, 307, 308)
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close();
        cleanupTempFile(tempPath);
        return resolve(download(res.headers.location, { expectedSize, onProgress }));
      }

      if (res.statusCode < 200 || res.statusCode >= 300) {
        file.close();
        cleanupTempFile(tempPath);
        return reject(new Error(`Download failed: HTTP ${res.statusCode}`));
      }

      const totalBytes = parseInt(res.headers['content-length'], 10) || expectedSize;
      let receivedBytes = 0;

      res.on('data', (chunk) => {
        if (signal.aborted) return;
        receivedBytes += chunk.length;
        if (onProgress) {
          onProgress(receivedBytes, totalBytes);
        }
      });

      res.pipe(file);

      file.on('finish', () => {
        file.close(() => {
          activeAbortController = null;
          resolve(tempPath);
        });
      });

      file.on('error', (err) => {
        file.close();
        cleanupTempFile(tempPath);
        activeAbortController = null;
        reject(err);
      });
    });

    req.on('error', (err) => {
      file.close();
      cleanupTempFile(tempPath);
      activeAbortController = null;
      if (signal.aborted) return; // already rejected
      reject(err);
    });

    req.on('timeout', () => {
      req.destroy();
      file.close();
      cleanupTempFile(tempPath);
      activeAbortController = null;
      reject(new Error('Download timed out'));
    });
  });
}

/**
 * Cancel the active download, if any.
 */
function cancel() {
  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
  }
}

/**
 * Check whether a download is in progress.
 */
function isDownloading() {
  return activeAbortController !== null;
}

/** Silently remove a temp file */
function cleanupTempFile(filePath) {
  try { fs.unlinkSync(filePath); } catch { /* ignored */ }
}

module.exports = {
  download,
  cancel,
  isDownloading,
};
