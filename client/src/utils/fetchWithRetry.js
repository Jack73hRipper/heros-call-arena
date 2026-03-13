/**
 * fetchWithRetry — resilient fetch wrapper for initial API calls.
 * 
 * On cold start the backend may still be booting when the frontend
 * fires its first requests. This utility retries on network errors
 * (ECONNREFUSED etc.) with exponential back-off so the UI gracefully
 * waits instead of silently failing.
 *
 * Usage:
 *   import { fetchWithRetry } from '../utils/fetchWithRetry';
 *   const data = await fetchWithRetry('/api/maps/');
 */

import { getServerUrl } from './serverUrl';

const DEFAULT_RETRIES = 5;
const DEFAULT_BASE_DELAY = 1000; // ms

/**
 * @param {string} url         – fetch URL (relative paths get server base prepended)
 * @param {RequestInit} [opts] – standard fetch options
 * @param {object} [config]
 * @param {number} [config.retries=5]       – max retry attempts
 * @param {number} [config.baseDelay=1000]  – initial delay in ms (doubles each retry)
 * @returns {Promise<Response>}
 */
export async function fetchWithRetry(url, opts = {}, config = {}) {
  const maxRetries = config.retries ?? DEFAULT_RETRIES;
  const baseDelay  = config.baseDelay ?? DEFAULT_BASE_DELAY;

  const base = await getServerUrl();
  const fullUrl = base + url;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(fullUrl, opts);
      return res;
    } catch (err) {
      // Network-level error (ECONNREFUSED, DNS failure, etc.)
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt); // 1s, 2s, 4s, 8s, 16s
        console.warn(
          `[fetchWithRetry] ${fullUrl} attempt ${attempt + 1}/${maxRetries + 1} failed, ` +
          `retrying in ${delay}ms…`,
          err.message,
        );
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        throw err; // exhausted retries — let caller handle it
      }
    }
  }
}
