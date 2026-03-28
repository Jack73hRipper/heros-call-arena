// ─────────────────────────────────────────────────────────
// WaterAnimation.js — Animated water shimmer overlay for
// flooded floors and shallow_water corridors.
//
// Draws time-varying caustic light ripples on top of water tiles.
// Uses an offscreen canvas with additive blending, throttled to
// ~15fps for performance (matches PropLighting approach).
//
// Called from ArenaRenderer.renderFrame() AFTER drawDungeonTiles(),
// BEFORE highlights and units.
// ─────────────────────────────────────────────────────────

import { TILE_SIZE } from './renderConstants.js';

// ═══════════════════════════════════════════════════════════
//  CONFIGURATION
// ═══════════════════════════════════════════════════════════

const REDRAW_INTERVAL = 66;  // ms — ~15fps
const CAUSTIC_INTENSITY = 0.06; // max caustic brightness
const RIPPLE_MAX = 12;          // max concurrent expanding ripples
const RIPPLE_SPAWN_CHANCE = 0.012; // per water tile per redraw

// ═══════════════════════════════════════════════════════════
//  MODULE STATE
// ═══════════════════════════════════════════════════════════

let _waterCanvas = null;
let _waterLastRedraw = 0;
let _waterAnimTime = 0;
let _waterLastFrame = 0;
let _waterCacheKey = null;

// Expanding ripple pool
const _ripples = [];

// Deterministic hash (same as ThemeEngine/TileProps)
function cellHash(gridX, gridY, salt = 0) {
  let h = ((gridX * 7919) + (gridY * 6271) + (salt * 3571)) | 0;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = (h >> 16) ^ h;
  return ((h & 0x7FFFFFFF) >>> 0) / 0x7FFFFFFF;
}

// ═══════════════════════════════════════════════════════════
//  WATER TILE DETECTION
// ═══════════════════════════════════════════════════════════

/**
 * Check if a theme has water tiles that should be animated.
 * @param {Object} theme - ThemeEngine theme object
 * @returns {boolean}
 */
export function themeHasWater(theme) {
  if (!theme) return false;
  const floorStyle = theme.floor?.style;
  const corridorStyle = theme.corridor?.style;
  return floorStyle === 'flooded' || corridorStyle === 'shallow_water';
}

/**
 * Check if a specific tile type is water-based for the given theme.
 */
function _isWaterTile(tileType, theme) {
  if (tileType === 'floor' || tileType === 'spawn') {
    return theme.floor?.style === 'flooded';
  }
  if (tileType === 'corridor') {
    return theme.corridor?.style === 'shallow_water';
  }
  return false;
}

// ═══════════════════════════════════════════════════════════
//  RIPPLE MANAGEMENT
// ═══════════════════════════════════════════════════════════

function _spawnRipple(px, py) {
  if (_ripples.length >= RIPPLE_MAX) return;
  _ripples.push({
    x: px,
    y: py,
    radius: 0,
    maxRadius: 8 + Math.random() * 12,
    alpha: 0.08 + Math.random() * 0.06,
    speed: 12 + Math.random() * 10, // pixels per second
  });
}

function _updateRipples(dt) {
  for (let i = _ripples.length - 1; i >= 0; i--) {
    const r = _ripples[i];
    r.radius += r.speed * dt;
    if (r.radius >= r.maxRadius) {
      _ripples.splice(i, 1);
    }
  }
}

// ═══════════════════════════════════════════════════════════
//  CLEAR CACHE (call on theme/floor change)
// ═══════════════════════════════════════════════════════════

export function clearWaterCache() {
  _waterCanvas = null;
  _waterLastRedraw = 0;
  _waterCacheKey = null;
  _ripples.length = 0;
}

// ═══════════════════════════════════════════════════════════
//  MAIN DRAW PASS
// ═══════════════════════════════════════════════════════════

/**
 * Draw animated water shimmer overlay on flooded/water tiles.
 *
 * @param {CanvasRenderingContext2D} ctx - Main canvas context
 * @param {Array<Array<number>>} tiles - 2D tile grid
 * @param {Object} tileLegend - Tile char → type mapping
 * @param {Object} theme - Current ThemeEngine theme object
 * @param {number} offsetX - Camera offset X (tiles)
 * @param {number} offsetY - Camera offset Y (tiles)
 */
export function drawWaterAnimation(ctx, tiles, tileLegend, theme, offsetX, offsetY) {
  if (!tiles || !tileLegend || !theme) return;
  if (!themeHasWater(theme)) return;

  const now = performance.now();
  const canvasW = ctx.canvas.width;
  const canvasH = ctx.canvas.height;

  // Advance animation clock
  if (_waterLastFrame > 0) {
    _waterAnimTime += (now - _waterLastFrame) / 1000;
  }
  _waterLastFrame = now;

  // Update ripples every frame (cheap — just position updates)
  const dt = _waterLastFrame > 0 ? Math.min((now - (_waterLastFrame - (now - _waterLastFrame))) / 1000, 0.1) : 0.016;
  _updateRipples(dt);

  // Invalidate on theme change
  const sourceKey = `${theme.id || ''}_${tiles.length}`;
  if (_waterCacheKey !== sourceKey) {
    _waterCanvas = null;
    _waterCacheKey = sourceKey;
    _waterLastRedraw = 0;
    _ripples.length = 0;
  }

  // Create or resize offscreen canvas
  if (!_waterCanvas || _waterCanvas.width !== canvasW || _waterCanvas.height !== canvasH) {
    _waterCanvas = document.createElement('canvas');
    _waterCanvas.width = canvasW;
    _waterCanvas.height = canvasH;
    _waterLastRedraw = 0;
  }

  // Throttled redraw
  if (now - _waterLastRedraw >= REDRAW_INTERVAL) {
    const offCtx = _waterCanvas.getContext('2d');
    offCtx.clearRect(0, 0, canvasW, canvasH);

    const height = tiles.length;
    const width = height > 0 ? tiles[0].length : 0;

    // Viewport bounds
    const tilesVisX = Math.ceil(canvasW / TILE_SIZE) + 1;
    const tilesVisY = Math.ceil(canvasH / TILE_SIZE) + 1;
    const startX = Math.max(0, Math.floor(offsetX));
    const startY = Math.max(0, Math.floor(offsetY));
    const endX = Math.min(width, startX + tilesVisX);
    const endY = Math.min(height, startY + tilesVisY);

    // Get water tint color from theme palette
    const accent = theme.palette?.accent || '#40ccbb';
    const highlight = theme.palette?.highlight || '#88ccff';

    // --- Pass 1: Caustic light patterns on water tiles ---
    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        if (y >= height || x >= width) continue;
        const ch = tiles[y][x];
        const tileType = tileLegend[ch] || 'wall';
        if (!_isWaterTile(tileType, theme)) continue;

        const px = (x - offsetX) * TILE_SIZE;
        const py = (y - offsetY) * TILE_SIZE;

        // Caustic pattern: overlapping sine waves create light network
        const t = _waterAnimTime;
        const seed = cellHash(x, y, 0);

        // Two slow-moving caustic highlights per tile
        for (let i = 0; i < 2; i++) {
          const phase = seed * 6.28 + i * 3.14;
          const cx = px + TILE_SIZE * (0.25 + 0.5 * Math.sin(t * 0.4 + phase));
          const cy = py + TILE_SIZE * (0.25 + 0.5 * Math.cos(t * 0.35 + phase + 1.2));
          const r = 4 + 3 * Math.sin(t * 0.6 + seed * 10 + i);
          const alpha = CAUSTIC_INTENSITY * (0.6 + 0.4 * Math.sin(t * 0.8 + phase));

          offCtx.fillStyle = `rgba(180, 240, 255, ${Math.max(0, alpha).toFixed(3)})`;
          offCtx.beginPath();
          offCtx.ellipse(cx, cy, r, r * 0.6, t * 0.2 + seed, 0, Math.PI * 2);
          offCtx.fill();
        }

        // Occasional ripple spawning
        if (Math.random() < RIPPLE_SPAWN_CHANCE) {
          _spawnRipple(
            px + TILE_SIZE * (0.2 + Math.random() * 0.6),
            py + TILE_SIZE * (0.2 + Math.random() * 0.6),
          );
        }
      }
    }

    // --- Pass 2: Expanding ripple rings ---
    offCtx.lineWidth = 0.8;
    for (const rip of _ripples) {
      const progress = rip.radius / rip.maxRadius;
      const alpha = rip.alpha * (1 - progress); // fade as it expands
      if (alpha < 0.005) continue;
      offCtx.strokeStyle = `rgba(200, 245, 255, ${alpha.toFixed(3)})`;
      offCtx.beginPath();
      offCtx.arc(rip.x, rip.y, rip.radius, 0, Math.PI * 2);
      offCtx.stroke();
    }

    _waterLastRedraw = now;
  }

  // Blit with additive blending
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.drawImage(_waterCanvas, 0, 0);
  ctx.restore();
}
