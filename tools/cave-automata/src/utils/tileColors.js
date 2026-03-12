// ─────────────────────────────────────────────────────────
// tileColors.js — Tile type → visual color mapping
//
// Matches the grimdark dungeon aesthetic of the Arena project.
// Consistent with the WFC Dungeon Lab color palette.
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

/** Brighter highlight colors for hover states */
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

/** Colors for room highlighting (cycled through for detected rooms) */
export const ROOM_COLORS = [
  'rgba(74, 144, 226, 0.25)',   // blue
  'rgba(80, 200, 120, 0.25)',   // green
  'rgba(255, 165, 0, 0.25)',    // orange
  'rgba(238, 130, 238, 0.25)',  // violet
  'rgba(255, 99, 71, 0.25)',    // tomato
  'rgba(0, 206, 209, 0.25)',    // dark turquoise
  'rgba(255, 215, 0, 0.25)',    // gold
  'rgba(147, 112, 219, 0.25)',  // medium purple
  'rgba(60, 179, 113, 0.25)',   // medium sea green
  'rgba(255, 105, 180, 0.25)',  // hot pink
];
