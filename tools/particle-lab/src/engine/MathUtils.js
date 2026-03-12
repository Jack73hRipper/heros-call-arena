// ─────────────────────────────────────────────────────────
// MathUtils.js — Pure math helpers for the particle engine
// Zero dependencies. Portable into client/src/canvas/particles/
// ─────────────────────────────────────────────────────────

/** Linearly interpolate between a and b by factor t (0–1). */
export function lerp(a, b, t) {
  return a + (b - a) * t;
}

/** Random float in [min, max). */
export function randomRange(min, max) {
  return min + Math.random() * (max - min);
}

/** Random integer in [min, max] (inclusive). */
export function randomInt(min, max) {
  return Math.floor(randomRange(min, max + 1));
}

/** Random angle in radians [0, 2π). */
export function randomAngle() {
  return Math.random() * Math.PI * 2;
}

/** Degrees to radians. */
export function degToRad(deg) {
  return (deg * Math.PI) / 180;
}

/** Radians to degrees. */
export function radToDeg(rad) {
  return (rad * 180) / Math.PI;
}

/** Clamp value between min and max. */
export function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

/**
 * Parse a hex color string (#rgb, #rrggbb, #rrggbbaa) into {r, g, b, a} (0–255, a 0–1).
 */
export function hexToRgba(hex) {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  if (h.length === 6) h += 'ff';
  const n = parseInt(h, 16);
  return {
    r: (n >> 24) & 0xff,
    g: (n >> 16) & 0xff,
    b: (n >> 8) & 0xff,
    a: (n & 0xff) / 255,
  };
}

/** Convert {r, g, b, a} (0–255, a 0–1) to an rgba() CSS string. */
export function rgbaToString({ r, g, b, a }) {
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/**
 * Lerp between two hex colors, returning an rgba() CSS string.
 * @param {string} colorA - Hex color
 * @param {string} colorB - Hex color
 * @param {number} t - 0–1
 */
export function lerpColor(colorA, colorB, t) {
  const a = hexToRgba(colorA);
  const b = hexToRgba(colorB);
  return {
    r: Math.round(lerp(a.r, b.r, t)),
    g: Math.round(lerp(a.g, b.g, t)),
    b: Math.round(lerp(a.b, b.b, t)),
    a: lerp(a.a, b.a, t),
  };
}

/**
 * Sample a multi-stop color gradient at time t (0–1).
 * @param {Array<{stop: number, color: string}>} gradient - Sorted by stop ascending.
 * @param {number} t - 0–1 position along the gradient.
 * @returns {{r,g,b,a}} RGBA values.
 */
export function sampleGradient(gradient, t) {
  if (!gradient || gradient.length === 0) return { r: 255, g: 255, b: 255, a: 1 };
  if (gradient.length === 1) return hexToRgba(gradient[0].color);

  // Clamp t
  t = clamp(t, 0, 1);

  // Find the two surrounding stops
  let lower = gradient[0];
  let upper = gradient[gradient.length - 1];
  for (let i = 0; i < gradient.length - 1; i++) {
    if (t >= gradient[i].stop && t <= gradient[i + 1].stop) {
      lower = gradient[i];
      upper = gradient[i + 1];
      break;
    }
  }

  const range = upper.stop - lower.stop;
  const localT = range === 0 ? 0 : (t - lower.stop) / range;
  return lerpColor(lower.color, upper.color, localT);
}

// ─────────────────────────────────────────────────────────
// Easing functions — all take t in [0,1], return [0,1]
// ─────────────────────────────────────────────────────────

export const EASINGS = {
  linear: (t) => t,

  easeInQuad: (t) => t * t,
  easeOutQuad: (t) => t * (2 - t),
  easeInOutQuad: (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t),

  easeInCubic: (t) => t * t * t,
  easeOutCubic: (t) => --t * t * t + 1,
  easeInOutCubic: (t) =>
    t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1,

  easeOutElastic: (t) => {
    if (t === 0 || t === 1) return t;
    return Math.pow(2, -10 * t) * Math.sin((t - 0.075) * (2 * Math.PI) / 0.3) + 1;
  },

  easeOutBounce: (t) => {
    if (t < 1 / 2.75) return 7.5625 * t * t;
    if (t < 2 / 2.75) return 7.5625 * (t -= 1.5 / 2.75) * t + 0.75;
    if (t < 2.5 / 2.75) return 7.5625 * (t -= 2.25 / 2.75) * t + 0.9375;
    return 7.5625 * (t -= 2.625 / 2.75) * t + 0.984375;
  },

  easeInExpo: (t) => (t === 0 ? 0 : Math.pow(2, 10 * (t - 1))),
  easeOutExpo: (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
};

/** Resolve an easing function by name. Falls back to linear. */
export function getEasing(name) {
  return EASINGS[name] || EASINGS.linear;
}

// ─────────────────────────────────────────────────────────
// Spawn shape helpers
// ─────────────────────────────────────────────────────────

/**
 * Generate a spawn offset {dx, dy} based on spawn shape configuration.
 * @param {string} shape - 'point' | 'circle' | 'ring' | 'line' | 'rect' | 'cone'
 * @param {object} config - Shape-specific params (radius, width, height, angle, spread)
 * @returns {{dx: number, dy: number}}
 */
export function getSpawnOffset(shape, config = {}) {
  const { radius = 0, width = 0, height = 0 } = config;

  switch (shape) {
    case 'circle': {
      const a = randomAngle();
      const r = Math.sqrt(Math.random()) * radius; // sqrt for uniform distribution
      return { dx: Math.cos(a) * r, dy: Math.sin(a) * r };
    }
    case 'ring': {
      const a = randomAngle();
      return { dx: Math.cos(a) * radius, dy: Math.sin(a) * radius };
    }
    case 'line': {
      const t = Math.random() - 0.5;
      return { dx: t * width, dy: 0 };
    }
    case 'rect': {
      return {
        dx: (Math.random() - 0.5) * width,
        dy: (Math.random() - 0.5) * height,
      };
    }
    case 'point':
    default:
      return { dx: 0, dy: 0 };
  }
}

/**
 * Generate initial velocity {vx, vy} based on angle range and speed.
 * @param {number} angleMin - Degrees
 * @param {number} angleMax - Degrees
 * @param {number} speedMin
 * @param {number} speedMax
 */
export function getEmitVelocity(angleMin, angleMax, speedMin, speedMax) {
  const angle = degToRad(randomRange(angleMin, angleMax));
  const speed = randomRange(speedMin, speedMax);
  return {
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
  };
}
