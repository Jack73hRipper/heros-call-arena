// ─────────────────────────────────────────────────────────
// PropLighting.js — Multi-tile glow pass for light-emitting props
//
// Draws additive radial gradients that spill across multiple
// tiles, creating warm pools of light around torches, braziers,
// candelabras, ritual circles, mushroom clusters, and fountains.
//
// Called from dungeonRenderer.js AFTER room props, BEFORE fog.
// Uses the same deterministic prop placement logic as TileProps.js
// so no server changes are needed.
// ─────────────────────────────────────────────────────────

import { TILE_SIZE } from './renderConstants.js';
import { ARCHETYPE_PROP_SLOTS } from './TileProps.js';

// ═══════════════════════════════════════════════════════════
//  UTILITIES (duplicated from TileProps for self-containment)
// ═══════════════════════════════════════════════════════════

function cellHash(gridX, gridY, salt = 0) {
  let h = ((gridX * 7919) + (gridY * 6271) + (salt * 3571)) | 0;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = (h >> 16) ^ h;
  return ((h & 0x7FFFFFFF) >>> 0) / 0x7FFFFFFF;
}

function hexToRgb(hex) {
  const h2 = hex.replace('#', '');
  return { r: parseInt(h2.slice(0, 2), 16), g: parseInt(h2.slice(2, 4), 16), b: parseInt(h2.slice(4, 6), 16) };
}

// ═══════════════════════════════════════════════════════════
//  LIGHT SOURCE DEFINITIONS
// ═══════════════════════════════════════════════════════════

// radius: in tiles, how far the glow reaches
// intensity: max alpha at center
// color: { r, g, b } — the glow color
// pulse: optional { speed, amplitude } for sine-wave pulsing
const LIGHT_SOURCES = {
  torch_sconce:     { radius: 3.0,  intensity: 0.22, color: { r: 255, g: 160, b: 60 } },
  brazier:          { radius: 3.5,  intensity: 0.28, color: { r: 255, g: 140, b: 40 } },
  candelabra:       { radius: 3.5,  intensity: 0.24, color: { r: 255, g: 180, b: 70 } },
  ritual_circle:    { radius: 4.0,  intensity: 0.22, color: null, pulse: { speed: 1.2, amplitude: 0.06 } },
  mushroom_cluster: { radius: 2.5,  intensity: 0.16, color: null, pulse: { speed: 0.8, amplitude: 0.04 } },
  fountain:         { radius: 2.5,  intensity: 0.14, color: { r: 100, g: 180, b: 220 } },
  altar:            { radius: 2.0,  intensity: 0.12, color: null },
};

// ═══════════════════════════════════════════════════════════
//  POSITION RESOLUTION (mirrors TileProps._resolvePosition)
// ═══════════════════════════════════════════════════════════

function _resolvePosition(position, bounds, seed) {
  const { x_min, y_min, x_max, y_max } = bounds;
  const floorW = x_max - x_min + 1, floorH = y_max - y_min + 1;
  const midX = Math.floor((x_min + x_max) / 2), midY = Math.floor((y_min + y_max) / 2);
  switch (position) {
    case 'center': return [{ x: midX, y: midY }];
    case 'corners': return [{ x: x_min, y: y_min }, { x: x_max, y: y_min }, { x: x_min, y: y_max }, { x: x_max, y: y_max }];
    case 'flanking_center': return [{ x: midX - 1, y: midY }, { x: midX + 1, y: midY }];
    case 'wall_left': return [{ x: x_min, y: midY }];
    case 'wall_right': return [{ x: x_max, y: midY }];
    case 'wall_top': { const tiles = []; for (let tx = x_min + 1; tx < x_max; tx += 2) tiles.push({ x: tx, y: y_min }); return tiles; }
    case 'wall_bottom': { const tiles = []; for (let tx = x_min + 1; tx < x_max; tx += 2) tiles.push({ x: tx, y: y_max }); return tiles; }
    case 'random_floor': {
      const count = 1 + Math.floor(cellHash(seed, 0, 90) * 2);
      const tiles = [];
      for (let i = 0; i < count; i++) tiles.push({ x: x_min + Math.floor(cellHash(seed, i, 91) * floorW), y: y_min + Math.floor(cellHash(seed, i, 92) * floorH) });
      return tiles;
    }
    default: return [];
  }
}

function _pickFocal(focalOptions, seed, affinities) {
  const valid = focalOptions.filter(f => { const aff = affinities[f.prop]; return aff !== undefined && aff > 0; });
  if (valid.length === 0) return null;
  const weighted = valid.map(f => ({ prop: f.prop, weight: f.weight * (affinities[f.prop] || 0) }));
  const totalWeight = weighted.reduce((sum, w) => sum + w.weight, 0);
  if (totalWeight <= 0) return null;
  let roll = cellHash(seed, 0, 200) * totalWeight;
  for (const w of weighted) { roll -= w.weight; if (roll <= 0) return w.prop; }
  return weighted[weighted.length - 1].prop;
}

// ═══════════════════════════════════════════════════════════
//  LIGHT SOURCE COLLECTION
// ═══════════════════════════════════════════════════════════

/**
 * Collect all light-emitting prop positions for a set of rooms.
 * Uses identical placement logic to drawRoomProps in TileProps.js.
 *
 * @param {Array} dungeonRooms - Array of { archetype, bounds }
 * @param {Object} theme - ThemeEngine theme object
 * @returns {Array<{ x: number, y: number, light: Object }>}
 */
export function collectLightSources(dungeonRooms, theme) {
  if (!dungeonRooms || !theme) return [];
  const affinities = theme.propAffinities || {};
  const sources = [];

  for (const room of dungeonRooms) {
    const b = room.bounds;
    if (!b) continue;
    const inner = {
      x_min: b.x_min + 1,
      y_min: b.y_min + 1,
      x_max: b.x_max - 1,
      y_max: b.y_max - 1,
    };
    const archetype = room.archetype || 'empty';
    const config = ARCHETYPE_PROP_SLOTS[archetype];
    if (!config) continue;
    const seed = ((b.x_min * 7919) + (b.y_min * 6271)) & 0x7FFFFFFF;
    const maxProps = config.maxProps || 99;
    let propsPlaced = 0;
    const claimed = new Set();

    const _collectSlot = (propName, position, slotSeed) => {
      const light = LIGHT_SOURCES[propName];
      if (!light) return false;
      const positions = _resolvePosition(position, inner, slotSeed);
      let placedAny = false;
      for (const pos of positions) {
        const key = `${pos.x},${pos.y}`;
        if (claimed.has(key)) continue;
        claimed.add(key);
        placedAny = true;

        // Resolve color: use palette accent for magic props, or specified color
        let color = light.color;
        if (!color && theme.palette) {
          const rgb = hexToRgb(theme.palette.accent);
          color = { r: rgb.r, g: rgb.g, b: rgb.b };
        }

        sources.push({
          x: pos.x,
          y: pos.y,
          radius: light.radius,
          intensity: light.intensity,
          color,
          pulse: light.pulse || null,
          prop: propName,
        });
      }
      return placedAny;
    };

    // Focal prop
    if (config.focal && config.focal.length > 0 && propsPlaced < maxProps) {
      const focalProp = _pickFocal(config.focal, seed, affinities);
      if (focalProp && _collectSlot(focalProp, 'center', seed)) propsPlaced++;
    }

    // Accent props (same priority logic as TileProps)
    const _POSITION_PRIORITY = { center: 0, flanking_center: 1, corners: 2, wall_top: 3, wall_bottom: 3, wall_left: 4, wall_right: 4, random_floor: 5 };
    if (config.accents) {
      const sortedAccents = config.accents.map((s, i) => ({ ...s, _origIdx: i }))
        .sort((a, b) => (_POSITION_PRIORITY[a.position] ?? 9) - (_POSITION_PRIORITY[b.position] ?? 9));
      for (const slot of sortedAccents) {
        if (propsPlaced >= maxProps) break;
        const i = slot._origIdx;
        const affinity = affinities[slot.prop];
        if (affinity === undefined || affinity <= 0) continue;
        const effectiveChance = slot.chance * affinity;
        if (cellHash(seed, i, 100) >= effectiveChance) continue;
        if (_collectSlot(slot.prop, slot.position, seed + i * 13)) propsPlaced++;
      }
    }
  }

  return sources;
}

// ═══════════════════════════════════════════════════════════
//  LIGHT SOURCE CACHE
// ═══════════════════════════════════════════════════════════

let _cachedSources = null;
let _cacheKey = null;

/**
 * Get (or recompute) the light sources for the current dungeon.
 * Cached until rooms/theme change.
 */
function _getLightSources(dungeonRooms, theme) {
  const key = `${theme?.id || ''}_${dungeonRooms?.length || 0}`;
  if (_cacheKey === key && _cachedSources) return _cachedSources;
  _cachedSources = collectLightSources(dungeonRooms, theme);
  _cacheKey = key;
  return _cachedSources;
}

/** Clear the light source cache (call on theme/floor change). */
export function clearLightCache() {
  _cachedSources = null;
  _cacheKey = null;
  _ambientLightMap = null;
  _ambientLightCacheKey = null;
  _darknessCanvas = null;
  _darknessCacheKey = null;
  _glowCanvas = null;
  _glowLastRedraw = 0;
  _glowSourceKey = null;
}

// ═══════════════════════════════════════════════════════════
//  MODULE-LEVEL ANIMATION CLOCK
// ═══════════════════════════════════════════════════════════

let _lightAnimTime = 0;
let _lightLastFrame = 0;

// ═══════════════════════════════════════════════════════════
//  GLOW OFFSCREEN CANVAS CACHE (P-C optimization)
// ═══════════════════════════════════════════════════════════

let _glowCanvas = null;
let _glowLastRedraw = 0;
const GLOW_REDRAW_INTERVAL = 100; // ms — 10fps for flicker animation
let _glowSourceKey = null;        // invalidation key for room/theme changes

// ═══════════════════════════════════════════════════════════
//  GLOW RENDERING PASS
// ═══════════════════════════════════════════════════════════

/**
 * Draw multi-tile additive glow halos for all light-emitting props.
 * Uses 'lighter' composite operation for soft additive blending.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array} dungeonRooms - Room data from server
 * @param {Object} theme - Current ThemeEngine theme object
 * @param {number} offsetX - Camera offset X (tiles)
 * @param {number} offsetY - Camera offset Y (tiles)
 */
export function drawPropGlowPass(ctx, dungeonRooms, theme, offsetX, offsetY) {
  if (!dungeonRooms || !theme) return;
  const sources = _getLightSources(dungeonRooms, theme);
  if (sources.length === 0) return;

  // Advance animation clock for pulsing effects
  const now = performance.now();
  if (_lightLastFrame > 0) {
    _lightAnimTime += (now - _lightLastFrame) / 1000;
  }
  _lightLastFrame = now;

  const canvasW = ctx.canvas.width;
  const canvasH = ctx.canvas.height;

  // Invalidate glow canvas on room/theme change
  const sourceKey = `${theme?.id || ''}_${dungeonRooms?.length || 0}`;
  if (_glowSourceKey !== sourceKey) {
    _glowCanvas = null;
    _glowSourceKey = sourceKey;
    _glowLastRedraw = 0;
  }

  // Create or resize offscreen canvas to match viewport
  if (!_glowCanvas || _glowCanvas.width !== canvasW || _glowCanvas.height !== canvasH) {
    _glowCanvas = document.createElement('canvas');
    _glowCanvas.width = canvasW;
    _glowCanvas.height = canvasH;
    _glowLastRedraw = 0; // force redraw after resize
  }

  // Throttled redraw: re-render glow sources at ~10fps for flicker animation
  if (now - _glowLastRedraw >= GLOW_REDRAW_INTERVAL) {
    const offCtx = _glowCanvas.getContext('2d');
    offCtx.clearRect(0, 0, canvasW, canvasH);

    // The offscreen canvas uses 'lighter' composite so overlapping glows
    // blend additively, matching the original behavior.
    offCtx.globalCompositeOperation = 'lighter';

    for (const src of sources) {
      const px = (src.x - offsetX) * TILE_SIZE + TILE_SIZE / 2;
      const py = (src.y - offsetY) * TILE_SIZE + TILE_SIZE / 2;
      const radiusPx = src.radius * TILE_SIZE;

      // Calculate pulsing intensity
      let intensity = src.intensity;
      if (src.pulse) {
        const wave = Math.sin(_lightAnimTime * src.pulse.speed * Math.PI * 2);
        intensity += wave * src.pulse.amplitude;
      }

      // Add subtle flicker for fire-based sources
      const isFireSource = src.prop === 'torch_sconce' || src.prop === 'brazier' || src.prop === 'candelabra';
      if (isFireSource) {
        const flicker = Math.sin(_lightAnimTime * 7.3 + src.x * 3.1 + src.y * 5.7) * 0.012
                       + Math.sin(_lightAnimTime * 11.1 + src.x * 7.9) * 0.008;
        intensity += flicker;
      }
      intensity = Math.max(0, intensity);

      const { r, g, b } = src.color;
      const grad = offCtx.createRadialGradient(px, py, 0, px, py, radiusPx);
      grad.addColorStop(0,   `rgba(${r}, ${g}, ${b}, ${(intensity * 1.0).toFixed(3)})`);
      grad.addColorStop(0.3, `rgba(${r}, ${g}, ${b}, ${(intensity * 0.6).toFixed(3)})`);
      grad.addColorStop(0.6, `rgba(${r}, ${g}, ${b}, ${(intensity * 0.25).toFixed(3)})`);
      grad.addColorStop(1,   `rgba(${r}, ${g}, ${b}, 0)`);

      offCtx.fillStyle = grad;
      offCtx.beginPath();
      offCtx.arc(px, py, radiusPx, 0, Math.PI * 2);
      offCtx.fill();
    }

    _glowLastRedraw = now;
  }

  // Blit the cached glow canvas with additive blending
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.drawImage(_glowCanvas, 0, 0);
  ctx.restore();
}

// ═══════════════════════════════════════════════════════════
//  FOG MODULATION DATA
// ═══════════════════════════════════════════════════════════

/**
 * Build a Map of tile keys → fog alpha reduction for tiles near light sources.
 * Used by the fog renderer to lighten revealed tiles near props.
 *
 * @param {Array} dungeonRooms
 * @param {Object} theme
 * @returns {Map<string, number>} key → alpha reduction (0.0 to 0.25)
 */
export function buildFogLightMap(dungeonRooms, theme) {
  const map = new Map();
  const sources = _getLightSources(dungeonRooms, theme);
  if (sources.length === 0) return map;

  for (const src of sources) {
    const radiusTiles = Math.ceil(src.radius);
    for (let dy = -radiusTiles; dy <= radiusTiles; dy++) {
      for (let dx = -radiusTiles; dx <= radiusTiles; dx++) {
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > src.radius) continue;
        const tx = src.x + dx;
        const ty = src.y + dy;
        const key = `${tx},${ty}`;
        // Smooth falloff: full reduction at center, 0 at edge
        const falloff = 1 - (dist / src.radius);
        const reduction = falloff * falloff * 0.25; // quadratic falloff, max 0.25 alpha reduction
        const existing = map.get(key) || 0;
        // Additive stacking from multiple sources, capped at 0.3
        map.set(key, Math.min(0.3, existing + reduction));
      }
    }
  }

  return map;
}

// ═══════════════════════════════════════════════════════════
//  AMBIENT DARKNESS PASS
// ═══════════════════════════════════════════════════════════

// Ambient darkness light map cache (for visible tiles)
let _ambientLightMap = null;
let _ambientLightCacheKey = null;

// Offscreen darkness canvas cache (P-A optimization)
let _darknessCanvas = null;
let _darknessCacheKey = null;

/**
 * Build a Map of tile keys → light intensity for visible tiles near light sources.
 * Used by drawAmbientDarknessPass to carve light out of the darkness overlay.
 */
function _getAmbientLightMap(dungeonRooms, theme) {
  const key = `${theme?.id || ''}_${dungeonRooms?.length || 0}`;
  if (_ambientLightCacheKey === key && _ambientLightMap) return _ambientLightMap;

  const map = new Map();
  const sources = _getLightSources(dungeonRooms, theme);
  for (const src of sources) {
    // Use a wider radius for the darkness carve-out than the glow visual
    const effectiveRadius = src.radius * 1.3;
    const radiusTiles = Math.ceil(effectiveRadius);
    for (let dy = -radiusTiles; dy <= radiusTiles; dy++) {
      for (let dx = -radiusTiles; dx <= radiusTiles; dx++) {
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > effectiveRadius) continue;
        const tx = src.x + dx;
        const ty = src.y + dy;
        const key2 = `${tx},${ty}`;
        const falloff = 1 - (dist / effectiveRadius);
        const reduction = falloff * falloff * 0.95;
        const existing = map.get(key2) || 0;
        map.set(key2, Math.min(1.0, existing + reduction));
      }
    }
  }

  _ambientLightMap = map;
  _ambientLightCacheKey = key;
  return map;
}

/**
 * Draw a semi-transparent darkness overlay on all visible tiles,
 * with light sources carving out bright pools.
 *
 * This creates contrast so prop lights feel like real illumination
 * rather than faint color washes on an already-bright scene.
 *
 * P-A optimization: renders to an offscreen canvas and blits with
 * a single drawImage() per frame. Re-renders only when visibleTiles
 * changes (once per turn), or on theme/floor change.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} gridWidth
 * @param {number} gridHeight
 * @param {Set<string>} visibleTiles - Currently visible tile keys
 * @param {number} offsetX - Camera offset X (tiles)
 * @param {number} offsetY - Camera offset Y (tiles)
 * @param {Array} dungeonRooms - Room data from server
 * @param {Object} theme - Current ThemeEngine theme object
 * @param {number} baseDarkness - Base darkness alpha (0.0–0.6), from theme config
 */
export function drawAmbientDarknessPass(ctx, gridWidth, gridHeight, visibleTiles, offsetX, offsetY, dungeonRooms, theme, baseDarkness = 0.35) {
  if (!visibleTiles || !dungeonRooms || dungeonRooms.length === 0) return;
  if (baseDarkness <= 0) return;

  const canvasW = ctx.canvas.width;
  const canvasH = ctx.canvas.height;
  const themeId = theme?.id || '';
  const roomCount = dungeonRooms.length;

  // Cache key: visibleTiles.size is a fast O(1) proxy — the Set grows when
  // the player reveals new tiles (once per turn). Theme/room/baseDarkness
  // changes also invalidate. offsetX/offsetY are included because the
  // offscreen canvas is viewport-scoped.
  const newKey = `${themeId}_${roomCount}_${baseDarkness}_${visibleTiles.size}_${offsetX}_${offsetY}_${canvasW}_${canvasH}`;

  if (_darknessCacheKey === newKey && _darknessCanvas) {
    // Cache hit — blit the pre-rendered darkness overlay
    ctx.drawImage(_darknessCanvas, 0, 0);
    return;
  }

  // Cache miss — render darkness to an offscreen canvas

  // Create or resize the offscreen canvas to match the viewport
  if (!_darknessCanvas || _darknessCanvas.width !== canvasW || _darknessCanvas.height !== canvasH) {
    _darknessCanvas = document.createElement('canvas');
    _darknessCanvas.width = canvasW;
    _darknessCanvas.height = canvasH;
  }

  const offCtx = _darknessCanvas.getContext('2d');
  offCtx.clearRect(0, 0, canvasW, canvasH);

  const lightMap = _getAmbientLightMap(dungeonRooms, theme);

  // Only iterate tiles visible in the current viewport
  const tilesVisibleX = Math.ceil(canvasW / TILE_SIZE) + 1;
  const tilesVisibleY = Math.ceil(canvasH / TILE_SIZE) + 1;
  const startX = Math.max(0, Math.floor(offsetX));
  const startY = Math.max(0, Math.floor(offsetY));
  const endX = Math.min(gridWidth, startX + tilesVisibleX);
  const endY = Math.min(gridHeight, startY + tilesVisibleY);

  for (let x = startX; x < endX; x++) {
    for (let y = startY; y < endY; y++) {
      const key = `${x},${y}`;
      if (!visibleTiles.has(key)) continue; // Only darken visible tiles — fog handles the rest

      const lightReduction = lightMap.get(key) || 0;
      const alpha = Math.max(0, baseDarkness * (1 - lightReduction));
      if (alpha < 0.005) continue; // Skip fully lit tiles

      offCtx.fillStyle = `rgba(0, 0, 0, ${alpha.toFixed(3)})`;
      offCtx.fillRect((x - offsetX) * TILE_SIZE, (y - offsetY) * TILE_SIZE, TILE_SIZE, TILE_SIZE);
    }
  }

  _darknessCacheKey = newKey;

  // Blit to the main canvas
  ctx.drawImage(_darknessCanvas, 0, 0);
}

// Fog light map cache
let _fogLightMap = null;
let _fogLightCacheKey = null;

/**
 * Get (or recompute) the fog light modulation map.
 */
export function getFogLightMap(dungeonRooms, theme) {
  const key = `${theme?.id || ''}_${dungeonRooms?.length || 0}`;
  if (_fogLightCacheKey === key && _fogLightMap) return _fogLightMap;
  _fogLightMap = buildFogLightMap(dungeonRooms, theme);
  _fogLightCacheKey = key;
  return _fogLightMap;
}
