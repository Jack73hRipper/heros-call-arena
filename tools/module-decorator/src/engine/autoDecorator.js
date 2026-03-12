// ─────────────────────────────────────────────────────────
// autoDecorator.js — Rule-based automatic sprite assignment
//
// Applies sensible default sprites to a module based on its
// tile types. Walls get wall sprites, floors get floor variants,
// corridors get smooth stone, etc. This gives a starting point
// that can be hand-refined in the editor.
// ─────────────────────────────────────────────────────────

import { createEmptySpriteMap, setBaseSprite, setOverlaySprite } from './spriteMap.js';

// ─── Default sprite regions from the mainlevbuild atlas ─────────

const FLOOR_COBBLE_VARIANTS = [
  { x: 736, y: 272, w: 16, h: 16 },  // Floor_Tile_Cobble1
  { x: 752, y: 272, w: 16, h: 16 },  // Floor_Tile_Cobble2
  { x: 736, y: 288, w: 16, h: 16 },  // Floor_Tile_Cobble3
  { x: 752, y: 288, w: 16, h: 16 },  // Floor_Tile_Cobble4
];

const FLOOR_SMOOTH_VARIANTS = [
  { x: 736, y: 208, w: 16, h: 16 },  // Floor_Tile_Smooth1
  { x: 752, y: 208, w: 16, h: 16 },  // Floor_Tile_Smooth2
  { x: 752, y: 224, w: 16, h: 16 },  // Floor_Tile_Smooth3
  { x: 736, y: 224, w: 16, h: 16 },  // Floor_Tile_Smooth4
  { x: 736, y: 240, w: 16, h: 16 },  // Floor_Tile_Smooth5
  { x: 752, y: 240, w: 16, h: 16 },  // Floor_Tile_Smooth6
];

const WALL_BRICK = { x: 272, y: 304, w: 16, h: 16 };
const WALL_COBBLE = { x: 80, y: 368, w: 16, h: 16 };
const WALL_STONE = { x: 384, y: 432, w: 16, h: 16 };

const WALL_VARIANTS = [WALL_BRICK, WALL_COBBLE, WALL_STONE];

// ─── Seeded PRNG for deterministic auto-decoration ──────────────

function mulberry32(seed) {
  let s = seed | 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ─── Tile type classification ───────────────────────────────────

const FLOOR_TYPES = new Set(['F', 'D', 'C', 'S', 'X', 'E', 'B']);
const WALL_TYPES = new Set(['W']);

/**
 * Auto-decorate a module with default sprites based on tile types.
 *
 * @param {string[][]} tiles - 2D tile grid (e.g., [['W','W',...],['F','F',...]])
 * @param {Object} options
 * @param {number} options.seed - Random seed for variant selection (default: 42)
 * @param {string} options.wallStyle - 'brick', 'cobble', 'stone', or 'mixed' (default: 'mixed')
 * @param {string} options.floorStyle - 'cobble', 'smooth', or 'mixed' (default: 'cobble')
 * @returns {Object} Sprite map with base assignments
 */
export function autoDecorate(tiles, options = {}) {
  const {
    seed = 42,
    wallStyle = 'mixed',
    floorStyle = 'cobble',
  } = options;

  const rng = mulberry32(seed);
  const height = tiles.length;
  const width = tiles[0].length;
  const spriteMap = createEmptySpriteMap(width, height);

  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const tile = tiles[row][col];
      const rand = rng();

      if (WALL_TYPES.has(tile)) {
        // Assign wall sprite
        const wallSprite = getWallSprite(wallStyle, rand);
        setBaseSprite(spriteMap, row, col, wallSprite);
      } else if (FLOOR_TYPES.has(tile)) {
        // Assign floor sprite based on tile subtype
        const flStyle = (tile === 'C' || tile === 'S') ? 'smooth' : floorStyle;
        const floorSprite = getFloorSprite(flStyle, rand);
        setBaseSprite(spriteMap, row, col, floorSprite);
      }
    }
  }

  return spriteMap;
}

/**
 * Auto-add overlay decorations (torches on walls near corridors, etc.)
 * This is an optional enhancement pass on top of autoDecorate.
 *
 * @param {string[][]} tiles - 2D tile grid
 * @param {Object} spriteMap - Existing sprite map (will be modified)
 * @param {Object} options
 * @param {number} options.seed - Random seed
 * @param {Array} options.overlaySprites - Available overlay sprite regions
 * @returns {Object} Modified sprite map
 */
export function autoAddOverlays(tiles, spriteMap, options = {}) {
  const {
    seed = 12345,
    overlaySprites = [],
  } = options;

  if (overlaySprites.length === 0) return spriteMap;

  const rng = mulberry32(seed);
  const height = tiles.length;
  const width = tiles[0].length;

  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const tile = tiles[row][col];

      // Only add overlays to walls adjacent to open spaces
      if (tile === 'W') {
        const hasAdjacentFloor = getNeighborTypes(tiles, row, col).some(t => FLOOR_TYPES.has(t));
        if (hasAdjacentFloor && rng() < 0.15) {
          // 15% chance to get an overlay on qualifying walls
          const idx = Math.floor(rng() * overlaySprites.length);
          setOverlaySprite(spriteMap, row, col, overlaySprites[idx]);
        }
      }
    }
  }

  return spriteMap;
}

// ─── Helpers ────────────────────────────────────────────────────

function getWallSprite(style, rand) {
  switch (style) {
    case 'brick': return WALL_BRICK;
    case 'cobble': return WALL_COBBLE;
    case 'stone': return WALL_STONE;
    case 'mixed':
    default:
      return WALL_VARIANTS[Math.floor(rand * WALL_VARIANTS.length)];
  }
}

function getFloorSprite(style, rand) {
  switch (style) {
    case 'smooth': {
      const idx = Math.floor(rand * FLOOR_SMOOTH_VARIANTS.length);
      return FLOOR_SMOOTH_VARIANTS[idx];
    }
    case 'cobble':
    default: {
      const idx = Math.floor(rand * FLOOR_COBBLE_VARIANTS.length);
      return FLOOR_COBBLE_VARIANTS[idx];
    }
  }
}

function getNeighborTypes(tiles, row, col) {
  const types = [];
  const dirs = [[-1, 0], [1, 0], [0, -1], [0, 1]];
  for (const [dr, dc] of dirs) {
    const r = row + dr;
    const c = col + dc;
    if (r >= 0 && r < tiles.length && c >= 0 && c < tiles[0].length) {
      types.push(tiles[r][c]);
    }
  }
  return types;
}

/**
 * Get the default auto-decoration options presets.
 */
export const AUTO_DECORATE_PRESETS = {
  'Grimdark Brick': { wallStyle: 'brick', floorStyle: 'cobble' },
  'Ancient Stone': { wallStyle: 'stone', floorStyle: 'smooth' },
  'Cobble Dungeon': { wallStyle: 'cobble', floorStyle: 'cobble' },
  'Mixed Ruins': { wallStyle: 'mixed', floorStyle: 'mixed' },
  'Clean Halls': { wallStyle: 'brick', floorStyle: 'smooth' },
};
