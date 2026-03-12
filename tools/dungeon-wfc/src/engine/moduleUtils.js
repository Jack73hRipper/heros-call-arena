// ─────────────────────────────────────────────────────────
// moduleUtils.js — Module data structures, rotation, socket derivation
//
// Content decoration fields (spawnSlots, contentRole, etc.) allow the
// post-generation room decorator to assign enemies, loot, bosses, and
// spawn points to structurally "empty" rooms.
// ─────────────────────────────────────────────────────────

import { socketChar } from '../utils/tileColors.js';

/** Module size — all modules are MODULE_SIZE x MODULE_SIZE tiles */
export const MODULE_SIZE = 8;

/**
 * Content roles for the room decorator system.
 * - 'flexible'   — Structural template; decorator can assign enemies/loot/spawn/boss.
 * - 'fixed'      — Content is baked into tiles (E/X/S/B); decorator won't touch it.
 * - 'structural' — Never gets content (filler walls, corridors, grand interior pieces).
 */
export const CONTENT_ROLES = ['flexible', 'fixed', 'structural'];

/**
 * Auto-derive spawnSlots from a module's tile grid.
 * Returns an array of { x, y, types } for every interior floor tile
 * (tiles not on the outer edge that are 'F' type).
 */
export function deriveSpawnSlots(tiles) {
  const slots = [];
  const h = tiles.length;
  const w = tiles[0]?.length || 0;
  for (let r = 1; r < h - 1; r++) {
    for (let c = 1; c < w - 1; c++) {
      if (tiles[r][c] === 'F') {
        slots.push({ x: c, y: r, types: ['enemy', 'loot', 'spawn', 'boss'] });
      }
    }
  }
  return slots;
}

/** Create a blank module filled with walls */
export function createBlankModule(name = 'New Module', purpose = 'empty') {
  const tiles = [];
  for (let r = 0; r < MODULE_SIZE; r++) {
    const row = [];
    for (let c = 0; c < MODULE_SIZE; c++) {
      row.push('W');
    }
    tiles.push(row);
  }
  return {
    id: generateId(),
    name,
    purpose,
    width: MODULE_SIZE,
    height: MODULE_SIZE,
    tiles,
    weight: 1.0,
    allowRotation: false,
    // Decorator fields
    contentRole: 'flexible',
    spawnSlots: [],
    maxEnemies: 0,
    maxChests: 0,
    canBeBoss: false,
    canBeSpawn: false,
  };
}

/** Generate a unique id */
export function generateId() {
  return 'mod_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

/**
 * Derive socket string for a module edge.
 * direction: 'north' | 'south' | 'east' | 'west'
 * Returns a string like "WWOOWW" where W=wall, O=open
 */
export function deriveSocket(tiles, direction) {
  const h = tiles.length;
  const w = tiles[0].length;
  let edgeTiles;

  switch (direction) {
    case 'north':
      edgeTiles = tiles[0]; // first row
      break;
    case 'south':
      edgeTiles = tiles[h - 1]; // last row
      break;
    case 'west':
      edgeTiles = tiles.map(row => row[0]); // first column
      break;
    case 'east':
      edgeTiles = tiles.map(row => row[w - 1]); // last column
      break;
    default:
      return '';
  }

  return edgeTiles.map(t => socketChar(t)).join('');
}

/** Get all four sockets for a module */
export function deriveSockets(tiles) {
  return {
    north: deriveSocket(tiles, 'north'),
    south: deriveSocket(tiles, 'south'),
    east: deriveSocket(tiles, 'east'),
    west: deriveSocket(tiles, 'west'),
  };
}

/**
 * Rotate a tile grid 90° clockwise.
 * newTiles[r][c] = oldTiles[N-1-c][r]
 */
export function rotateTiles90CW(tiles) {
  const h = tiles.length;
  const w = tiles[0].length;
  const rotated = [];
  for (let r = 0; r < w; r++) {
    const row = [];
    for (let c = 0; c < h; c++) {
      row.push(tiles[h - 1 - c][r]);
    }
    rotated.push(row);
  }
  return rotated;
}

/**
 * Generate all rotation variants for a module (0°, 90°, 180°, 270°).
 * Returns array of { tiles, sockets, rotation } objects.
 * Deduplicates if rotations produce identical socket signatures.
 */
/**
 * Rotate a single spawn slot coordinate 90° CW within a size×size grid.
 * Matches the transform in rotateTiles90CW: (x, y) → (size-1-y, x)
 */
function rotateSlot90CW(slot, size) {
  return {
    x: size - 1 - slot.y,
    y: slot.x,
    types: slot.types ? [...slot.types] : ['enemy', 'loot', 'spawn', 'boss'],
  };
}

export function generateRotationVariants(mod) {
  const variants = [];
  const seen = new Set();

  let currentTiles = mod.tiles.map(r => [...r]);
  let currentSlots = (mod.spawnSlots || []).map(s => ({ ...s, types: s.types ? [...s.types] : undefined }));
  const size = mod.tiles.length; // MODULE_SIZE (8)

  for (let rot = 0; rot < 4; rot++) {
    if (rot > 0) {
      currentTiles = rotateTiles90CW(currentTiles);
      currentSlots = currentSlots.map(s => rotateSlot90CW(s, size));
    }
    const sockets = deriveSockets(currentTiles);
    const key = `${sockets.north}|${sockets.south}|${sockets.east}|${sockets.west}`;

    if (!seen.has(key)) {
      seen.add(key);
      variants.push({
        tiles: currentTiles.map(r => [...r]),
        sockets,
        rotation: rot * 90,
        sourceId: mod.id,
        sourceName: mod.name,
        purpose: mod.purpose,
        weight: mod.weight,
        // Decorator metadata (carried from source module, slots rotated to match tiles)
        contentRole: mod.contentRole || 'structural',
        spawnSlots: currentSlots.map(s => ({ ...s, types: s.types ? [...s.types] : undefined })),
        maxEnemies: mod.maxEnemies || 0,
        maxChests: mod.maxChests || 0,
        canBeBoss: mod.canBeBoss || false,
        canBeSpawn: mod.canBeSpawn || false,
      });
    }
  }

  return variants;
}

/**
 * Expand the full module library into WFC-ready variants.
 * Each module with allowRotation gets up to 4 variants.
 * Each module without rotation gets 1 variant.
 */
export function expandModules(modules) {
  const variants = [];
  for (const mod of modules) {
    if (mod.allowRotation) {
      variants.push(...generateRotationVariants(mod));
    } else {
      const sockets = deriveSockets(mod.tiles);
      variants.push({
        tiles: mod.tiles.map(r => [...r]),
        sockets,
        rotation: 0,
        sourceId: mod.id,
        sourceName: mod.name,
        purpose: mod.purpose,
        weight: mod.weight,
        // Decorator metadata
        contentRole: mod.contentRole || 'structural',
        spawnSlots: mod.spawnSlots || [],
        maxEnemies: mod.maxEnemies || 0,
        maxChests: mod.maxChests || 0,
        canBeBoss: mod.canBeBoss || false,
        canBeSpawn: mod.canBeSpawn || false,
      });
    }
  }
  return variants;
}

/** Deep clone a module */
export function cloneModule(mod) {
  return JSON.parse(JSON.stringify(mod));
}
