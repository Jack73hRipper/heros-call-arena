/**
 * Verifier — Hero's Call Arena Launcher
 *
 * SHA-256 integrity check for downloaded files.
 * Compares computed hash against the expected hash from the manifest.
 */

const crypto = require('crypto');
const fs = require('fs');

/**
 * Compute the SHA-256 hash of a file.
 *
 * @param {string} filePath — Absolute path to the file
 * @returns {Promise<string>} — Lowercase hex digest
 */
function hashFile(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath);

    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('end', () => resolve(hash.digest('hex')));
    stream.on('error', reject);
  });
}

/**
 * Verify a downloaded file against an expected SHA-256 hash.
 *
 * @param {string} filePath     — Path to the downloaded file
 * @param {string} expectedHash — Expected SHA-256 hex digest (from manifest)
 * @returns {Promise<Object>}   — { valid: boolean, actual: string, expected: string }
 */
async function verify(filePath, expectedHash) {
  const actual = await hashFile(filePath);
  const expected = expectedHash.toLowerCase();
  return {
    valid: actual === expected,
    actual,
    expected,
  };
}

module.exports = {
  hashFile,
  verify,
};
