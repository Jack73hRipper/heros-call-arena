// ─────────────────────────────────────────────────────────
// tileColors.js — Tile type → visual color mapping
// Matches the grimdark dungeon aesthetic of the Arena project
// ─────────────────────────────────────────────────────────

export const TILE_TYPES = {
  W: 'wall',
  F: 'floor',
  D: 'door',
  C: 'corridor',
  S: 'spawn',
  X: 'chest',
  E: 'enemy_spawn',
  B: 'boss_spawn',
};

/** Colors for rendering tiles on the canvas */
export const TILE_COLORS = {
  W: '#3a3a4a',   // dark stone wall
  F: '#6b6b5e',   // cobble floor
  D: '#8b6914',   // wooden door
  C: '#7a7a6e',   // corridor (slightly lighter floor)
  S: '#4a7a4a',   // spawn (greenish tint)
  X: '#c9a02c',   // chest (gold)
  E: '#8a3a3a',   // enemy spawn (red)
  B: '#9a2a6a',   // boss spawn (purple-red)
};

/** Brighter highlight colors for the module editor selected tile */
export const TILE_HIGHLIGHTS = {
  W: '#5a5a6a',
  F: '#8b8b7e',
  D: '#ab8934',
  C: '#9a9a8e',
  S: '#6a9a6a',
  X: '#e9c04c',
  E: '#aa5a5a',
  B: '#ba4a8a',
};

/** Border/outline colors */
export const TILE_BORDERS = {
  W: '#2a2a3a',
  F: '#5b5b4e',
  D: '#6b4904',
  C: '#6a6a5e',
  S: '#3a6a3a',
  X: '#a9801c',
  E: '#6a1a1a',
  B: '#7a0a4a',
};

/** Ordered list of paintable tile types for the editor toolbar */
export const PAINT_TILES = ['W', 'F', 'D', 'C', 'S', 'X', 'E', 'B'];

/** Tile labels for UI display */
export const TILE_LABELS = {
  W: 'Wall',
  F: 'Floor',
  D: 'Door',
  C: 'Corridor',
  S: 'Spawn',
  X: 'Chest',
  E: 'Enemy',
  B: 'Boss',
};

/**
 * For socket matching, these tile types are treated as "open" (passable).
 * Used to auto-derive socket patterns from edge tiles.
 */
export const OPEN_TILES = new Set(['F', 'D', 'C', 'S', 'X', 'E', 'B']);

/**
 * Simplify a tile type for socket pattern comparison.
 * All open tiles become 'O', walls stay 'W'.
 */
export function socketChar(tile) {
  return OPEN_TILES.has(tile) ? 'O' : 'W';
}
