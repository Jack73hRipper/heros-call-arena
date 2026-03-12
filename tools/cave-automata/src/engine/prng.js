// ─────────────────────────────────────────────────────────
// prng.js — Seeded pseudo-random number generator
//
// Uses mulberry32 algorithm for deterministic generation.
// Same implementation as the WFC Dungeon Lab for consistency.
// ─────────────────────────────────────────────────────────

/**
 * Create a seeded PRNG using the mulberry32 algorithm.
 * @param {number} seed - Integer seed value
 * @returns {function} Function that returns a random float in [0, 1)
 */
export function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Generate a random integer seed from current time + entropy.
 * @returns {number}
 */
export function randomSeed() {
  return (Math.random() * 2147483647) | 0;
}
