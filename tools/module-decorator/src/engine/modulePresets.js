// ─────────────────────────────────────────────────────────
// modulePresets.js — Built-in WFC module definitions
//
// Direct copy of the tile grids from dungeon-wfc presets.
// We only include the subset of fields needed for decoration.
// ─────────────────────────────────────────────────────────

export const PRESET_MODULES = [
  {
    id: 'preset_solid',
    name: 'Solid Wall',
    purpose: 'empty',
    allowRotation: false,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
    ],
  },
  {
    id: 'preset_corridor_h',
    name: 'Corridor Straight',
    purpose: 'corridor',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['F','F','F','F','F','F'],
      ['F','F','F','F','F','F'],
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
    ],
  },
  {
    id: 'preset_corridor_l',
    name: 'Corridor L-Turn',
    purpose: 'corridor',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['F','F','F','F','W','W'],
      ['F','F','F','F','W','W'],
      ['W','W','F','F','W','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_corridor_t',
    name: 'Corridor T-Junction',
    purpose: 'corridor',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['F','F','F','F','F','F'],
      ['F','F','F','F','F','F'],
      ['W','W','F','F','W','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_corridor_cross',
    name: 'Corridor Crossroads',
    purpose: 'corridor',
    allowRotation: false,
    tiles: [
      ['W','W','F','F','W','W'],
      ['W','W','F','F','W','W'],
      ['F','F','F','F','F','F'],
      ['F','F','F','F','F','F'],
      ['W','W','F','F','W','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_room_dead_end',
    name: 'Dead End Room',
    purpose: 'empty',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_room_passthrough',
    name: 'Room Passthrough',
    purpose: 'empty',
    allowRotation: true,
    tiles: [
      ['W','W','F','F','W','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_room_corner',
    name: 'Room Corner',
    purpose: 'empty',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','F'],
      ['W','F','F','F','F','F'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_room_three_way',
    name: 'Room Three-Way',
    purpose: 'empty',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','F','F','F','F','W'],
      ['F','F','F','F','F','F'],
      ['F','F','F','F','F','F'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_room_hub',
    name: 'Room Hub',
    purpose: 'empty',
    allowRotation: false,
    tiles: [
      ['W','W','F','F','W','W'],
      ['W','F','F','F','F','W'],
      ['F','F','F','F','F','F'],
      ['F','F','F','F','F','F'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_spawn_room',
    name: 'Spawn Room',
    purpose: 'spawn',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','S','S','S','S','W'],
      ['W','S','S','S','S','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_enemy_den',
    name: 'Enemy Den',
    purpose: 'enemy',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','F','E','E','F','W'],
      ['W','F','F','F','F','F'],
      ['W','F','F','F','F','F'],
      ['W','F','E','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_skeleton_hall',
    name: 'Skeleton Hall',
    purpose: 'enemy',
    allowRotation: true,
    tiles: [
      ['W','W','F','F','W','W'],
      ['W','F','F','F','F','W'],
      ['W','E','F','F','E','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_treasury',
    name: 'Treasury',
    purpose: 'loot',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','X','F','F','X','W'],
      ['W','F','F','F','F','W'],
      ['W','F','F','F','F','W'],
      ['W','X','F','F','X','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_boss_chamber',
    name: 'Boss Chamber',
    purpose: 'boss',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','F','F','F','F','W'],
      ['W','F','B','B','F','W'],
      ['W','F','B','B','F','W'],
      ['W','F','F','F','F','W'],
      ['W','W','F','F','W','W'],
    ],
  },
  {
    id: 'preset_doored_corridor',
    name: 'Doored Corridor',
    purpose: 'corridor',
    allowRotation: true,
    tiles: [
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
      ['F','F','D','D','F','F'],
      ['F','F','F','F','F','F'],
      ['W','W','W','W','W','W'],
      ['W','W','W','W','W','W'],
    ],
  },
];

/**
 * Get a module by ID.
 * @param {string} id
 * @returns {Object|undefined}
 */
export function getModuleById(id) {
  return PRESET_MODULES.find(m => m.id === id);
}

/**
 * Get all unique purposes.
 * @returns {string[]}
 */
export function getModulePurposes() {
  return [...new Set(PRESET_MODULES.map(m => m.purpose))];
}
