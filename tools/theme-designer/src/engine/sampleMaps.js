// ─────────────────────────────────────────────────────────
// sampleMaps.js — Sample dungeon layouts for theme preview
//
// Hardcoded tile grids representing different dungeon
// configurations. Used by the Theme Designer tool to
// preview how a theme looks on an actual layout.
// ─────────────────────────────────────────────────────────

/**
 * Tile legend used by all sample maps:
 *   W = wall
 *   F = floor
 *   C = corridor
 *   D = door
 *   S = spawn
 *   X = chest
 *   T = stairs
 */
export const TILE_LEGEND = {
  'W': 'wall',
  'F': 'floor',
  'C': 'corridor',
  'D': 'door',
  'S': 'spawn',
  'X': 'chest',
  'T': 'stairs',
};

/**
 * Sample dungeon: Classic 5-room dungeon (15x15)
 * Entry room → corridor → large hall → side rooms → boss room
 */
export const SAMPLE_CLASSIC = {
  name: 'Classic Dungeon',
  width: 15,
  height: 15,
  tiles: [
    'WWWWWWWWWWWWWWW',
    'WWWSSFWWWWWWWWW',
    'WWWFFFWWWWWWWWW',
    'WWWFSFWWWFFFWWW',
    'WWWWDWWWWFFFWWW',
    'WWWWCWWWWFXFWWW',
    'WWWWCWWWWWDWWWW',
    'WWWWCCCCCCCWWWW',
    'WWWWCWWWWWCWWWW',
    'WWFFCFWWWWCWWWW',
    'WWFFFFWWFFCFFWW',
    'WWFXFFWWFFDFFWW',
    'WWFFFDCCCCFFFWW',
    'WWFFFFWWFFFFFFW',
    'WWWWWWWWWWWTWWW',
  ].map(row => row.split('')),
};

/**
 * Sample dungeon: Winding corridors (15x15)
 * Narrow passageways connecting small rooms.
 */
export const SAMPLE_CORRIDORS = {
  name: 'Winding Corridors',
  width: 15,
  height: 15,
  tiles: [
    'WWWWWWWWWWWWWWW',
    'WSFFWWWWWWWWWWW',
    'WFFFDCCCCCCWWWW',
    'WSFFWWWWWWCWWWW',
    'WWWWWWWWWWCWWWW',
    'WWWWFFXFWWCWWWW',
    'WWWWFFFFDCCWWWW',
    'WWWWFFFFWWWWWWW',
    'WWWWWDWWWWWWWWW',
    'WCCCCCWWWFFFWWW',
    'WCWWWWWWWFFFWWW',
    'WCWWWFFFWFXFWWW',
    'WCCCCFFFWWDWWWW',
    'WWWWWFFTWWCWWWW',
    'WWWWWWWWWWWWWWW',
  ].map(row => row.split('')),
};

/**
 * Sample dungeon: Large open hall (15x15)
 * Big central room with alcoves and side chambers.
 */
export const SAMPLE_OPEN_HALL = {
  name: 'Open Hall',
  width: 15,
  height: 15,
  tiles: [
    'WWWWWWWWWWWWWWW',
    'WWWWWWSDSWWWWWW',
    'WWWWWWFFFWWWWWW',
    'WWWWWWWDWWWWWWW',
    'WWWXFCCCCCFXWWW',
    'WWWFFFFFFFSFWWW',
    'WWWFFFFFFFFFWWW',
    'WWWDFFFWFFFDWWW',
    'WWWFFFFFFFFFWWW',
    'WWWFFFFFFFSFWWW',
    'WWWXFCCCCCFXWWW',
    'WWWWWWWDWWWWWWW',
    'WWWWWWFFFWWWWWW',
    'WWWWWWFTWWWWWWW',
    'WWWWWWWWWWWWWWW',
  ].map(row => row.split('')),
};

/**
 * Sample dungeon: Boss arena (12x12)
 * Mini boss encounter room.
 */
export const SAMPLE_BOSS = {
  name: 'Boss Arena',
  width: 12,
  height: 12,
  tiles: [
    'WWWWWWWWWWWW',
    'WWWSSSWWWWWW',
    'WWWSSSWWWWWW',
    'WWWWDWWWWWWW',
    'WWCCCCCCWWWW',
    'WWCFFFFFFDWW',
    'WWCFFFFFFDWW',
    'WWCFFFFFXWWW',
    'WWCFFFFFFWWW',
    'WWWFFFFFFWWW',
    'WWWWWTWWWWWW',
    'WWWWWWWWWWWW',
  ].map(row => row.split('')),
};

/**
 * All sample maps keyed by ID.
 */
export const SAMPLE_MAPS = {
  classic: SAMPLE_CLASSIC,
  corridors: SAMPLE_CORRIDORS,
  open_hall: SAMPLE_OPEN_HALL,
  boss: SAMPLE_BOSS,
};

export function getSampleMapIds() {
  return Object.keys(SAMPLE_MAPS);
}

export function getSampleMap(id) {
  return SAMPLE_MAPS[id] || SAMPLE_CLASSIC;
}
