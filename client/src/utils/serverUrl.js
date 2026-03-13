/**
 * serverUrl — resolves the game server base URL.
 *
 * Priority:
 *   1. Cached value (already fetched this session)
 *   2. Remote server-url.json from GitHub Pages (online mode)
 *   3. Fallback to local server (localhost:8000)
 *
 * In dev mode (Vite dev server), returns '' so relative URLs
 * go through the Vite proxy as usual.
 */

const SERVER_URL_ENDPOINT =
  'https://jack73hripper.github.io/heros-call-arena/server-url.json';

const LOCAL_FALLBACK = 'http://localhost:8000';

let cachedServerUrl = null;
let fetchPromise = null;

/**
 * Returns the server base URL (e.g. 'https://xxx.trycloudflare.com').
 * In dev mode returns '' (empty string) so relative paths use the Vite proxy.
 */
export async function getServerUrl() {
  // Dev mode — Vite proxy handles everything via relative paths
  if (import.meta.env.DEV) return '';

  // Already resolved
  if (cachedServerUrl !== null) return cachedServerUrl;

  // Deduplicate concurrent calls
  if (fetchPromise) return fetchPromise;

  fetchPromise = resolveServerUrl();
  cachedServerUrl = await fetchPromise;
  fetchPromise = null;
  return cachedServerUrl;
}

async function resolveServerUrl() {
  try {
    const res = await fetch(SERVER_URL_ENDPOINT, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.url && data.status === 'online') {
      console.log(`[Server] Remote server: ${data.url}`);
      // Verify the remote server is actually reachable
      const health = await fetch(`${data.url}/health`, { signal: AbortSignal.timeout(5000) });
      if (health.ok) return data.url;
      console.warn('[Server] Remote server unreachable, falling back to local');
    }
  } catch (err) {
    console.warn('[Server] Could not fetch server URL, using local fallback:', err.message);
  }
  return LOCAL_FALLBACK;
}

/**
 * Fetch wrapper that auto-prepends the server base URL.
 * Drop-in replacement for fetch() when calling /api/... endpoints.
 */
export async function apiFetch(path, opts) {
  const base = await getServerUrl();
  return fetch(base + path, opts);
}

/**
 * Returns the WebSocket base URL for the resolved server.
 * Converts http(s) to ws(s).
 */
export async function getWsUrl() {
  const base = await getServerUrl();
  if (!base) {
    // Dev mode — use relative path through Vite proxy
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}`;
  }
  return base.replace(/^http/, 'ws');
}
