// ─────────────────────────────────────────────────────────
// tileColors.js — Tile type → visual color mapping
// Matches the grimdark dungeon aesthetic of the Arena project
// Shared by the module decorator for gameplay layer ghost overlay
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
  W: '#3a3a4a',
  F: '#6b6b5e',
  D: '#8b6914',
  C: '#7a7a6e',
  S: '#4a7a4a',
  X: '#c9a02c',
  E: '#8a3a3a',
  B: '#9a2a6a',
};

/** Brighter highlight colors for selected tile / hover */
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

/** Purpose badge colors */
export const PURPOSE_COLORS = {
  empty: '#666',
  corridor: '#7a7a6e',
  spawn: '#4a7a4a',
  enemy: '#8a3a3a',
  loot: '#c9a02c',
  boss: '#9a2a6a',
};
