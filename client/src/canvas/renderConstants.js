/**
 * renderConstants — Shared constants for canvas rendering.
 *
 * Extracted from ArenaRenderer.js (P4 refactoring).
 * Contains tile size, color tables, shape maps, and name maps
 * used by all renderer modules.
 */

export const TILE_SIZE = 48; // pixels per tile (bumped from 40 for closer zoom)

// Player colors — each player gets a unique color by index
export const PLAYER_COLORS = [
  '#4a9ff5', // blue
  '#f54a4a', // red
  '#4af59f', // green
  '#f5c542', // gold
  '#c44af5', // purple
  '#f5884a', // orange
  '#4af5f5', // cyan
  '#f54aa5', // pink
];

// Team colors — unified per team (AI vs human distinguished by shape, not color)
export const TEAM_COLORS = {
  ally: '#4a9ff5',       // blue for all allies (human + AI)
  enemy: '#f54a4a',      // red for all enemies (human + AI)
};

// Phase 4A: Class colors and shapes
export const CLASS_COLORS = {
  crusader: '#4a8fd0',
  confessor: '#f0e060',
  inquisitor: '#a050f0',
  ranger: '#40c040',
  hexblade: '#e04040',
  mage: '#e07020',
  bard: '#d4a017',
  blood_knight: '#8B0000',
  plague_doctor: '#50C878',
  revenant: '#708090',
  shaman: '#8B6914',
};

export const CLASS_SHAPES = {
  crusader: 'square',
  confessor: 'circle',
  inquisitor: 'triangle',
  ranger: 'diamond',
  hexblade: 'star',
  mage: 'hexagon',
  bard: 'crescent',
  blood_knight: 'shield',
  plague_doctor: 'flask',
  revenant: 'coffin',
  shaman: 'totem',
};

export const CLASS_NAMES = {
  crusader: 'Crusader',
  confessor: 'Confessor',
  inquisitor: 'Inquisitor',
  ranger: 'Ranger',
  hexblade: 'Hexblade',
  mage: 'Mage',
  bard: 'Bard',
  blood_knight: 'Blood Knight',
  plague_doctor: 'Plague Doctor',
  revenant: 'Revenant',
  shaman: 'Shaman',
};

// Phase 4C: Enemy type colors, shapes, and names
export const ENEMY_COLORS = {
  demon: '#cc3333',
  skeleton: '#c8c8c8',
  undead_knight: '#6633aa',
  imp: '#ff6644',
  dark_priest: '#8844aa',
  wraith: '#6699cc',
  medusa: '#44aa66',
  acolyte: '#aa4488',
  werewolf: '#9B7924',
  reaper: '#1a1a2e',
  construct: '#7a7a8a',
  imp_lord: '#cc4400',
  demon_boss: '#991111',
  demon_knight: '#aa2222',
  construct_boss: '#5a5a6a',
  ghoul: '#66aa77',
  necromancer: '#442266',
  undead_caster: '#9966bb',
  horror: '#553366',
  insectoid: '#889922',
  caster: '#cc6600',
  evil_snail: '#77aa44',
  goblin_spearman: '#668833',
  shade: '#334455',
};

export const ENEMY_SHAPES = {
  demon: 'diamond',
  skeleton: 'triangle',
  undead_knight: 'star',
  imp: 'triangle',
  dark_priest: 'circle',
  wraith: 'diamond',
  medusa: 'circle',
  acolyte: 'circle',
  werewolf: 'diamond',
  reaper: 'star',
  construct: 'square',
  imp_lord: 'star',
  demon_boss: 'star',
  demon_knight: 'diamond',
  construct_boss: 'star',
  ghoul: 'triangle',
  necromancer: 'star',
  undead_caster: 'triangle',
  horror: 'diamond',
  insectoid: 'triangle',
  caster: 'circle',
  evil_snail: 'circle',
  goblin_spearman: 'triangle',
  shade: 'diamond',
};

export const ENEMY_NAMES = {
  demon: 'Demon',
  skeleton: 'Skeleton',
  undead_knight: 'Undead Knight',
  imp: 'Imp',
  dark_priest: 'Dark Priest',
  wraith: 'Wraith',
  medusa: 'Medusa',
  acolyte: 'Acolyte',
  werewolf: 'Werewolf',
  reaper: 'Reaper',
  construct: 'Construct',
  imp_lord: 'Imp Lord',
  demon_boss: 'Demon Lord',
  demon_knight: 'Demon Knight',
  construct_boss: 'Construct Guardian',
  ghoul: 'Ghoul',
  necromancer: 'Necromancer',
  undead_caster: 'Undead Caster',
  horror: 'Horror',
  insectoid: 'Insectoid',
  caster: 'Dark Caster',
  evil_snail: 'Evil Snail',
  goblin_spearman: 'Goblin Spearman',
  shade: 'Shade',
};

// Phase 4B-2: Dungeon tile colors
export const DUNGEON_COLORS = {
  wall: '#2a2a3a',
  wallBorder: '#3a3a4a',
  floor: '#1a1a2e',
  corridor: '#151528',
  spawn: '#1a2a1a',
  doorClosed: '#8B4513',
  doorOpen: '#A0764B',
  doorOpenBg: '#1a1a2e',
  chest: '#DAA520',
  chestOpened: '#8B7355',
  // Stairs tile colors
  stairs: '#2a3a2a',
  stairsIcon: '#88CC88',
  stairsBorder: '#66AA66',
  // Phase 12C: Portal scroll colors (turquoise + purple redesign)
  portalGlow: '#00F5D4',
  portalCore: '#C77DFF',
  portalRing: '#7B2FBE',
  portalText: '#C0FFF4',
};

// Phase 7E-1: Preview color palette for multi-unit hover path previews.
// Each selected unit gets a unique color from this palette.
export const PREVIEW_COLORS = [
  { line: 'rgba(0, 230, 255, 0.55)',  fill: 'rgba(0, 230, 255, 0.10)',  ghost: 'rgba(0, 230, 255, 0.25)',  door: '#00E6FF' },   // Cyan (primary/player)
  { line: 'rgba(0, 255, 136, 0.55)',  fill: 'rgba(0, 255, 136, 0.10)',  ghost: 'rgba(0, 255, 136, 0.25)',  door: '#00FF88' },   // Green
  { line: 'rgba(255, 165, 0, 0.55)',  fill: 'rgba(255, 165, 0, 0.10)',  ghost: 'rgba(255, 165, 0, 0.25)',  door: '#FFA500' },   // Orange
  { line: 'rgba(187, 102, 255, 0.55)', fill: 'rgba(187, 102, 255, 0.10)', ghost: 'rgba(187, 102, 255, 0.25)', door: '#BB66FF' }, // Purple
  { line: 'rgba(255, 215, 0, 0.55)',  fill: 'rgba(255, 215, 0, 0.10)',  ghost: 'rgba(255, 215, 0, 0.25)',  door: '#FFD700' },   // Gold
];

/**
 * Get a player color by index.
 */
export function getPlayerColor(index) {
  return PLAYER_COLORS[index % PLAYER_COLORS.length];
}
