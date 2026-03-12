// ─────────────────────────────────────────────────────────
// noiseUtils.js — Deterministic noise & hash utilities
//
// Provides seeded PRNG, per-cell hashing, and color
// manipulation helpers for procedural tile generation.
// All functions are pure — no side effects, no randomness
// beyond the provided seed.
// ─────────────────────────────────────────────────────────

/**
 * Deterministic hash for a grid cell position.
 * Returns a float in [0, 1) that's stable for any (x, y, salt) combo.
 * Used to select tile variants, place details, etc.
 */
export function cellHash(gridX, gridY, salt = 0) {
  let h = ((gridX * 7919) + (gridY * 6271) + (salt * 3571)) | 0;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = (h >> 16) ^ h;
  return ((h & 0x7FFFFFFF) >>> 0) / 0x7FFFFFFF;
}

/**
 * Mulberry32 seeded PRNG. Returns a function that produces
 * deterministic floats in [0, 1) on each call.
 */
export function mulberry32(seed) {
  let s = seed | 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Parse a hex color string to { r, g, b } integers.
 */
export function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

/**
 * Convert { r, g, b } integers to a CSS rgb() string.
 */
export function rgbToCSS(r, g, b, a = 1) {
  if (a < 1) return `rgba(${r}, ${g}, ${b}, ${a})`;
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Vary a hex color by a random amount.
 * @param {string} baseHex - Base color like '#2a1520'
 * @param {number} amount - Max shift per channel (e.g. 15)
 * @param {number} hashVal - A float [0,1) for deterministic variation
 * @returns {string} CSS color string
 */
export function varyColor(baseHex, amount, hashVal) {
  const { r, g, b } = hexToRgb(baseHex);
  const shift = Math.floor((hashVal - 0.5) * 2 * amount);
  const clamp = v => Math.max(0, Math.min(255, v + shift));
  return rgbToCSS(clamp(r), clamp(g), clamp(b));
}

/**
 * Lighten or darken a hex color by a fixed amount.
 * Positive = lighter, negative = darker.
 */
export function shiftColor(baseHex, amount) {
  const { r, g, b } = hexToRgb(baseHex);
  const clamp = v => Math.max(0, Math.min(255, v + amount));
  return rgbToCSS(clamp(r), clamp(g), clamp(b));
}

/**
 * Blend two hex colors. t=0 returns colorA, t=1 returns colorB.
 */
export function lerpColor(hexA, hexB, t) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const mix = (va, vb) => Math.round(va + (vb - va) * t);
  return rgbToCSS(mix(a.r, b.r), mix(a.g, b.g), mix(a.b, b.b));
}

/**
 * Create an RGBA string from a hex color + alpha.
 */
export function hexAlpha(hex, alpha) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
