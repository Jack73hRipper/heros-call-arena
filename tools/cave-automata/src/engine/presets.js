// ─────────────────────────────────────────────────────────
// presets.js — Cellular automata rule presets
//
// Each preset defines parameters that produce a distinct
// cave style. Users can select these as starting points
// and then tweak individual parameters.
// ─────────────────────────────────────────────────────────

export const PRESETS = [
  {
    id: 'natural-caves',
    name: 'Natural Caves',
    description: 'Classic cave formation — smooth organic chambers with connecting passages',
    params: {
      fillPercent: 48,
      birthThreshold: 5,
      survivalThreshold: 4,
      iterations: 5,
    },
  },
  {
    id: 'cavern-network',
    name: 'Cavern Network',
    description: 'Large connected caverns with wide open spaces',
    params: {
      fillPercent: 42,
      birthThreshold: 5,
      survivalThreshold: 4,
      iterations: 7,
    },
  },
  {
    id: 'winding-tunnels',
    name: 'Winding Tunnels',
    description: 'Narrow winding passages with small chambers',
    params: {
      fillPercent: 55,
      birthThreshold: 5,
      survivalThreshold: 4,
      iterations: 4,
    },
  },
  {
    id: 'island-archipelago',
    name: 'Island Archipelago',
    description: 'Scattered floor islands separated by walls — good for multi-chamber layouts',
    params: {
      fillPercent: 58,
      birthThreshold: 5,
      survivalThreshold: 3,
      iterations: 6,
    },
  },
  {
    id: 'open-clearing',
    name: 'Open Clearing',
    description: 'Mostly open space with scattered pillars and wall clusters',
    params: {
      fillPercent: 35,
      birthThreshold: 5,
      survivalThreshold: 4,
      iterations: 6,
    },
  },
  {
    id: 'dense-labyrinth',
    name: 'Dense Labyrinth',
    description: 'Maze-like passages with many dead ends and tight corridors',
    params: {
      fillPercent: 52,
      birthThreshold: 5,
      survivalThreshold: 5,
      iterations: 3,
    },
  },
  {
    id: 'crystal-caverns',
    name: 'Crystal Caverns',
    description: 'Geometric-feeling caves with angular walls and open centers',
    params: {
      fillPercent: 45,
      birthThreshold: 6,
      survivalThreshold: 4,
      iterations: 4,
    },
  },
  {
    id: 'flooded-depths',
    name: 'Flooded Depths',
    description: 'Very open cave floors with scattered thick wall columns',
    params: {
      fillPercent: 38,
      birthThreshold: 6,
      survivalThreshold: 5,
      iterations: 8,
    },
  },
];

/** Map size presets matching game conventions */
export const SIZE_PRESETS = [
  { label: '12 x 12', width: 12, height: 12 },
  { label: '15 x 15', width: 15, height: 15 },
  { label: '20 x 20', width: 20, height: 20 },
  { label: '25 x 25', width: 25, height: 25 },
  { label: '30 x 30', width: 30, height: 30 },
  { label: '40 x 40', width: 40, height: 40 },
  { label: '50 x 50', width: 50, height: 50 },
];

/**
 * Get a preset by ID.
 * @param {string} id
 * @returns {Object|undefined}
 */
export function getPreset(id) {
  return PRESETS.find(p => p.id === id);
}
